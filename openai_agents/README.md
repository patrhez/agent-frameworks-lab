# OpenAI Agents SDK weather assistant

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
