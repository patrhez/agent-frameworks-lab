# AutoGen AgentChat weather assistant

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
