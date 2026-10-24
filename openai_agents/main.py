"""Runner, a function tool, an input guardrail, and a SQLite session."""

import asyncio
import os
import sys
from pathlib import Path

from agents import (
    Agent, GuardrailFunctionOutput, OpenAIChatCompletionsModel, Runner, SQLiteSession,
    function_tool, input_guardrail, set_tracing_disabled,
)
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
if os.getenv("DEEPSEEK_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
    os.environ["OPENAI_BASE_URL"] = os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com")
    os.environ["OPENAI_MODEL"] = os.getenv("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat")
set_tracing_disabled(os.getenv("FRAMEWORK_TRACE", "0") != "1")
calls: list[str] = []


@function_tool
def get_weather(city: str) -> str:
    """Return mock weather for the requested city, never live weather."""
    print(f"[tool.call] get_weather(city={city!r})", flush=True)
    result = f"{city}: sunny, 22 C (mock data)."
    calls.append(city)
    print(f"[tool.return] {result}", flush=True)
    return result


@input_guardrail(run_in_parallel=False)
async def short_input(ctx, agent, input) -> GuardrailFunctionOutput:
    """Reject empty or oversized inputs before starting the model loop."""
    # Sessions supply a message list, potentially including earlier turns.
    text = input
    if isinstance(input, list):
        users = [item for item in input if item.get("role") == "user"]
        text = users[-1].get("content", "") if users else ""
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text)
    blocked = not isinstance(text, str) or not 1 <= len(text.strip()) <= 500
    return GuardrailFunctionOutput(
        output_info="Input must contain 1-500 characters.", tripwire_triggered=blocked,
    )


async def main() -> None:
    message = " ".join(sys.argv[1:]) or "What is the weather in Shanghai?"
    print(f"[user] {message}", flush=True)
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "...":
        raise SystemExit("Set DEEPSEEK_API_KEY or OPENAI_API_KEY in the root .env or shell first.")
    calls.clear()
    agent = Agent(
        name="Weather assistant", model=OpenAIChatCompletionsModel(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            openai_client=AsyncOpenAI(timeout=60, max_retries=1)),
        instructions="You MUST call get_weather for the user's city on every turn. "
        "Then answer in one English sentence and identify the data as mock.",
        tools=[get_weather], input_guardrails=[short_input],
    )
    # A session without a file is in-memory; opt into persistence with SESSION_DB.
    session = SQLiteSession("weather-lab", os.getenv("SESSION_DB", ":memory:"))
    try:
        result = await Runner.run(agent, message, session=session, max_turns=6)
        if not calls:
            raise RuntimeError("The model skipped get_weather; this run did not pass.")
        print(f"[final] {result.final_output}", flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
