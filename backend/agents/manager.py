"""Farm Manager Agent: picks the specialists, merges their proposals, and writes the final answer.

Flow for one question:
  1. Search farm memory for similar past incidents.
  2. Select the relevant specialist agents by keyword.
  3. Run the specialists, then the Finance Agent costs their proposals.
  4. Merge duplicate proposals and save them as "proposed" (nothing is executed here).
  5. Write the final answer with Gemini if configured, otherwise with the demo template.

Optional: pass an `emit` callback to receive live events while the run progresses.
"""
import json
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from backend.agents.base import AgentContext, AgentFinding
from backend.agents.breeding import BreedingAgent
from backend.agents.finance import FinanceAgent
from backend.agents.health import HealthAgent
from backend.agents.inventory import InventoryAgent
from backend.agents.nutrition import NutritionAgent
from backend.config import settings
from backend.services import herd as herd_service
from backend.services import llm
from backend.services.actions import build_description, create_proposals, serialize_action
from backend.services.memory import search_memory

ROUTES = {
    "Nutrition Agent": ["feed", "nutrition", "food", "diet", "milk", "fodder", "grass",
                        "hay", "silage", "pellet", "yield", "eat", "appetite"],
    "Breeding Agent": ["breed", "heat", "pregnan", "insemination", "calf", "bull",
                       "mating", "calving", "cycle"],
    "Inventory Agent": ["stock", "inventory", "order", "buy", "reorder", "supply",
                        "supplies", "store", "run out", "running low"],
    "Finance Agent": ["cost", "money", "price", "budget", "spend", "expense",
                      "rupee", "cheap", "afford", "profit"],
}
LANG_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def select_agents(question: str) -> set[str]:
    """Health always runs (safety first). Other agents run when the question mentions their topic."""
    q = question.lower()
    selected = {name for name, words in ROUTES.items() if any(w in q for w in words)}
    if not selected:
        # A general question like "how is the herd?" gets the full check
        selected = {"Nutrition Agent", "Breeding Agent", "Inventory Agent"}
    selected.add("Health Agent")
    return selected


def merge_actions(raw: list[dict]) -> list[dict]:
    """Combine proposals about the same animal or feed item into one, keeping every reason."""
    grouped: dict[tuple[str, str], dict] = {}
    for action in raw:
        key = (action["action_type"], action["parameters"]["target"])
        if key not in grouped:
            grouped[key] = {
                "action_type": action["action_type"],
                "priority": action["priority"],
                "reasons": [],
                "parameters": dict(action["parameters"]),
            }
        group = grouped[key]
        if PRIORITY_RANK[action["priority"]] < PRIORITY_RANK[group["priority"]]:
            group["priority"] = action["priority"]
        if action["reason"] not in group["reasons"]:
            group["reasons"].append(action["reason"])

    merged = []
    for group in grouped.values():
        params = group["parameters"]
        params["reasons"] = group["reasons"]
        description = build_description(
            group["action_type"], params["label"], group["reasons"], params
        )
        merged.append({
            "action_type": group["action_type"],
            "priority": group["priority"],
            "description": description,
            "parameters": params,
        })
    return merged


def _demo_answer(findings: list[AgentFinding], memory: list[dict], proposals: list[dict]) -> str:
    lines = []
    attention = [f for f in findings if f.status != "ok"]
    if attention:
        lines.append("Here is what the farm records show:")
        for finding in attention:
            for item in finding.findings[:2]:
                lines.append(f"- {item}")
    else:
        lines.append("The farm records look stable for this question.")

    if memory:
        top = memory[0]
        lines.append(
            f"A similar past incident was '{top['title']}'. Outcome: {top['outcome'] or 'not recorded'}. "
            "This is useful context, not proof of the current cause."
        )
    if proposals:
        lines.append(f"I have proposed {len(proposals)} action(s) for your approval. Nothing has been carried out yet.")
    lines.append("For any animal health concern, please consult a veterinarian.")
    return "\n".join(lines)


