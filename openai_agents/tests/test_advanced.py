import os
import pytest

from advanced import approvals_handoff as adapter
from shared.testing.contracts import (
    check_gate, check_process_resume, check_script, check_beginner, check_live,
)

PROJECT = "openai_agents"


@pytest.mark.parametrize("mode", ["auto_approve", "auto_reject"])
def test_pretool_approval(tmp_path, monkeypatch, mode):
    check_gate(adapter, tmp_path, monkeypatch, mode)


def test_interrupt_and_resume_in_new_process(tmp_path):
    check_process_resume(PROJECT, tmp_path)


@pytest.mark.parametrize("script,expected", [
    ("approve_after_reject.json", 1), ("timeout.json", 0), ("reject.json", 0),
])
def test_scripted_decisions(tmp_path, script, expected):
    check_script(PROJECT, tmp_path, script, expected)


def test_beginner_import():
    check_beginner(PROJECT)


@pytest.mark.skipif(os.getenv("RUN_LIVE") != "1", reason="Set RUN_LIVE=1 to spend provider tokens")
def test_live_smoke(tmp_path):
    check_live(PROJECT, tmp_path)


def test_input_guardrail_blocks_before_model(tmp_path, monkeypatch):
    import asyncio
    from agents import InputGuardrailTripwireTriggered, Runner
    from shared.runtime import ToolRuntime
    runtime = ToolRuntime(tmp_path, "op", "Shanghai")

    async def forbidden(*args, **kwargs):
        raise AssertionError("Model must not run after blocking input guardrail")
    monkeypatch.setattr(adapter.ScriptModel, "get_response", forbidden)
    with pytest.raises(InputGuardrailTripwireTriggered):
        asyncio.run(Runner.run(adapter.build_agents(runtime), "x" * 1001))
    assert runtime.effect_count() == 0


def test_output_guardrail_rejects_unlabeled_booking(tmp_path, monkeypatch):
    import asyncio
    from agents import OutputGuardrailTripwireTriggered, Runner, ModelResponse, Usage
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText
    from shared.runtime import ToolRuntime
    runtime = ToolRuntime(tmp_path, "op", "Shanghai")

    async def unlabeled(*args, **kwargs):
        return ModelResponse(output=[ResponseOutputMessage(
            id="bad-final", type="message", role="assistant", status="completed",
            content=[ResponseOutputText(type="output_text", text="Booked.", annotations=[])],
        )], usage=Usage(), response_id=None)
    monkeypatch.setattr(adapter.ScriptModel, "get_response", unlabeled)
    booking = adapter.build_agents(runtime).handoffs[0]
    with pytest.raises(OutputGuardrailTripwireTriggered):
        asyncio.run(Runner.run(booking, "Explain this booking"))
    assert runtime.effect_count() == 0
