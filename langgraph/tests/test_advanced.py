import asyncio
import os

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from advanced import hitl_graph as adapter
from shared.runtime import ToolRuntime
from shared.storage import read_json
from shared.testing.contracts import (
    check_gate, check_process_resume, check_script, check_beginner, check_live, cli,
)

PROJECT = "langgraph"


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


def test_native_event_stream(tmp_path):
    output = cli(PROJECT, tmp_path, "--stream")
    assert '["__interrupt__"]' in output
    assert '["execute"]' in output
    assert '["reviewer"]' in output


def test_native_checkpoint_cannot_bypass_policy(tmp_path):
    runtime = ToolRuntime(tmp_path, "op", "Shanghai")
    asyncio.run(adapter.prepare(runtime))
    saved = read_json(tmp_path / "checkpoint.json")
    config = {"configurable": {"thread_id": saved["thread_id"]}}
    with SqliteSaver.from_conn_string(str(tmp_path / "graph.sqlite")) as saver:
        graph = adapter.build_graph(runtime, saver)
        state = graph.get_state(config)
        assert state.next == ("approval",)
        assert any(task.interrupts for task in state.tasks)
        assert state.values["messages"][-1].tool_calls[0]["name"] == "book_flight"
        # A forged native resume payload is insufficient without a ledger decision.
        with pytest.raises(PermissionError, match="persisted policy"):
            graph.invoke(Command(resume={"approved": True}), config=config)
    assert runtime.status() == "pending"
    assert runtime.effect_count() == 0
    assert (tmp_path / "graph.sqlite").exists()
    assert (tmp_path / "approvals.sqlite").exists()
    assert (tmp_path / "session.json").exists()
