"""Runner, a function tool, an input guardrail, and a SQLite session."""

import asyncio
import os
import sys
from pathlib import Path

from agents import (
    Agent, GuardrailFunctionOutput, OpenAIChatCompletionsModel, Runner, SQLiteSession,
    RunContextWrapper, function_tool, input_guardrail, set_tracing_disabled,
)
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.providers import configure_beginner_environment
from shared.dependencies import AppDeps
set_tracing_disabled(os.getenv("FRAMEWORK_TRACE", "0") != "1")


@function_tool
def get_weather(ctx: RunContextWrapper[AppDeps], city: str) -> str:
    """Return mock weather for the requested city, never live weather."""
    return ctx.context.read_weather(city)


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
    configure_beginner_environment()
    message = " ".join(sys.argv[1:]) or "What is the weather in Shanghai?"
    print(f"[user] {message}", flush=True)
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "...":
        raise SystemExit("Set a provider key in the environment, root .env, or a literal DEEPSEEK_API_KEY in ~/.zshrc.")
    deps = AppDeps()
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
        result = await Runner.run(agent, message, context=deps, session=session, max_turns=6)
        if not deps.weather.calls:
            raise RuntimeError("The model skipped get_weather; this run did not pass.")
        print(f"[final] {result.final_output}", flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
