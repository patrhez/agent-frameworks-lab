"""AgentChat owns the model/tool/reflection loop for one assistant."""

import asyncio
import os
import sys
from pathlib import Path

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.providers import configure_beginner_environment
calls: list[str] = []


async def get_weather(city: str) -> str:
    """Return mock weather for the requested city, never live weather."""
    print(f"[tool.call] get_weather(city={city!r})", flush=True)
    result = f"{city}: sunny, 22 C (mock data)."
    calls.append(city)
    print(f"[tool.return] {result}", flush=True)
    return result


async def main() -> None:
    configure_beginner_environment()
    message = " ".join(sys.argv[1:]) or "What is the weather in Shanghai?"
    print(f"[user] {message}", flush=True)
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "...":
        raise SystemExit("Set a provider key in the environment, root .env, or a literal DEEPSEEK_API_KEY in ~/.zshrc.")
    calls.clear()
    client = OpenAIChatCompletionClient(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), timeout=60, max_retries=1,
        base_url=os.getenv("OPENAI_BASE_URL"),
        model_info={"vision": False, "function_calling": True, "json_output": True,
                    "family": "unknown", "structured_output": False},
    )
    try:
        agent = AssistantAgent(
            name="weather_assistant", model_client=client, tools=[get_weather],
            system_message="You MUST call get_weather for the user's city. "
            "Then answer in one English sentence and identify the data as mock.",
            reflect_on_tool_use=True, max_tool_iterations=2,
        )
        # No Team: run ends after the assistant's final text/reflection.
        result = await agent.run(task=message)
        if not calls:
            raise RuntimeError("The model skipped get_weather; this run did not pass.")
        print(f"[final] {result.messages[-1].content}", flush=True)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
