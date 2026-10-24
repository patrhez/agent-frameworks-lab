# OpenAI Agents SDK weather assistant

## Beginner -> advanced reading order

Read `main.py` first, then `advanced/run.py`, then `approvals_handoff.py` through the
symbols in the module map. Beginner behavior is retained; advanced is independent.

```sh
uv sync
uv run main.py                 # Beginner: provider key required
uv run python -m advanced.run --hitl auto_approve
uv run python -m advanced.run --hitl auto_reject --state-dir .local-data/rejected
uv run python -m advanced.run --hitl scripted \
  --script ../shared/scripts/approve_after_reject.json --state-dir .local-data/scripted
uv run python -m advanced.run --phase prepare --state-dir .local-data/persisted
uv run python -m advanced.run --phase resume --state-dir .local-data/persisted
uv run pytest                 # Native mock tests; live smoke skipped by default
```

All paths above are relative to this project directory. Advanced defaults to no
key and no network; it mocks the provider, not the framework loop. Choose a fresh
state directory for each experiment; a completed directory returns its terminal
result. `HITL_MODE` supplies the default (`auto_approve`), `--hitl` overrides it,
and `HITL_SCRIPT` is the fallback script path. Timeout scripts reject immediately.
No code waits for keyboard input. `--role readonly` blocks bookings; the default
traveler role still requires approval for high-risk tools.

For a paid smoke, export provider variables and run:

```sh
RUN_LIVE=1 uv run pytest tests/test_advanced.py::test_live_smoke -q
```

This sends several model requests, typically 10–120 seconds, billed by the provider;
all booking effects remain mock. `--live` also requires `RUN_LIVE=1`.

## Advanced module map

| File / symbol | Responsibility |
| --- | --- |
| `main.py` | Original weather happy path |
| `advanced/run.py` | CLI entry and access to shared modules |
| `advanced/approvals_handoff.py:build_agents` | Router/Booking handoff, guarded tools, and input/output checks |
| `advanced/approvals_handoff.py:require_approval` | Bind actual arguments before native interruption |
| `advanced/approvals_handoff.py:prepare / resume` | RunState JSON restore, approve/reject, and Runner continuation |
| `../shared/cli.py:execute` | Bounded prepare/decision/resume orchestration |
| `../shared/hitl.py` | Request/Decision and unattended approvers |
| `../shared/runtime.py:ToolRuntime` | Allowlist, payload binding, decision audit, mock effects |
| `tests/test_advanced.py` | Native integration, new-process recovery, scripts, gated live smoke |

## What advanced demonstrates

A real SDK handoff transfers Router -> Booking. The Booking tool has a native
`needs_approval` callback; Runner returns `interruptions` before its body executes.
The router reads weather before handing off. A named booking tool choice
ensures the native approval path is reached; DeepSeek thinking is disabled where
required/named tool selection is used. Prepare saves `result.to_state().to_json()`
with its SQLite session ID. Resume
reconstructs the graph with unique agent names, calls `RunState.from_json`, applies
`state.approve` or `state.reject`, then runs Runner with that native state.

A blocking input guardrail checks input length. An output guardrail requires a
mock label on final output. A file-backed `SQLiteSession` holds history separately
from RunState and the shared approval/effect database. Native RunState serialization
keeps tracing API keys excluded. Native tracing is opt-in; this adapter does not
implement streaming. See the official
[approval guide](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals).

## Advanced vs a handwritten Go harness

- Runner owns loop, handoff, and native interruption protocol; the app owns approver identity/policy.
- Sessions provide history; RunState provides pending execution state; neither proves an external effect committed.
- The shared ledger rechecks arguments/approval even after native SDK approval.
- Input/output guardrails validate boundaries; tool authorization and execution isolation remain separate concerns.

## Persistence, tracing, and isolation

Session/history files and `checkpoint.json` are separate from `approvals.sqlite`.
The latter has requests, decisions, and local mock receipt tables. Operation IDs
bind approvals to exact tool arguments. Replaying a local mock receipt is safe;
real downstream APIs need their own idempotency/reconciliation. One controller owns
a state directory; local checkpoints are trusted harness storage, not user uploads.

Structured boundary logs work offline. `LAB_TRACE=1` adds diagnostics.
`FRAMEWORK_TRACE=1` opts into supported CrewAI/SDK tracing exporters (with separate
credentials/data export); AutoGen/Pydantic have native event logs via `--stream`.
No default `OTEL_SDK_DISABLED` is set. Frameworks do not provision a VM here:
execution isolation belongs to the harness/sandbox layer. MCP is intentionally omitted.

The beginner reference below is retained as the original first lesson.

## Five-line concept map

1. **Agent** holds instructions, model, tools, and attached input guardrails.
2. **Runner** executes the model/tool loop: `await Runner.run(...)`.
3. **Function tool** wraps `get_weather` with `@function_tool`.
4. **Session** maintains conversation history: `SQLiteSession` passed into Runner.
5. **Guardrail** checks input before the model: `short_input`, attached to the Agent.

## Run

Configure `../.env` using the [root README](../README.md), then:

```sh
uv sync
uv run main.py
uv run main.py "What is the weather in Beijing?"
```

Initial installation: `uv add openai-agents python-dotenv`. The package name is
`openai-agents`, but Python imports come from `agents`.

## What this demonstrates

Runner routes the model's function call to the mock tool and requests the final
English reply. The four standard log markers expose this flow. The application
fails if no weather tool call occurred. `max_turns=6` bounds model turns.

`@input_guardrail(run_in_parallel=False)` makes the length check block before
model execution. Inputs must contain 1–500 characters after trimming. The check
is attached at `input_guardrails=[short_input]`; a tripwire raises an SDK exception.
This is a small validation example, not weather-topic detection or a tool permission policy.

`SQLiteSession("weather-lab", ":memory:")` is the default minimal session. To keep
conversation history across process restarts, use the same session ID and file:

```sh
SESSION_DB=weather.db uv run main.py "What is the weather in Shanghai?"
SESSION_DB=weather.db uv run main.py "What is the weather in Beijing?"
```

Database files are ignored by Git. Session history is distinct from a checkpoint
that can resume an interrupted tool execution. SDK tracing is disabled in this demo.

## Compared with a handwritten while-loop

- Runner owns repeated model calls and function dispatch until final output.
- Session loads and saves conversation messages; you select storage and identity.
- Guardrails provide attachment points; you still define policies and human approvals.

## Handoff sketch

A handoff transfers control to another agent, including its instructions and tools.
This sketch is not part of the executed single-agent demo:

```python
specialist = Agent(name="Weather", tools=[get_weather])
router = Agent(name="Router", handoffs=[specialist])
# The model can choose the handoff tool to transfer control.
result = await Runner.run(router, "What is the weather in Shanghai?")
print(result.final_output)
```

## Versions and official references

Installed with `uv pip freeze`:

```text
openai-agents==0.24.0
openai==3.37.0
python-dotenv==1.2.4
```

Live verification passed on 2026-10-24 using the configured DeepSeek model,
`deepseek-flash`. `OpenAIChatCompletionsModel` uses `AsyncOpenAI` with the mapped
DeepSeek endpoint/key instead of requiring the OpenAI Responses API.
Offline checks also confirmed oversized-input rejection before a model call and
SQLite history across two runs. With sessions, guardrails receive message items;
the implementation extracts the latest user message before checking its length.
See the official [quickstart](https://developers.openai.com/api/docs/guides/agents/quickstart),
[running agents](https://developers.openai.com/api/docs/guides/agents/running-agents),
and [guardrails guide](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals).
