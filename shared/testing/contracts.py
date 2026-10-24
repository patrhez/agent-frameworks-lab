"""Assertions exercise real framework dispatch; only the model provider is mocked."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from shared.hitl import AutoApprover
from shared.runtime import ToolRuntime

ROOT = Path(__file__).resolve().parents[2]


def check_gate(adapter, tmp_path, monkeypatch, mode):
    runtime = ToolRuntime(tmp_path, "test-operation", "Shanghai")
    effects = []

    def mock_effect(city, operation_id):
        assert runtime.status() == "approved", "High-risk tool reached its body before approval"
        effects.append(operation_id)
        return f"MOCK booking to {city}; operation_id={operation_id}"

    monkeypatch.setattr("shared.runtime.book_flight", mock_effect)
    asyncio.run(adapter.prepare(runtime))
    assert runtime.status() == "pending"
    assert runtime.effect_count() == 0 and effects == []
    assert (tmp_path / "checkpoint.json").exists()
    runtime.decide(AutoApprover(mode))
    asyncio.run(adapter.resume(runtime))
    expected = 1 if mode == "auto_approve" else 0
    assert len(effects) == runtime.effect_count() == expected
    if expected:
        # Replay of a local mock receipt cannot execute the effect body twice.
        runtime.book("Shanghai")
        assert len(effects) == 1


def cli(project, directory, *args, live=False):
    env = os.environ.copy()
    env["PYDANTIC_AI_NO_BANNER"] = "1"
    if not live:
        # Prove the deterministic integration does not need a provider key.
        for name in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "RUN_LIVE"):
            env.pop(name, None)
    result = subprocess.run([sys.executable, "-m", "advanced.run", "--state-dir", str(directory), *args],
                            cwd=ROOT / project, env=env, text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def effects(directory):
    with sqlite3.connect(directory / "approvals.sqlite") as db:
        return db.execute("SELECT count(*) FROM effects").fetchone()[0]


def check_process_resume(project, tmp_path):
    output = cli(project, tmp_path, "--phase", "prepare")
    assert "[checkpoint]" in output
    assert effects(tmp_path) == 0
    # A distinct child process reconstructs runtime and framework state from files.
    cli(project, tmp_path, "--phase", "resume")
    assert effects(tmp_path) == 1
    replay = cli(project, tmp_path, "--phase", "resume")
    assert '"replay": true' in replay
    assert effects(tmp_path) == 1


def check_script(project, tmp_path, filename, expected):
    cli(project, tmp_path, "--hitl", "scripted", "--script", str(ROOT / "shared/scripts" / filename))
    assert effects(tmp_path) == expected
    with sqlite3.connect(tmp_path / "approvals.sqlite") as db:
        statuses = [r[0] for r in db.execute("SELECT status FROM decisions ORDER BY id")]
    assert statuses == (["rejected", "approved"] if expected else ["rejected"])


def check_beginner(project):
    path = ROOT / project / "main.py"
    spec = importlib.util.spec_from_file_location("beginner_weather", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)


def check_live(project, tmp_path):
    cli(project, tmp_path, "--live", live=True)
    assert effects(tmp_path) == 1
    assert json.loads((tmp_path / "completed.json").read_text())["status"] == "approved"
