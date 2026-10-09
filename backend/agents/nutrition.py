"""Nutrition Agent: checks feed quality grades and whether feeding is logged when milk drops."""
from datetime import timedelta

from backend import models as m
from backend.agents.base import AgentContext, AgentFinding, raise_status


class NutritionAgent:
    name = "Nutrition Agent"

    def run(self, ctx: AgentContext) -> AgentFinding:
        db = ctx.db
        status = "ok"
        findings: list[str] = []

        for item in db.query(m.FeedItem).order_by(m.FeedItem.name).all():
            if item.quality_grade != "A":
                status = raise_status(status, "attention")
                findings.append(f"{item.name} is grade {item.quality_grade}. Check quality before feeding large amounts.")

        milk_drop = [a for a in ctx.herd
                     if any("Milk down" in e for e in a["health_indicator"]["explanations"])]
        for animal in milk_drop:
            label = f"{animal['name']} ({animal['tag_id']})"
            status = raise_status(status, "attention")
            since = ctx.today - timedelta(days=14)
            logged = (
                db.query(m.FeedingRecord)
                .filter(m.FeedingRecord.animal_id == animal["id"],
                        m.FeedingRecord.recorded_on >= since)
                .all()
            )
            if not logged:
                findings.append(
                    f"{label}: milk has dropped but no feeding is logged in the last 14 days. "
                    "Log recent feed changes so the cause can be checked."
                )
            else:
                feeds = sorted({r.feed_name for r in logged})
                findings.append(f"{label}: milk has dropped. Recent feeds logged: {', '.join(feeds)}.")

        if not findings:
            findings.append("Feed quality grades are good and no milk drops need a feed check.")

        return AgentFinding(
            agent=self.name,
            status=status,
            summary=f"{len(milk_drop)} animal(s) with a milk drop to check against feeding.",
            findings=findings,
        )
