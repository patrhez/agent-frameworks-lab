from dataclasses import replace
from pathlib import Path

import pytest

from shared.hitl import ApprovalRequest, AutoApprover, Decision, ScriptedApprover, make_approver
from shared.runtime import ToolRuntime

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


@pytest.fixture
def approval_request():
    return ApprovalRequest("op-1", "book_flight", {"city": "Shanghai"}, "high", "booking")


@pytest.mark.parametrize("mode,status", [("auto_approve", "approved"), ("auto_reject", "rejected")])
def test_auto_modes(approval_request, mode, status):
    approver = AutoApprover(mode)
    assert approver.decide(approval_request).status == status
    assert approver.decide(replace(approval_request, risk="low")).status == "approved"


def test_scripted_reject_approve_and_exhaustion(approval_request):
    approver = ScriptedApprover(SCRIPTS / "approve_after_reject.json")
    assert [approver.decide(approval_request, n).status for n in range(3)] == ["rejected", "approved", "rejected"]
    assert approver.decide(replace(approval_request, tool_name="unknown")).status == "rejected"


def test_script_matches_operation_id(approval_request, tmp_path):
    path = tmp_path / "script.json"
    path.write_text('{"steps":[{"operation_id":"op-1","status":"approved"}]}')
    approver = ScriptedApprover(path)
    assert approver.decide(approval_request).status == "approved"
    assert approver.decide(replace(approval_request, operation_id="op-2")).status == "rejected"


def test_timeout_fails_closed(approval_request):
    result = ScriptedApprover(SCRIPTS / "timeout.json").decide(approval_request)
    assert result.status == "rejected" and "timeout" in result.reason


def test_invalid_configuration():
    with pytest.raises(ValueError):
        make_approver("scripted")
    with pytest.raises(ValueError):
        AutoApprover("invalid")
    with pytest.raises(ValueError):
        Decision("invalid", "bad status")


def test_allowlist_and_readonly_role(tmp_path):
    runtime = ToolRuntime(tmp_path, "op", "Shanghai", role="readonly")
    assert "mock" in runtime.weather("Shanghai")
    with pytest.raises(PermissionError):
        runtime.request("Shanghai")
    with pytest.raises(PermissionError):
        runtime.authorize("transfer_money")
    assert runtime.effect_count() == 0


def test_approval_payload_binding_and_local_idempotency(tmp_path):
    runtime = ToolRuntime(tmp_path, "op", "Shanghai")
    runtime.request("Shanghai")
    with pytest.raises(PermissionError):
        runtime.book("Shanghai")
    with pytest.raises(PermissionError):
        runtime.request("Beijing")
    runtime.decide(AutoApprover())
    assert runtime.book("Shanghai") == runtime.book("Shanghai")
    assert runtime.effect_count() == 1
    with pytest.raises(RuntimeError):
        runtime.reopen()


def test_persisted_script_cursor_and_rejection(tmp_path):
    runtime = ToolRuntime(tmp_path, "op", "Shanghai")
    runtime.request("Shanghai")
    runtime.decide(ScriptedApprover(SCRIPTS / "approve_after_reject.json"))
    with pytest.raises(PermissionError):
        runtime.book("Shanghai")
    restored = ToolRuntime(tmp_path, "op", "Shanghai")
    restored.reopen()
    assert restored.decide(ScriptedApprover(SCRIPTS / "approve_after_reject.json")).status == "approved"
    assert restored.attempts() == 2
