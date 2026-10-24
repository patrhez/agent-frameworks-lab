# Pydantic AI weather assistant

## Five-line concept map

1. **Agent** binds the model, instructions, function tools, and final output type.
2. **Function tool** uses `@agent.tool_plain`; no runtime dependencies are needed here.
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
`class WeatherAnswer` block (lines 24–27) defines the final answer's fields; the
`output_type=WeatherAnswer` line (line 40) attaches the contract to the agent. The
`@agent.tool_plain` / `def get_weather(city: str) -> str` lines (lines 47–48) generate the
tool argument schema from annotations. `Field(min_length=1)` rejects empty city
or answer fields. The plain string tool result is distinct from the validated
final Pydantic output; annotations are not a business authorization policy.
This demonstrates structured output; dependency injection is not needed.

## Compared with a handwritten while-loop

- Agent owns model requests, tool execution, and output-validation retries.
- Python annotations generate the tool argument contract; BaseModel validates final fields.
- You consume `result.output.answer` instead of manually parsing final JSON.

The installed API uses `output_type`, not the older `result_type` spelling.
`tool_plain` is the official registration method for a tool without `RunContext`;
use `@agent.tool` with `RunContext[Deps]` when adding dependency injection.
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
