# Agent Frameworks Lab

A four-hour, hands-on comparison for a Go backend developer who has written an
agent harness. Each project solves the same task: receive a weather question,
let a model call `get_weather(city: str) -> str`, and produce an English answer.
The tool always returns sunny, 22 C, explicitly labeled as mock data.
Model requests use the configured OpenAI-compatible provider; the weather tool
makes no network requests. Live verification used DeepSeek.

## Injected mock tool dependencies

All four beginner entries now receive per-run services instead of relying on pure
functions or global dependency instances. `shared/dependencies.py` defines
`AppDeps` and a `WeatherClient` backed by an in-memory dictionary. Its `.get(city)`
logs `[deps.weather]`; tools never use requests/httpx or call a weather endpoint.

| Framework | Injection boundary | Tool access |
| --- | --- | --- |
| Pydantic AI | `Agent(deps_type=AppDeps)` and `run_sync(..., deps=deps)` | `RunContext[AppDeps].deps` with `@agent.tool` |
| OpenAI Agents SDK | `Runner.run(..., context=deps)` | `RunContextWrapper[AppDeps].context` |
| LangChain / LangGraph | `context_schema=AppDeps` and `invoke(..., context=deps)` | Injected `ToolRuntime[AppDeps].context` |
| CrewAI | `WeatherTool(deps=deps)` / `BookingTool(deps=deps)` | Tool model field used by `_run` |

The shared `read_weather` helper delegates to `deps.weather.get(city)` and retains
consistent tool logs. Advanced tools keep their policy/approval runtime through
injected context or Tool fields. Checkpoints persist operation state, not service
instances; services are rebuilt when resuming. Pydantic's context-free `tool_plain`
is deliberately not used for tools requiring dependencies.

Run `./scripts/test_all.sh -q` without a key. Provider doubles are local, dependency
substitution tests assert the injected result/call record, and default in-process
tests reject TCP connections. This increment performs no live model requests.
Existing model-backed entry commands still require provider credentials; tool
dependencies remain mocks even if live model inference is explicitly selected.

## Advanced: unattended approval and recovery

Keep the beginner `main.py` examples as the first step. Advanced entries mock only
the model provider by default; framework loops, tool dispatch, and state APIs are real.
No key, network, keyboard prompt, or `input()` is needed.

```sh
(cd crewai && uv run python -m advanced.run --hitl auto_approve)
(cd langgraph && uv run python -m advanced.run --hitl auto_approve --stream)
(cd pydantic_ai && uv run python -m advanced.run --hitl auto_approve --stream)
(cd openai_agents && uv run python -m advanced.run --hitl auto_approve)
```

Low-risk `get_weather` passes the allowlist; high-risk `book_flight` persists a
pending request and cannot create its mock receipt until approved. All projects
support these commands **inside their own directory**:

```sh
uv run python -m advanced.run --hitl auto_reject --state-dir .local-data/rejected
uv run python -m advanced.run --hitl scripted \
  --script ../shared/scripts/approve_after_reject.json --state-dir .local-data/scripted
uv run python -m advanced.run --hitl scripted \
  --script ../shared/scripts/timeout.json --state-dir .local-data/timeout

# Separate processes; prepare exits with zero booking effects.
uv run python -m advanced.run --phase prepare --state-dir .local-data/persisted
uv run python -m advanced.run --phase resume --state-dir .local-data/persisted
```

Reusing a completed directory returns its terminal outcome without a new effect.
Use a fresh directory for another operation/mode. Scripted all-mode can explicitly
start a new attempt after rejection if a matching next step exists. A rejected
call never executes; the next approval applies to the new attempt. Timeouts reject
immediately, without sleeping. Script position and decisions survive restarts.

`HITL_MODE=auto_approve|auto_reject|scripted` defaults to `auto_approve`; `--hitl`
overrides it. `HITL_SCRIPT` supplies a path if `--script` is omitted. `--role readonly`
denies booking before model execution. The default traveler can request it but
still needs approval. Unknown tools fail the shared allowlist.

### State and observability

`control.json` identifies an operation. `checkpoint.json` stores pending work.
Framework history/session files are separate from `approvals.sqlite`, whose
requests, decisions, and mock effects have separate tables. See each module map
for native APIs. Only load trusted local harness checkpoints, not client input.

