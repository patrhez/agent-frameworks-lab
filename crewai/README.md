# CrewAI weather crew

## Five-line concept map

1. **Agent** holds a role, goal, model, and tools: `researcher` and `writer` in `main.py`.
2. **Task** describes work and its expected output: `research` and `write`.
3. **Crew** coordinates those agents and tasks: the `Crew(...).kickoff()` block.
4. **Process** selects scheduling: `Process.sequential` runs research before writing.
5. **Tool** exposes a Python function to an agent: `@tool("get_weather")` on the researcher.

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
