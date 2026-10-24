# CrewAI weather crew

## Injecting mock dependencies: Tool model fields

`tools_injected.py` defines `WeatherTool(BaseTool)` and `BookingTool(BaseTool)`.
Each instance receives `deps: AppDeps` through its constructor/model field, marked
`Field(exclude=True)` so service objects are not serialized. `_run` reads `self.deps`;
weather delegates to the injected `weather.get(city)` mock.

Shared `AppDeps.runtime` uses the concrete `ToolRuntime | None` type rather than
`Any`, so type checkers can validate weather and approval method calls.
`for_runtime(runtime: ToolRuntime) -> AppDeps` binds the services, and
`require_runtime() -> ToolRuntime` checks and narrows the optional runtime.
Postponed annotations and a delayed default-client import in `ToolRuntime` avoid
the circular import while keeping `AppDeps` annotations resolvable at runtime.
This applies to both beginner dependencies and advanced HITL context.

```python
deps = AppDeps(weather=WeatherClient(cache={"Beijing": "Injected weather (mock)."}))
weather_tool = WeatherTool(deps=deps)
# Register the instance on Agent(tools=[weather_tool], ...).
```

The beginner researcher and advanced crew use these Tool instances, not closures.
The advanced dependency carries ToolRuntime and preserves its pre-effect approval
check. `tool_plain` belongs to Pydantic AI; this framework expresses injection through
Tool fields instead. `[deps.weather]` records service use. Weather/cache methods
are pure in-memory mocks; tools never create HTTP clients.


## Beginner -> advanced reading order

Read `main.py` first, then `advanced/run.py`, then `hitl_crew.py` through the
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
| `main.py` | Weather crew with injected Tool instances |
| `tools_injected.py` | BaseTool fields hold deps; _run uses mock services |
| `advanced/run.py` | CLI entry and access to shared modules |
| `advanced/hitl_crew.py:execute_crew` | Create the actual Crew and register guarded tools |
| `advanced/hitl_crew.py:ScriptLLM` | Offline ReAct model only; Crew dispatch remains real |
| `advanced/hitl_crew.py:prepare / resume` | Save work item, then recreate task from saved output |
| `../shared/cli.py:execute` | Bounded prepare/decision/resume orchestration |
| `../shared/dependencies.py` | Per-run mock weather/cache services and AppDeps |
| `../shared/providers.py` | Environment/.env/literal ~/.zshrc provider loading |
| `../shared/hitl.py` | Request/Decision and unattended approvers |
| `../shared/runtime.py:ToolRuntime` | Allowlist, payload binding, decision audit, mock effects |
| `tests/test_advanced.py` | Native integration, new-process recovery, scripts, gated live smoke |

## What advanced demonstrates

The actual Crew tool calls pass through `runtime.guarded_book` before any
booking body runs. Pending/rejected calls return a blocked result. Resume creates
a new Crew task using a saved task outcome; this is an application work-item
checkpoint, not native mid-loop stack serialization.

`human_input=True` reviews task output; it is intentionally not used because this
lab needs pre-tool approval without a human prompt. CrewAI Flow/hierarchical
orchestration is not implemented in advanced; compare the official
[Flows](https://docs.crewai.com/en/concepts/flows) and
[human input](https://docs.crewai.com/en/learn/human-input-on-execution) guides.
Other adapters supply the three implemented orchestration examples.

## Advanced vs a handwritten Go harness

- Crew owns model/tool iterations; the app owns approval and task-boundary replay.
- The wrapped function is the permission boundary; role text is only a prompt.
- `crew-session.json` is task context; `checkpoint.json` is a work item; `approvals.sqlite` records policy/effects.
- A local mock receipt deduplicates by operation ID; real effects need downstream idempotency.

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

1. **Agent** holds a role, goal, model, and tools: `researcher` and `writer` in `main.py`.
2. **Task** describes work and its expected output: `research` and `write`.
3. **Crew** coordinates those agents and tasks: the `Crew(...).kickoff()` block.
4. **Process** selects scheduling: `Process.sequential` runs research before writing.
5. **Tool** is a `WeatherTool(deps=deps)` instance on the researcher.

## Run

Configure `../.env` as described in the [root README](../README.md), then:

```sh
uv sync
uv run main.py
uv run main.py "What is the weather in Beijing?"
```

Initial setup used `uv init --bare --name lab-crewai --python 3.11` and
`uv add crewai python-dotenv`. The committed lockfile captures the resolved environment.

## What this demonstrates

The researcher must call the mock tool. The writer receives the research task's
output through `context=[research]` and writes the natural-language answer.
The code comments explicitly mark **Agent**, **Task**, and **Crew** definitions.
Look for `[user]`, `[tool.call]`, `[tool.return]`, and `[final]` in stdout.
The run raises if research never actually executes the tool.

## Compared with a handwritten while-loop

- Crew owns model/tool iterations; Task and Process also own inter-agent scheduling.
- Task context carries the research result to the writer; no manual message handoff.
- Roles and expected outputs guide the model; they do not enforce OS permissions.

Memory and tool caching are disabled; this example does not implement HITL.
`max_iter=4` bounds each agent's reasoning iterations; sequential task completion
ends the crew. Local framework storage, if needed, goes under ignored `.local-data/`.

## Versions and official references

Installed with `uv pip freeze`:

```text
crewai==1.15.30
crewai-core==1.15.30
crewai-cli==1.15.30
openai==2.54.0
pydantic==2.12.5
python-dotenv==1.2.4
```

Live verification passed on 2026-10-24 using the configured DeepSeek model,
`deepseek-flash`. The native OpenAI adapter receives the configured base URL;
LiteLLM is unnecessary for this example. Approximate-token-count warnings for
this custom model are expected and do not prevent task completion.
CrewAI may initialize its own per-user credential directory on import, even with
tracing disabled; `CREWAI_STORAGE_DIR` only redirects its workflow storage.

Based on the official [quickstart](https://docs.crewai.com/en/quickstart) and
[custom tool guide](https://docs.crewai.com/en/learn/create-custom-tools).
This small inline example uses the same Agent/Task/Crew API without YAML scaffolding.