One controller owns a state directory. SQLite deduplicates local mock receipts
by operation ID; external providers need downstream idempotency/reconciliation.
Conversation persistence alone cannot guarantee crash-safe external side effects.

JSON logs include `[user]`, `[tool.call]`, `[tool.return]`, `[approval]`,
`[checkpoint]`, `[deps.weather]`, and `[final]`. `LAB_TRACE=1` adds diagnostic logs. `--stream`
prints native graph-update events in LangGraph and graph-node events in Pydantic AI.
CrewAI/SDK adapters do not claim streaming. `FRAMEWORK_TRACE=1` opts into native
CrewAI/SDK exporters; these may require separate tracing credentials and transmit
trace data. Offline structured logs need no exporter. No entry point sets
`OTEL_SDK_DISABLED` by default.

### Test without a key; opt into live smoke

```sh
./scripts/test_all.sh -q
(cd openai_agents && uv run pytest)
# Export provider settings first. This opt-in spends model tokens.
(cd pydantic_ai && RUN_LIVE=1 uv run pytest tests/test_advanced.py::test_live_smoke -q)
(cd openai_agents && RUN_LIVE=1 uv run python -m advanced.run --live \
  --state-dir .local-data/live)
```

All four projects have a gated live smoke. Without `RUN_LIVE=1` tests skip it
and `--live` is rejected. Expect several model calls, roughly 10–120 seconds
per project, and provider token charges. Bookings remain mock. Tests use fresh
temporary directories; provider credentials never enter serialized state.

Read [GUIDE.md](GUIDE.md) for the 90-minute return path,
[COMPARISON.md](COMPARISON.md) for the completed comparison, and
[ADVANCED_CHANGELOG.md](ADVANCED_CHANGELOG.md) for versions and limitations.

## Setup

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/),
Python 3.11, and an OpenAI or DeepSeek API key with model access.

Clone the repository:

```sh
git clone https://github.com/patrhez/agent-frameworks-lab.git
cd agent-frameworks-lab
```

From the repository root:

```sh
cp .env.example .env
# Edit .env locally and replace ... with your API key.
```

Every demo loads that exact root `.env` using `python-dotenv`. Existing shell
environment variables take precedence. Never put a real key in `.env.example`.

If no usable provider key is available in the environment or root `.env`, the
shared loader reads the three literal DeepSeek assignments from `~/.zshrc`:
`DEEPSEEK_API_KEY`, `DEEPSEEK_API_BASE_URL`, and `DEEPSEEK_DEFAULT_MODEL`.
Both `NAME=value` and `export NAME=value` work. You can run `uv run main.py`
directly without manually exporting these existing assignments.

The loader only parses those names: it never sources the file, runs shell commands,
or expands variable/command substitutions. Computed shell values must be exported
normally. Environment settings take precedence over `.env`, then the shell fallback;
an explicit usable OpenAI key prevents automatic selection of a shell-only DeepSeek key.
An explicitly configured DeepSeek key selects DeepSeek over OpenAI. Credentials
are used only by API clients and are never printed or copied into repository files.
Advanced mock runs do not read the shell file; gated live runs use this same loader.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Required for OpenAI | Authenticate OpenAI requests |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Bare model name, shared across demos |
| `OPENAI_BASE_URL` | SDK default | Optional OpenAI-compatible endpoint |
| `DEEPSEEK_API_KEY` | Optional | Select and authenticate DeepSeek |
| `DEEPSEEK_API_BASE_URL` | `https://api.deepseek.com` | DeepSeek-compatible endpoint |
| `DEEPSEEK_DEFAULT_MODEL` | `deepseek-chat` | DeepSeek model; tests used the configured `deepseek-flash` |
| `SESSION_DB` | `:memory:` | Agents SDK only: optional SQLite file path |

Each directory has its own `pyproject.toml`, `.python-version`, `uv.lock`, and
`.venv`. There is no root Python workspace or shared dependency lock.
`uv run` installs/syncs the selected project's locked dependencies automatically.
Keep each `uv.lock` in version control for reproducibility.

## Run the four demos

Run each command from the repository root; the subshell selects the independent
project, so each demo is also directly runnable as `uv run main.py` in its directory.

```sh
(cd crewai && uv run main.py)
(cd langgraph && uv run main.py)
(cd pydantic_ai && uv run main.py)
(cd openai_agents && uv run main.py)
```

