# Agent Frameworks Lab

A four-hour, hands-on comparison for a Go backend developer who has written an
agent harness. Each project solves the same task: receive a weather question,
let a model call `get_weather(city: str) -> str`, and produce an English answer.
The tool always returns sunny, 22 C, explicitly labeled as mock data.
Model requests use the configured OpenAI-compatible provider; the weather tool
makes no network requests. Live verification used DeepSeek.

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

If you already assign DeepSeek variables in your interactive `~/.zshrc`,
export their names before running the demos; no values need to be printed or copied:

```sh
export DEEPSEEK_API_KEY DEEPSEEK_API_BASE_URL DEEPSEEK_DEFAULT_MODEL
```

Shell assignments without `export` are not inherited by child processes;
export their names to make them available. The demos do not read or source `~/.zshrc`.
Alternatively, uncomment and configure the DeepSeek entries in your ignored `.env`.
A nonempty DeepSeek key selects DeepSeek over OpenAI settings.

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
(cd autogen && uv run main.py)
(cd pydantic_ai && uv run main.py)
(cd openai_agents && uv run main.py)
```

The default question is `What is the weather in Shanghai?`. All demos accept a
custom question as a command-line argument:

```sh
(cd autogen && uv run main.py "What is the weather in Beijing?")
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
prints `[structured]` with the validated final object. A missing tool call raises
an error instead of reporting success. Prompts request the call; the post-run
check detects violations. These checks are not an authorization boundary.

Missing credentials stop execution with a setup message. Authentication, quota,
connectivity, or model-access errors require fixing the relevant environment
setting or account. A model override should support tool calling. AutoGen declares
text/tool capabilities explicitly for models outside its built-in registry.
The Agents SDK uses its Chat Completions adapter for provider compatibility.
Pydantic AI validates final output locally and disables DeepSeek thinking mode
to allow its output-tool selection; server-side strict tool schemas are disabled.
Tracing/telemetry is disabled explicitly in the CrewAI and Agents SDK demos.

## Four-hour route

| Time | Activity |
| --- | --- |
| 0:00–0:20 | Configure the environment; run all four examples |
| 0:20–1:00 | CrewAI: follow Researcher → Task context → Writer |
| 1:00–1:40 | AutoGen: follow tool events and the assistant's termination |
| 1:40–2:20 | Pydantic AI: inspect tool schema and validated final output |
| 2:20–3:00 | Agents SDK: inspect Runner, guardrail, and session history |
| 3:00–4:00 | Change a city, try a rejected input, inspect state, fill the comparison |

## Project comparison worksheet

| Project | Abstractions to locate | Loop observation | State observation | Go harness notes |
| --- | --- | --- | --- | --- |
| [CrewAI](crewai/README.md) | Agent / Task / Crew | | | |
| [AutoGen AgentChat](autogen/README.md) | AssistantAgent / model client / TaskResult | | | |
| [Pydantic AI](pydantic_ai/README.md) | Agent / tool / output model | | | |
| [OpenAI Agents SDK](openai_agents/README.md) | Agent / Runner / session / guardrail | | | |

## How I compare with a Go harness

Use these five questions to fill [COMPARISON.md](COMPARISON.md), based on code
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
- [x] Root README, four project READMEs, and comparison worksheet exist.
- [x] No real API key is included in repository files.
- [x] Go harness comparison covers loop, checkpoint, permissions, HITL, persistence.

Read [GUIDE.md](GUIDE.md) for a `uv` tutorial, framework building blocks, code
comparisons, and English answers to all three self-check questions.
