"""Breeding Agent: finds heat checks and pregnancy checks that are overdue."""
from backend import models as m
from backend.agents.base import AgentContext, AgentFinding, make_action, raise_status

HEAT_CYCLE_DAYS = 21
PREGNANCY_CHECK_DAYS = 60


class BreedingAgent:
    name = "Breeding Agent"

    def run(self, ctx: AgentContext) -> AgentFinding:
        status = "ok"
        findings: list[str] = []
        actions: list[dict] = []

        females = ctx.db.query(m.Animal).filter(m.Animal.sex == "female").all()
        for animal in females:
            events = sorted(animal.breeding_records, key=lambda r: r.event_date)
            if not events:
                continue
            last = events[-1]
            days = (ctx.today - last.event_date).days
            label = f"{animal.name} ({animal.tag_id})"
            target = f"animal:{animal.tag_id}"

            if last.event_type == "heat_observed" and days >= HEAT_CYCLE_DAYS:
                status = raise_status(status, "attention")
                reason = (f"Last heat seen {days} days ago on {last.event_date}, "
                          "with no insemination logged since. Heat check or breeding review is due.")
                findings.append(f"{label}: {reason}")
                actions.append(make_action("flag_animal", target, label, "medium", reason,
                                           {"animal_id": animal.id}))

            elif last.event_type == "insemination" and days >= PREGNANCY_CHECK_DAYS:
                status = raise_status(status, "attention")
                reason = (f"Insemination was {days} days ago on {last.event_date}. "
                          "No pregnancy check is logged. A pregnancy check is due.")
                findings.append(f"{label}: {reason}")
                actions.append(make_action("flag_animal", target, label, "medium", reason,
                                           {"animal_id": animal.id}))

        if not findings:
            findings.append("No breeding alerts. Heat and pregnancy records are up to date.")

        return AgentFinding(
            agent=self.name,
            status=status,
            summary=f"{len(actions)} breeding alert(s).",
            findings=findings,
            actions=actions,
        )