def _llm_answer(question: str, lang: str, findings: list[AgentFinding],
                memory: list[dict], proposals: list[dict]) -> str:
    payload = {
        "question": question,
        "agent_findings": [
            {"agent": f.agent, "status": f.status, "findings": f.findings} for f in findings
        ],
        "similar_past_incidents": [
            {"title": mem["title"], "outcome": mem["outcome"]} for mem in memory
        ],
        "proposed_actions": [
            {"action_type": p["action_type"], "description": p["description"], "priority": p["priority"]}
            for p in proposals
        ],
    }
    prompt = f"""You are the Farm Manager Agent for a small livestock farm.
Write a short, practical answer for the farmer.

Rules:
- Write the "answer" value in {LANG_NAMES[lang]}.
- Use only the facts in the DATA. Do not invent animals, numbers or costs.
- Past incidents are context only, not proof of the current cause.
- Never say an action has been carried out. Actions are only proposed and wait for the farmer's approval.
- Do not diagnose, and do not recommend medicines or treatments. Recommend a veterinarian for health concerns.
- Keep the answer under 150 words.

Return ONLY a JSON object in this form: {{"answer": "..."}}

DATA:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""
    result = llm.generate_json(prompt)
    answer = result.get("answer", "")
    if not isinstance(answer, str) or not answer.strip():
        raise llm.LLMError("Gemini returned an empty answer")
    return answer.strip()


def compose_answer(question: str, lang: str, findings: list[AgentFinding],
                   memory: list[dict], proposals: list[dict]) -> tuple[str, str, str | None]:
    """Return (answer, ai_mode_used, fallback_reason)."""
    if settings.gemini_enabled:
        try:
            return _llm_answer(question, lang, findings, memory, proposals), "gemini", None
        except llm.LLMError as exc:
            reason = str(exc)[:300]
    else:
        reason = "GEMINI_API_KEY is not set, so demo mode answered"
    return _demo_answer(findings, memory, proposals), "demo", reason


def run_manager(db: Session, question: str, lang: str = "en", emit=None) -> dict:
    emit = emit or (lambda event: None)  # live updates for the streaming endpoint

    today = date.today()
    herd = herd_service.get_herd(db)
    memory = search_memory(db, question)
    ctx = AgentContext(db=db, herd=herd, today=today, memory=memory)

    selected = select_agents(question)
    emit({"event": "started", "data": {"agents": sorted(selected)}})

    specialists = [HealthAgent(), NutritionAgent(), BreedingAgent(), InventoryAgent()]

    findings: list[AgentFinding] = []
    raw_actions: list[dict] = []
    for agent in specialists:
        if agent.name in selected:
            finding = agent.run(ctx)
            findings.append(finding)
            raw_actions.extend(finding.actions)
            emit({"event": "agent_done", "data": {
                "agent": finding.agent, "status": finding.status, "summary": finding.summary}})

    actions = merge_actions(raw_actions)
    if actions or "Finance Agent" in selected:
        finance = FinanceAgent().run(ctx, actions)  # adds cost to each action
        findings.append(finance)
        emit({"event": "agent_done", "data": {
            "agent": finance.agent, "status": finance.status, "summary": finance.summary}})

    rows = create_proposals(db, actions)
    proposals = [serialize_action(r) for r in rows]
    emit({"event": "proposals_ready", "data": {
        "count": len(proposals), "proposed_actions": proposals}})

    answer, ai_mode, reason = compose_answer(question, lang, findings, memory, proposals)
    language_note = None
    if lang != "en" and ai_mode == "demo":
        language_note = "Demo mode answers in English. Live Gemini answers in the requested language."

    return {
        "question": question,
        "language": lang,
        "language_note": language_note,
        "ai_mode_used": ai_mode,
        "fallback_reason": reason,
        "agents_consulted": [f.agent for f in findings],
        "final_recommendation": answer,
        "agent_findings": [
            {"agent": f.agent, "status": f.status, "summary": f.summary, "findings": f.findings}
            for f in findings
        ],
        "memory_matches": memory,
        "proposed_actions": proposals,
        "generated_at": datetime.now(timezone.utc),
    }