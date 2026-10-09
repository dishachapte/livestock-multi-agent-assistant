"""Finance Agent: estimates the cost of each proposed action so the farmer can prioritise."""
from backend.agents.base import AgentContext, AgentFinding

VET_VISIT_COST_INR = 800.0  # demo assumption, not a real price


class FinanceAgent:
    name = "Finance Agent"

    def run(self, ctx: AgentContext, actions: list[dict]) -> AgentFinding:
        total = 0.0
        for action in actions:
            p = action["parameters"]
            if action["action_type"] == "reorder_feed":
                cost = p["quantity_kg"] * p["unit_cost_inr"]
            elif action["action_type"] == "book_vet":
                cost = VET_VISIT_COST_INR
            else:
                cost = 0.0  # monitoring costs nothing extra
            p["estimated_cost_inr"] = round(cost, 2)
            total += cost

        if not actions:
            return AgentFinding(self.name, "ok", "No spending proposed.",
                                ["No spending is proposed for this question."])

        high = [a for a in actions if a["priority"] == "high"]
        findings = [f"Estimated total for proposed actions: INR {total:,.0f}."]
        if high:
            findings.append(f"{len(high)} high-priority action(s) should be approved first.")
        return AgentFinding(
            agent=self.name,
            status="attention" if total > 0 else "ok",
            summary=f"Estimated INR {total:,.0f} across {len(actions)} action(s).",
            findings=findings,
        )
