"""Crew tool wrapper -> pending work item -> task-boundary replay after approval."""
import asyncio
import json
import os

# No OTEL_SDK_DISABLED: application JSON logs work offline; framework export is opt-in.
os.environ.setdefault("CREWAI_TRACING_ENABLED", "true" if os.getenv("FRAMEWORK_TRACE") == "1" else "false")
os.environ.setdefault("CREWAI_TELEMETRY_DISABLED", "true")

from crewai import Agent, BaseLLM, Crew, LLM, Task
from crewai.tools import tool

from shared.logging_util import log
from shared.providers import live_settings
from shared.storage import read_json, write_json


class ScriptLLM(BaseLLM):
    """A deterministic ReAct provider; Crew owns parsing and actual tool dispatch."""
    def __init__(self, runtime):
        super().__init__(model="offline-react")
        self.runtime, self.turn = runtime, 0

    def call(self, messages, **kwargs):
        self.turn += 1
        args = json.dumps({"city": self.runtime.city})
        if self.turn == 1:
            return f"Thought: Read weather.\nAction: get_weather\nAction Input: {args}"
        if self.turn == 2:
            return f"Thought: Request booking.\nAction: book_flight\nAction Input: {args}"
        return f"Thought: Stop this task.\nFinal Answer: Mock outcome: {self.runtime.status()}"

    def supports_function_calling(self):
        return False


def execute_crew(runtime, live=False, previous=None):
    storage = runtime.directory / "crew-storage"
    storage.mkdir(exist_ok=True)
    os.environ["CREWAI_STORAGE_DIR"] = str(storage)
    if live:
        name, key, base = live_settings()
        model = LLM(model=f"openai/{name}", api_key=key, base_url=base, timeout=60)
    else:
        model = ScriptLLM(runtime)

    @tool("get_weather")
    def get_weather(city: str) -> str:
        """Read low-risk mock weather."""
        return runtime.weather(city)

    @tool("book_flight")
    def book_flight(city: str) -> str:
        """Request a mock booking; pre-tool approval blocks effects until approved."""
        return runtime.guarded_book(city)

    agent = Agent(role="Travel executor", goal="Use weather and booking tools safely.",
                  backstory="Respect pending or rejected approval; never bypass tools.",
                  tools=[get_weather, book_flight], llm=model, max_iter=5,
                  allow_delegation=False, max_retry_limit=0)
    task = Task(agent=agent,
        description=f"Call get_weather and book_flight for {runtime.city}. If pending or rejected, "
        f"stop and report it. CURRENT authoritative policy status: {runtime.status()}. "
        "You MUST call both tools in THIS task; do not reuse historical tool results. "
        "An earlier pending answer is obsolete after approval. "
        f"Historical context only: {previous or 'none'}.",
        expected_output="A short mock travel outcome.")
    result = Crew(agents=[agent], tasks=[task], memory=False, cache=False,
                  verbose=False, tracing=os.getenv("FRAMEWORK_TRACE", "0") == "1").kickoff()
    write_json(runtime.directory / "crew-session.json", {"task_output": result.raw})
    log("answer", text=result.raw)


async def prepare(runtime, live=False, stream=False):
    await asyncio.to_thread(execute_crew, runtime, live)
    runtime.pending_request()
    # Application-owned work-item checkpoint, NOT serialization of the Crew execution stack.
    write_json(runtime.directory / "checkpoint.json", {"operation_id": runtime.operation_id,
                                                        "resume_at": "booking-task-boundary"})


async def resume(runtime, live=False, stream=False):
    previous = read_json(runtime.directory / "crew-session.json")["task_output"]
    await asyncio.to_thread(execute_crew, runtime, live, previous)
