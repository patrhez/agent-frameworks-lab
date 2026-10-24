# Pydantic AI weather assistant

## Injecting mock dependencies: why not tool_plain?

`shared.dependencies.AppDeps` contains a per-run `WeatherClient` with an in-memory
cache. `build_agent` declares `deps_type=AppDeps`; `@agent.tool` receives
`ctx: RunContext[AppDeps]`, then `ctx.deps.read_weather(city)` calls the injected
`deps.weather.get(city)`. The run passes `deps=AppDeps(...)` explicitly.
`tool_plain` is for tools without a RunContext, so it cannot express this injection.

Shared `AppDeps.runtime` uses the concrete `ToolRuntime | None` type rather than
`Any`, so type checkers can validate weather and approval method calls.
`for_runtime(runtime: ToolRuntime) -> AppDeps` binds the services, and
`require_runtime() -> ToolRuntime` checks and narrows the optional runtime.
Postponed annotations and a delayed default-client import in `ToolRuntime` avoid
the circular import while keeping `AppDeps` annotations resolvable at runtime.
This applies to both beginner dependencies and advanced HITL context.

```python
deps = AppDeps(weather=WeatherClient(cache={"Beijing": "Injected weather (mock)."}))
agent = build_agent(model)
result = agent.run_sync("Beijing weather?", deps=deps)
```

The advanced deferred path keeps `RunContext[ToolRuntime]`; ToolRuntime now accepts
an injected `weather` client and delegates to its `.get`. Native deferred approvals
remain in place. `[deps.weather]` proves service use. No tool dependency issues HTTP;
unit models are fake and default in-process tests block TCP connections.


## Beginner -> advanced reading order

Read `main.py` first, then `advanced/run.py`, then `deferred_hitl.py` through the
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

Beginner and gated live runs also read literal DeepSeek settings from `~/.zshrc`
when no provider key is set in the environment/root `.env`; no manual export is
needed for those assignments. Shell scripts are never executed. For a paid smoke:

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
| `advanced/deferred_hitl.py:build_agent` | Typed tools, injected runtime, and approval requirement |
| `advanced/deferred_hitl.py:prepare` | Capture DeferredToolRequests, messages, and call ID |
| `advanced/deferred_hitl.py:resume` | Feed DeferredToolResults through native graph |
| `../shared/cli.py:execute` | Bounded prepare/decision/resume orchestration |
| `../shared/dependencies.py` | Per-run mock weather/cache services and AppDeps |
| `../shared/providers.py` | Environment/.env/literal ~/.zshrc provider loading |
| `../shared/hitl.py` | Request/Decision and unattended approvers |
| `../shared/runtime.py:ToolRuntime` | Allowlist, payload binding, decision audit, mock effects |
| `tests/test_advanced.py` | Native integration, new-process recovery, scripts, gated live smoke |

## What advanced demonstrates

`@agent.tool(requires_approval=True)` returns native `DeferredToolRequests`
before running `book_flight`. Prepare saves typed message history and the pending
call ID. Resume passes `DeferredToolResults(approvals={id: bool})` through the real
agent graph. `output_type=[TravelAnswer, DeferredToolRequests]` retains a typed final
answer. `RunContext[ToolRuntime]` injects the policy/effect boundary; an Approver
could also be placed in a dependency object, while this CLI deliberately decides
outside the suspended graph so approvals can survive process exit.

`--stream` prints native graph-node events via `agent.iter`, not token deltas.
See [deferred tools](https://ai.pydantic.dev/deferred-tools/). Strict server schemas
are disabled for compatible providers; local Pydantic output validation remains.
DeepSeek thinking is disabled for its required/named output-tool selection.

## Advanced vs a handwritten Go harness

- The Agent graph owns tool dispatch and output-validation retries; schemas replace manual JSON parsing.
- Native deferred requests save approval protocol plumbing; the app still routes/stores decisions.
- DI supplies services/policy to tools; a typed field is not an authorization rule.
- Message history and deferred IDs are separate from committed mock effects and downstream idempotency.

## Persistence, tracing, and isolation

Session/history files and `checkpoint.json` are separate from `approvals.sqlite`.
The latter has requests, decisions, and local mock receipt tables. Operation IDs
bind approvals to exact tool arguments. Replaying a local mock receipt is safe;
real downstream APIs need their own idempotency/reconciliation. One controller owns
a state directory; local checkpoints are trusted harness storage, not user uploads.

Structured boundary logs work offline. `LAB_TRACE=1` adds diagnostics.
`FRAMEWORK_TRACE=1` opts into supported CrewAI/SDK tracing exporters (with separate
credentials/data export); LangGraph/Pydantic have native event logs via `--stream`.
No default `OTEL_SDK_DISABLED` is set. Frameworks do not provision a VM here:
execution isolation belongs to the harness/sandbox layer. MCP is intentionally omitted.

The beginner reference below is retained as the original first lesson.

## Five-line concept map

1. **Agent** binds the model, instructions, function tools, and final output type.
2. **Function tool** uses `@agent.tool` and `RunContext[AppDeps]` for injected services.
3. **Output model** is `WeatherAnswer(BaseModel)`, validated before a result is returned.
4. **AgentRunResult** exposes that typed object as `result.output`.
5. **UsageLimits** bounds model requests, including validation retries, to six.

## Run

Configure `../.env` using the [root README](../README.md), then:

```sh
uv sync
uv run main.py
uv run main.py "What is the weather in Beijing?"
```

Initial installation: `uv add pydantic-ai python-dotenv`.

## What this demonstrates

The tool returns a string and the final answer is structured. The program prints
the standard four markers plus `[structured]` containing city, answer, and is_mock.
It rejects a run that skipped the weather tool or failed to identify mock data.

**Pydantic models are tool/output contracts:** in `main.py`, the
`class WeatherAnswer` block defines the final answer's fields; the
`output_type=WeatherAnswer` declaration attaches the contract to the agent. The
`@agent.tool` / `def get_weather(ctx: RunContext[AppDeps], city: str) -> str` definitions generate the
tool argument schema from annotations. `Field(min_length=1)` rejects empty city
or answer fields. The plain string tool result is distinct from the validated
final Pydantic output; annotations are not a business authorization policy.
This demonstrates both structured output and per-run dependency injection.

## Compared with a handwritten while-loop

- Agent owns model requests, tool execution, and output-validation retries.
- Python annotations generate the tool argument contract; BaseModel validates final fields.
- You consume `result.output.answer` instead of manually parsing final JSON.

The installed API uses `output_type`, not the older `result_type` spelling.
`@agent.tool` with `RunContext[AppDeps]` supplies dependencies; `tool_plain` would
be appropriate only for a tool with no injected context.
History is available through `result.all_messages()`; this demo does not persist it.

## Versions and official references

Installed with `uv pip freeze`:

```text
pydantic-ai==2.61.0
pydantic-ai-slim==2.61.0
pydantic==2.14.1
openai==3.37.0
python-dotenv==1.2.4
```

Live verification passed on 2026-10-24 using the configured DeepSeek model,
`deepseek-flash`. This demo uses `OpenAIChatModel` with an explicit provider and
base URL. Strict server tool schemas are disabled; local Pydantic validation remains.
DeepSeek initially returned HTTP 400 because thinking mode rejects required/named
tool choice. The DeepSeek-only `thinking.type=disabled` setting fixes that path,
as documented in its [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/).
See the official [overview](https://ai.pydantic.dev/),
[function tools](https://ai.pydantic.dev/tools/), and
[structured output](https://ai.pydantic.dev/output/) guides.