The default question is `What is the weather in Shanghai?`. All demos accept a
custom question as a command-line argument:

```sh
(cd langgraph && uv run main.py "What is the weather in Beijing?")
```

Every successful run prints these markers, in order (framework diagnostics may
also appear):

```text
[user] What is the weather in Shanghai?
[tool.call] get_weather(city='Shanghai')
[tool.return] Shanghai: sunny, 22 C (mock data).
[final] ...natural-language answer...
```

The final wording is model-generated and can vary. Pydantic AI additionally
prints `[structured]` with the validated final object. The LangChain beginner
uses `create_agent` and lets the model choose tools or a direct reply. Other
beginner demos retain their weather-call checks; these are not authorization boundaries.

Missing credentials stop execution with a setup message. Authentication, quota,
connectivity, or model-access errors require fixing the relevant environment
setting or account. A model override should support tool calling. The LangChain
`create_agent` factory owns the beginner loop; its recursion limit bounds execution.
The separate advanced LangGraph workflow still demonstrates explicit approval branches.
The Agents SDK uses its Chat Completions adapter for provider compatibility.
Pydantic AI validates final output locally and disables DeepSeek thinking mode
to allow its output-tool selection; server-side strict tool schemas are disabled.
External tracing is opt-in for CrewAI/SDK; advanced structured logs work offline.

## Four-hour route

| Time | Activity |
| --- | --- |
| 0:00–0:20 | Configure the environment; run all four examples |
| 0:20–1:00 | CrewAI: follow Researcher → Task context → Writer |
| 1:00–1:40 | LangChain create_agent first; then native LangGraph approval checkpoints |
| 1:40–2:20 | Pydantic AI: inspect tool schema and validated final output |
| 2:20–3:00 | Agents SDK: inspect Runner, guardrail, and session history |
| 3:00–4:00 | Change a city, try a rejected input, inspect state, review the comparison |

## Project comparison map

| Project | Abstractions to locate | Loop observation | State observation | Go harness notes |
| --- | --- | --- | --- | --- |
| [CrewAI](crewai/README.md) | Agent / Task / Crew | Crew task/agent loop | Task outputs + work item | App-owned policy and replay |
| [LangChain / LangGraph](langgraph/README.md) | create_agent / tools / checkpointer | Factory-owned beginner loop | In-memory thread; advanced SQLite state | Advanced native interrupt and effect policy |
| [Pydantic AI](pydantic_ai/README.md) | Agent / tool / output model | Agent graph | Typed history + deferred IDs | Typed approval protocol |
| [OpenAI Agents SDK](openai_agents/README.md) | Agent / Runner / session / guardrail | Runner + handoff | SQLiteSession + RunState | Native interruption protocol |

## How I compare with a Go harness

Use these five questions to review [COMPARISON.md](COMPARISON.md), based on code
and observed behavior:

1. **Loop:** Who calls the model, dispatches tools, limits iterations, and stops?
2. **Checkpoint:** What would you serialize to resume halfway through a tool call?
3. **Permissions:** Where could an allowlist or approval check block execution?
4. **HITL:** How would a human approve a proposed action before it runs?
5. **Persistence:** Where does conversation history live, and what survives restart?

Sketch the equivalent Go `for` loop, message slice, tool registry, and policy
check. Then identify which pieces the framework owns and which remain your job.
The demos intentionally cover a small slice of each framework; absent features
in a demo are not evidence that the framework lacks them.

## Verification

Installed versions are recorded in each project's README from `uv pip freeze`.
On 2026-10-24, all four independent `uv run main.py` commands exited successfully
against the configured DeepSeek endpoint/model. Each printed a real framework
tool call for Shanghai, the mock weather result, and a model-generated final answer.
Credentials were passed through child-process environment variables, never saved
in the repository or printed. Offline checks additionally verified SDK guardrail
rejection before a model call and SQLite history across two runs.

- [x] All four directories complete `uv run main.py` with a live model.
- [x] All four live runs call the mock `get_weather` tool.
- [x] Root README, four project READMEs, and filled comparison exist.
- [x] No real API key is included in repository files.
- [x] Go harness comparison covers loop, checkpoint, permissions, HITL, persistence.

Read [GUIDE.md](GUIDE.md) for a `uv` tutorial, framework building blocks, code
comparisons, and English answers to all three self-check questions.
