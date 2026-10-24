"""Unattended approvers. Script timeouts deny immediately; no interactive input."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ApprovalRequest:
    operation_id: str
    tool_name: str
    arguments: dict
    risk: Literal["low", "high"]
    agent_id: str


@dataclass(frozen=True)
class Decision:
    status: Literal["approved", "rejected"]
    reason: str

    def __post_init__(self):
        if self.status not in ("approved", "rejected"):
            raise ValueError("Invalid decision status")


class AutoApprover:
    def __init__(self, mode: str = "auto_approve"):
        if mode not in ("auto_approve", "auto_reject"):
            raise ValueError("Invalid automatic approval mode")
        self.mode = mode

    def decide(self, request: ApprovalRequest, attempt: int = 0) -> Decision:
        approved = request.risk == "low" or self.mode == "auto_approve"
        return Decision("approved" if approved else "rejected", self.mode)


class ScriptedApprover:
    """Match by operation ID/tool; attempt is persisted in the approval ledger."""
    def __init__(self, path: str | Path):
        self.steps = json.loads(Path(path).read_text())["steps"]
        if not isinstance(self.steps, list):
            raise ValueError("steps must be a list")
        for step in self.steps:
            if step.get("status") not in ("approved", "rejected", "timeout"):
                raise ValueError("Invalid script decision")

    def matching(self, request: ApprovalRequest) -> list[dict]:
        return [step for step in self.steps
                if step.get("operation_id", "*") in ("*", request.operation_id)
                and step.get("tool_name", "*") in ("*", request.tool_name)]

    def decide(self, request: ApprovalRequest, attempt: int = 0) -> Decision:
        if request.risk == "low":
            return Decision("approved", "Low-risk allowlist")
        matches = self.matching(request)
        if attempt >= len(matches):
            return Decision("rejected", "Script exhausted or no matching decision")
        step = matches[attempt]
        if step["status"] == "timeout":
            return Decision("rejected", "Simulated approval timeout (fail closed)")
        return Decision(step["status"], step.get("reason", "Scripted decision"))

    def has_next(self, request: ApprovalRequest, attempt: int) -> bool:
        return attempt < len(self.matching(request))


def make_approver(mode: str, script: str | None = None):
    if mode == "scripted":
        if not script:
            raise ValueError("scripted mode requires --script / HITL_SCRIPT")
        return ScriptedApprover(script)
    return AutoApprover(mode)
