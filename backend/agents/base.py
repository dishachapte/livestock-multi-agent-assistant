"""Shared types for all agents: the context they receive and the finding they return."""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

STATUS_RANK = {"ok": 0, "attention": 1, "critical": 2}


@dataclass
class AgentContext:
    db: Session
    herd: list[dict]
    today: date
    memory: list[dict] = field(default_factory=list)


@dataclass
class AgentFinding:
    agent: str
    status: str  # ok / attention / critical
    summary: str
    findings: list[str]
    actions: list[dict] = field(default_factory=list)


def raise_status(current: str, new: str) -> str:
    return new if STATUS_RANK[new] > STATUS_RANK[current] else current


def make_action(action_type: str, target: str, label: str, priority: str,
                reason: str, params: dict | None = None) -> dict:
    """One proposed action from one agent. The Manager merges duplicates later."""
    return {
        "action_type": action_type,
        "priority": priority,
        "reason": reason,
        "parameters": {"target": target, "label": label, **(params or {})},
    }
