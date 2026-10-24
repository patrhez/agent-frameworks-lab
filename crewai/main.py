"""Two agents, two tasks, one sequential weather crew."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.providers import configure_beginner_environment
os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "true" if os.getenv("FRAMEWORK_TRACE") == "1" else "false")
os.environ.setdefault("CREWAI_STORAGE_DIR", str(Path(__file__).parent / ".local-data"))

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool

calls: list[str] = []


@tool("get_weather")
def get_weather(city: str) -> str:
    """Return mock weather for the requested city, never live weather."""
    print(f"[tool.call] get_weather(city={city!r})", flush=True)
    result = f"{city}: sunny, 22 C (mock data)."
    calls.append(city)
    print(f"[tool.return] {result}", flush=True)
    return result


def main() -> None:
    configure_beginner_environment()
    message = " ".join(sys.argv[1:]) or "What is the weather in Shanghai?"
    print(f"[user] {message}", flush=True)
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "...":
        raise SystemExit("Set a provider key in the environment, root .env, or a literal DEEPSEEK_API_KEY in ~/.zshrc.")
    calls.clear()
    llm = LLM(model=f"openai/{os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')}",
              base_url=os.getenv("OPENAI_BASE_URL"), timeout=60)
    # Agent: role, model, and available tools.
    researcher = Agent(
        role="Weather researcher", goal="Fetch weather using get_weather.",
        backstory="You use tools rather than guessing weather.",
        tools=[get_weather], llm=llm, allow_delegation=False, max_iter=4,
    )
    writer = Agent(
        role="Weather writer", goal="Answer using the researcher's result.",
        backstory="You write concise English answers and label mock data.",
        llm=llm, allow_delegation=False, max_iter=4,
    )
    # Task: assigned work and expected output; context connects the two tasks.
    research = Task(
        description=f"User: {message}\nYou MUST call get_weather for the city.",
        expected_output="Weather returned by get_weather, including the city.",
        agent=researcher,
    )
    write = Task(
        description=f"Answer this user in English using the supplied weather: {message}",
        expected_output="One natural-language sentence identifying mock weather.",
        agent=writer, context=[research],
    )
    # Crew: owns task scheduling and each agent's model/tool loop.
    result = Crew(
        agents=[researcher, writer], tasks=[research, write],
        process=Process.sequential, memory=False, cache=False, verbose=False,
    ).kickoff()
    if not calls:
        raise RuntimeError("The model skipped get_weather; this run did not pass.")
    print(f"[final] {result.raw}", flush=True)


if __name__ == "__main__":
    main()
