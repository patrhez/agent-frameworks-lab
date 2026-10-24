import os
import pytest

from advanced import deferred_hitl as adapter
from shared.testing.contracts import (
    check_gate, check_process_resume, check_script, check_beginner, check_live,
)

PROJECT = "pydantic_ai"


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
    from shared.testing.contracts import cli
    output = cli(PROJECT, tmp_path, "--stream")
    assert "[stream]" in output
    assert "CallToolsNode" in output if PROJECT == "pydantic_ai" else "ToolCallExecutionEvent" in output
