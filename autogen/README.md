# AutoGen AgentChat weather assistant

## Beginner -> advanced reading order

Read `main.py` first, then `advanced/run.py`, then `hitl_team.py` through the
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
| `advanced/hitl_team.py:build_team` | Executor/reviewer, tool wrappers, and explicit termination |
| `advanced/hitl_team.py:drive` | Consume native Team event stream |
| `advanced/hitl_team.py:prepare / resume` | Native Team state save/load and automated feedback |
| `../shared/cli.py:execute` | Bounded prepare/decision/resume orchestration |
| `../shared/hitl.py` | Request/Decision and unattended approvers |
| `../shared/runtime.py:ToolRuntime` | Allowlist, payload binding, decision audit, mock effects |
| `tests/test_advanced.py` | Native integration, new-process recovery, scripts, gated live smoke |

## What advanced demonstrates

A real `RoundRobinGroupChat` coordinates executor and reviewer. Explicit
termination combines executor-scoped `PENDING_APPROVAL`, a reviewer-content/ledger
`FunctionalTermination`, and `MaxMessageTermination(8)`. Quoted markers in user
feedback or model reasoning cannot prematurely complete the resumed task.
The executor's tool wrapper returns pending before effects; the simulator decides
outside the Team; resume restores `team.save_state()` with `team.load_state()`
and sends automated feedback. No interactive `UserProxyAgent` is used.

`--stream` prints native `run_stream` tool/message/TaskResult events, not fabricated
token output. See the official
[state tutorial](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/state.html).
Team state is saved at a message boundary, not while a tool frame is suspended.

## Advanced vs a handwritten Go harness

- Team owns participant scheduling and message history; the app owns policy decisions.
- A registered tool is available, not automatically authorized; the wrapper checks first.
- Team JSON restores context/manager state; approval/effect tables remain independent.
- Human feedback is simulated at a stopped Team boundary; production approval delivery is still app work.

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

1. **AssistantAgent** owns the assistant's conversation and tool-use behavior.
2. **Model client** adapts a provider: `OpenAIChatCompletionClient` in `main()`.
3. **Tool** is the typed async function `get_weather` passed to `tools=[...]`.
4. **TaskResult** is returned by `agent.run(task=message)` and contains messages.
5. **Team** coordinates multiple agents; this single-agent example does not use one.

## Run

Configure `../.env` using the [root README](../README.md), then:

```sh
uv sync
uv run main.py
uv run main.py "What is the weather in Beijing?"
```

Initial installation: `uv add "autogen-agentchat" "autogen-ext[openai]" python-dotenv`.
These are AgentChat packages, not legacy `pyautogen`. The official quickstart
also includes an `azure` extra; it is unnecessary for this OpenAI-only example.

## What this demonstrates and how it stops

`AssistantAgent(..., tools=[get_weather], reflect_on_tool_use=True)` lets the
model request weather and then write a natural-language response based on the
tool result. The four standard log markers show input, arguments, result, and answer.
The application raises if the model never calls the weather tool.

**Termination is in `agent.run(...)`:** a plain text response ends the tool loop;
`max_tool_iterations=2` bounds tool rounds, with final reflection enabled. No Team
is used, so no Team termination condition or magic `TERMINATE` token is needed.
The model client closes in `finally`.

## Compared with a handwritten while-loop

- AssistantAgent manages message history, tool dispatch, and final reflection.
- The model client abstracts the provider protocol; messages arrive in TaskResult.
- A Team would add coordination and explicit termination rules; it is omitted here.

History stays in the agent for its lifetime. For a later persistence experiment,
inspect `await agent.save_state()` and `await agent.load_state(state)`; this demo
does not save state or add human approval.

## Versions and official references

Installed with `uv pip freeze`:

```text
autogen-agentchat==0.7.5
autogen-core==0.7.5
autogen-ext==0.7.5
openai==3.37.0
python-dotenv==1.2.4
```

Live verification passed on 2026-10-24 using the configured DeepSeek model,
`deepseek-flash`. The OpenAI client receives its base URL from the mapped
DeepSeek settings. Explicit `model_info` declares text/tool capabilities without
relying on AutoGen's registry of OpenAI model names.
See the official [AgentChat quickstart](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/quickstart.html)
and [state tutorial](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/state.html).
