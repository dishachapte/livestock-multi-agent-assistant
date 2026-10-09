"""Health Agent: herd traffic lights, symptom-report screening, and milk anomalies.

Findings come from two places:
  * the herd's health indicators (temperature history and milk trend), and
  * farmer symptom reports saved through POST /api/assess (last 7 days).
Everything is passed to the Farm Manager, which combines it with the other agents.
"""
import json
from datetime import datetime, timedelta, timezone

from backend import models as m
from backend.agents.base import AgentContext, AgentFinding, make_action, raise_status

REPORT_WINDOW_DAYS = 7
PRIORITY_STATUS = {"urgent": "critical", "high": "critical", "medium": "attention", "low": "ok"}


class HealthAgent:
    name = "Health Agent"

    def run(self, ctx: AgentContext) -> AgentFinding:
        status = "ok"
        findings: list[str] = []
        actions: list[dict] = []
        red_count = yellow_count = 0

        for animal in ctx.herd:
            ind = animal["health_indicator"]
            label = f"{animal['name']} ({animal['tag_id']})"
            target = f"animal:{animal['tag_id']}"
            reasons = "; ".join(ind["explanations"])

            if ind["color"] == "red":
                red_count += 1
                status = raise_status(status, "critical")
                findings.append(f"{label} is RED: {reasons}")
                actions.append(make_action("flag_animal", target, label, "high", reasons,
                                           {"animal_id": animal["id"]}))
                if any("fever" in e.lower() for e in ind["explanations"]):
                    tomorrow = (ctx.today + timedelta(days=1)).isoformat()
                    actions.append(make_action(
                        "book_vet", target, label, "high",
                        "Fever reported. A veterinarian should examine this animal.",
                        {"animal_id": animal["id"], "requested_for": tomorrow},
                    ))

            elif ind["color"] == "yellow":
                yellow_count += 1
                status = raise_status(status, "attention")
                findings.append(f"{label} to watch: {reasons}")
                actions.append(make_action("flag_animal", target, label, "medium", reasons,
                                           {"animal_id": animal["id"]}))

        report_findings, report_actions, report_status = self._symptom_reports(ctx)
        findings.extend(report_findings)
        actions.extend(report_actions)
        status = raise_status(status, report_status)

        if not findings:
            findings.append("All animals are green. No health concerns in the last 7 days.")

        return AgentFinding(
            agent=self.name,
            status=status,
            summary=f"{red_count} red and {yellow_count} yellow animal(s), "
                    f"{len(report_findings)} symptom report(s) to review.",
            findings=findings,
            actions=actions,
        )

    def _symptom_reports(self, ctx: AgentContext) -> tuple[list[str], list[dict], str]:
        """Use the newest report per animal from the last 7 days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=REPORT_WINDOW_DAYS)
        newest: dict[int, m.SymptomReport] = {}
        for report in ctx.db.query(m.SymptomReport).order_by(m.SymptomReport.id.desc()).all():
            created = report.created_at if report.created_at.tzinfo else report.created_at.replace(tzinfo=timezone.utc)
            if created >= cutoff:
                newest.setdefault(report.animal_id, report)

        findings: list[str] = []
        actions: list[dict] = []
        status = "ok"
        for report in newest.values():
            result = json.loads(report.result_json)
            if result["priority"] == "low":
                continue
            conditions = ", ".join(c["name"] for c in result["possible_conditions"]) or "no specific condition matched"
            concerns = "; ".join(result["concerns"][:3])
            findings.append(
                f"{result['animal_label']} symptom report ({result['priority']} priority): "
                f"possible {conditions}. {concerns}".rstrip(". ") + "."
            )
            actions.extend(result["actions"])
            status = raise_status(status, PRIORITY_STATUS[result["priority"]])

        return findings, actions, status
