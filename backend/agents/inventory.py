"""Inventory Agent: finds feed below its reorder level and proposes a top-up order."""
from backend import models as m
from backend.agents.base import AgentContext, AgentFinding, make_action, raise_status


class InventoryAgent:
    name = "Inventory Agent"

    def run(self, ctx: AgentContext) -> AgentFinding:
        items = ctx.db.query(m.FeedItem).order_by(m.FeedItem.name).all()
        low = [i for i in items if i.quantity_kg < i.reorder_level_kg]

        status = "ok"
        findings: list[str] = []
        actions: list[dict] = []

        for item in low:
            critical = item.quantity_kg < item.reorder_level_kg * 0.5
            status = raise_status(status, "critical" if critical else "attention")
            # Order enough to bring stock to twice the reorder level
            order_kg = round(item.reorder_level_kg * 2 - item.quantity_kg)
            reason = (f"Stock is {item.quantity_kg:.0f} kg, below the reorder level of "
                      f"{item.reorder_level_kg:.0f} kg.")
            findings.append(f"{item.name}: {reason} Suggested order {order_kg} kg.")
            actions.append(make_action(
                "reorder_feed", f"feed:{item.id}", item.name,
                "high" if critical else "medium", reason,
                {"feed_item_id": item.id, "quantity_kg": float(order_kg),
                 "unit_cost_inr": item.unit_cost_inr},
            ))

        if not low:
            findings.append("All feed items are above their reorder level.")

        return AgentFinding(
            agent=self.name,
            status=status,
            summary=f"{len(low)} feed item(s) below reorder level.",
            findings=findings,
            actions=actions,
        )
