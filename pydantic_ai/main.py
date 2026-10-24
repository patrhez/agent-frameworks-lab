"""Typed function tool plus a validated Pydantic final answer."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.providers import configure_beginner_environment
from shared.dependencies import AppDeps
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


class WeatherAnswer(BaseModel):
    city: str = Field(min_length=1)
    answer: str = Field(min_length=1, description="Natural-language English answer")
    is_mock: bool = Field(description="True when the weather comes from mock data")


def build_agent(model, settings=None):
    agent = Agent(
        model,
        deps_type=AppDeps, output_type=WeatherAnswer,
        model_settings=settings or {},
        instructions="You MUST call get_weather for the user's city before answering. "
        "Return one English sentence identifying mock data, with is_mock=true.",
    )

    @agent.tool
    def get_weather(ctx: RunContext[AppDeps], city: str) -> str:
        """Read mock weather through the per-run dependency context."""
        return ctx.deps.read_weather(city)

    return agent


def main() -> None:
    configure_beginner_environment()
    message = " ".join(sys.argv[1:]) or "What is the weather in Shanghai?"
    print(f"[user] {message}", flush=True)
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "...":
        raise SystemExit("Set a provider key in the environment, root .env, or a literal DEEPSEEK_API_KEY in ~/.zshrc.")
    deps = AppDeps()
    model = OpenAIChatModel(os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        provider=OpenAIProvider(base_url=os.getenv("OPENAI_BASE_URL")),
        profile=OpenAIModelProfile(openai_supports_strict_tool_definition=False))
    settings = {"extra_body": {"thinking": {"type": "disabled"}}} if os.getenv("DEEPSEEK_API_KEY") else {}
    agent = build_agent(model, settings)
    result = agent.run_sync(message, deps=deps, usage_limits=UsageLimits(request_limit=6))
    if not deps.weather.calls:
        raise RuntimeError("The model skipped get_weather; this run did not pass.")
    if not result.output.is_mock:
        raise RuntimeError("The final answer must identify mock data.")
    print(f"[structured] {result.output.model_dump_json()}", flush=True)
    print(f"[final] {result.output.answer}", flush=True)


if __name__ == "__main__":
    main()
