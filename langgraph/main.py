"""A weather agent built with the official create_agent factory."""
import os
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain.tools import ToolRuntime, tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.providers import configure_beginner_environment
from shared.dependencies import AppDeps


@tool
def get_weather(city: str, runtime: ToolRuntime[AppDeps]) -> str:
    """Return mock weather for the requested city, never live weather."""
    return runtime.context.read_weather(city)


def build_agent(model):
    return create_agent(
        model=model, tools=[get_weather],
        system_prompt="For city weather questions, use get_weather and identify its mock data "
        "in a concise English answer. Answer other questions directly when no tool is needed.",
        checkpointer=InMemorySaver(),
        context_schema=AppDeps,
    )


def main() -> None:
    configure_beginner_environment()
    message = " ".join(sys.argv[1:]) or "What is the weather in Shanghai?"
    print(f"[user] {message}", flush=True)
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "...":
        raise SystemExit("Configure a provider key in the environment, root .env, or ~/.zshrc.")
    deps = AppDeps()
    model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=60, max_retries=1,
        extra_body={"thinking": {"type": "disabled"}} if os.getenv("DEEPSEEK_API_KEY") else {})
    result = build_agent(model).invoke({"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": "weather-demo"}, "recursion_limit": 8}, context=deps)
    print(f"[final] {result['messages'][-1].content}", flush=True)


if __name__ == "__main__":
    main()
