# Advanced harness changelog

## Latest increment: tools use injected mock deps

- Added shared AppDeps and an in-memory WeatherClient/cache with `[deps.weather]` logs.
- Pydantic AI beginner uses deps_type, @agent.tool, RunContext, and explicit run deps.
- SDK beginner/advanced tools and approval callback use RunContextWrapper context;
  persisted RunState stores operation metadata and restores fresh service instances.
- LangChain keeps create_agent, adding context_schema and native ToolRuntime injection.
  Advanced graph tools/nodes use native context while preserving interrupt/Command recovery.
- CrewAI beginner/advanced tools use BaseTool fields with injected dependencies,
  excluded from serialization; no tool captures a runtime/client in a closure.
- Existing Pydantic deferred tools keep their injected policy runtime, now backed
  by a replaceable mock weather client. Approval and effect checks remain intact.
- Added service substitution tests, per-run isolation checks, hidden-parameter
  schema checks, and default in-process TCP blocking. No live requests in this increment.
- No dependency/package versions changed; existing isolated uv projects remain.
- Full default regression: **56 passed, 4 skipped**; no live model requests were run.
  Default in-process tests block TCP, and tool-service tests verify injected sentinel results and call records.

## Previous increment: use create_agent for the beginner weather assistant

- Replaced the manual StateGraph / ToolNode / tools_condition ReAct loop in
  `langgraph/main.py` with `langchain.agents.create_agent(model, tools, system_prompt)`.
- Removed forced tool choice and the post-run tool-call requirement. The model may
  call weather tools or answer directly. InMemorySaver and thread_id retain turns
  for the lifetime of the same agent process.
- Deleted the old beginner graph implementation. The independent advanced approval
  graph is retained because its custom interrupt/recovery lesson is outside this change.
- Added langchain 1.4.7 to the isolated uv project, retaining existing framework versions.
- Two beginner tests cover invoke/ToolMessage, follow-up history, and a direct reply.
- LangGraph regression: **11 passed, 1 skipped**; dependency compatibility checks passed.
- Live DeepSeek verification called get_weather for Beijing without forced selection.
- Run: `cd langgraph && uv run main.py "What is the weather in Beijing?"`.
- Tests: `cd langgraph && uv run pytest`.

## Current increment plan (recorded before implementation)

1. Replace AutoGen with an isolated LangGraph uv project while retaining the other three frameworks.
2. Add the same short weather beginner and unattended advanced approval/recovery entry points.
3. Use native StateGraph routing, interrupt/Command resume, SQLite checkpoints, planner/reviewer roles, and graph events.
4. Match pre-effect, reject/timeout/scripted, process-boundary resume, and opt-in live tests; update every active command and comparison.
5. Inspect secrets and the staged diff, commit, and publish without rewriting history.

## Current implementation

- `shared/hitl.py`: typed requests/decisions and automatic/scripted approvers.
- `shared/runtime.py`: allowlist, immutable operation payload binding, decision audit, local mock effects.
- `shared/cli.py`: bounded prepare/decide/resume, persistent script position, explicit retry attempts, terminal replay.
- Four separate uv projects: CrewAI, LangGraph, Pydantic AI, OpenAI Agents SDK.
- LangGraph replaces the removed project completely, including its venv, tests, commands, and active documentation.
- Native model-provider doubles are the default; the actual framework loop, tools, state and approval APIs execute.
- LangGraph graph-update streams and Pydantic graph-node events provide offline observability. Structured logs work in all four.
- Native exporters are opt-in with `FRAMEWORK_TRACE=1`; no default `OTEL_SDK_DISABLED` is set.

## Native approval and recovery boundaries

| Framework | Implemented boundary | Persistent state |
| --- | --- | --- |
| CrewAI | Custom pre-tool wrapper; application task-boundary replay | Task-output JSON and work-item checkpoint |
| LangGraph | Native interrupt before effect, conditional execute/reject routes, Command resume | SqliteSaver graph checkpoints and stable thread ID |
| Pydantic AI | Native requires_approval / DeferredToolRequests / DeferredToolResults | Typed message JSON plus pending call ID |
| Agents SDK | Native handoff, needs_approval, interruptions, RunState approve/reject | SQLiteSession plus native RunState JSON |

LangGraph restarts the interrupted node on resume. Registration before interrupt is
idempotent; booking remains in a downstream tool node. Its checkpointer includes
message state; a separate session export is only a readable conversation view.
All native histories/checkpoints remain separate from the shared authoritative
approval/effect database. A forged native resume approval cannot authorize itself.

## Installed API versions

| Project | Framework | Client / persistence | Test runner |
| --- | --- | --- | --- |
| CrewAI | crewai / crewai-core / crewai-cli 1.15.30 | openai 2.54.0 | pytest 9.1.1 |
| LangGraph | langgraph 1.2.17; checkpoint 4.3.0 | langchain-openai 1.7.2; langchain-core 1.7.0; checkpoint-sqlite 3.1.2; openai 3.37.0 | pytest 9.1.1 |
| Pydantic AI | pydantic-ai / pydantic-ai-slim 2.61.0 | openai 3.37.0 | pytest 9.1.1 |
| Agents SDK | openai-agents 0.24.0 | openai 3.37.0 | pytest 9.1.1 |

## Provider-loading fix retained

All beginner entries and gated live adapters share environment/.env/literal
`~/.zshrc` provider loading. Only the three allowed DeepSeek assignments are parsed;
shell commands/substitutions are never executed and key values are never logged.
Explicit provider credentials keep priority. Advanced mock runs do not read keys.
The earlier provider-loading regression suite remains in `shared/tests`.

## Deliberate limits

- CrewAI's checkpoint is application-owned task replay, not an in-flight Crew stack.
- Local checkpoints are trusted harness storage. One controller owns a state directory;
  distributed leases, signed approval decisions, and a production identity API are out of scope.
- SQLite deduplicates local mock receipts only. Real effects require downstream
  idempotency/reconciliation; conversation state is not an exactly-once guarantee.
- No real booking/transfer, VM sandbox, or MCP server is included. Execution isolation
  belongs to the harness/compute layer; MCP remains an optional extension.
- Streaming here is native event streaming, not fabricated model token deltas.

## Verification

- LangGraph isolated mock suite: 10 passed, 1 opt-in live test skipped.
- LangGraph beginner completed a real DeepSeek call for Beijing and executed get_weather.
- LangGraph gated advanced live smoke passed: proposal -> interrupt -> saved checkpoint -> approval -> resume -> one mock receipt.
- Native-state tests verify pending tasks, separate approval storage, and rejection of forged resume authorization.
- Full four-project default regression: **50 passed, 4 skipped** (the opt-in live smokes).
- English-only, syntax, no input(), documentation links/snippets, and beginner size checks passed.
- Dependency compatibility passed in the LangGraph environment; other framework implementations are retained.
- Staged secret checks run before publication; the final response reports the commit/push outcome.
