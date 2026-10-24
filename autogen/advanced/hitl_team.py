"""RoundRobinGroupChat -> pre-tool gate -> termination -> save/load team state."""
import json

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import FunctionalTermination, MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import FunctionCall
from autogen_core.models import CreateResult, RequestUsage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.replay import ReplayChatCompletionClient

from shared.logging_util import log
from shared.providers import live_settings
from shared.storage import read_json, write_json

MODEL_INFO = {"vision": False, "function_calling": True, "json_output": True,
              "family": "unknown", "structured_output": False}


class ScriptClient(ReplayChatCompletionClient):
    """Mock only the provider; actual Team, tool dispatch, events, and state APIs run."""
    def __init__(self, runtime):
        super().__init__(["unused"], model_info=MODEL_INFO)
        self.runtime = runtime

    async def create(self, messages, *, tools=(), **kwargs):
        if tools:
            content = [FunctionCall(id=f"call_{name}", name=name,
                                   arguments=json.dumps({"city": self.runtime.city}))
                       for name in ("get_weather", "book_flight")]
            reason = "function_calls"
        else:
            waiting = self.runtime.status() == "approved" and not self.runtime.effect_count()
            content = "Continue to booking executor." if waiting else "DONE: mock travel reviewed."
            reason = "stop"
        return CreateResult(content=content, finish_reason=reason, cached=False,
                            usage=RequestUsage(prompt_tokens=0, completion_tokens=0))


def build_team(runtime, live=False):
    def client():
        if not live:
            return ScriptClient(runtime)
        name, key, base = live_settings()
        return OpenAIChatCompletionClient(model=name, api_key=key, base_url=base,
                                         model_info=MODEL_INFO, timeout=60, max_retries=1)

    async def get_weather(city: str) -> str:
        """Read low-risk mock weather."""
        return runtime.weather(city)

    async def book_flight(city: str) -> str:
        """Request approval before creating a mock booking; never bypass the gate."""
        return runtime.guarded_book(city)

    executor_client, reviewer_client = client(), client()
    executor = AssistantAgent("executor", model_client=executor_client,
        tools=[get_weather, book_flight], reflect_on_tool_use=False,
        system_message="Call get_weather and book_flight for the requested city. "
        "If pending, stop. On resume call the tools again; policy reads the saved decision.")
    reviewer = AssistantAgent("reviewer", model_client=reviewer_client,
        system_message="Review the executor's mock outcome. If instructed to resume and no "
        "booking result exists yet, say continue. After a booking result or rejection, say DONE.")
    # Scope sentinels to their speaker: quoted history/user feedback must not stop a run.
    def reviewed(messages):
        terminal = runtime.status() == "rejected" or runtime.effect_count() == 1
        # Check final content, not hidden thought/to_text strings containing quoted DONE.
        return terminal and any(m.source == "reviewer" and
                                isinstance(getattr(m, "content", None), str) and
                                m.content.startswith("DONE") for m in messages)

    termination = (TextMentionTermination("PENDING_APPROVAL", sources=["executor"]) |
                   FunctionalTermination(reviewed) | MaxMessageTermination(8))
    team = RoundRobinGroupChat([executor, reviewer], termination_condition=termination)
    return team, [executor_client, reviewer_client]


async def drive(team, task, stream=False):
    result = None
    async for event in team.run_stream(task=task):
        if stream:
            log("stream", framework="autogen", event=type(event).__name__)
        if hasattr(event, "stop_reason"):
            result = event
    if result is None:
        raise RuntimeError("Team did not produce a terminal TaskResult")
    log("termination", reason=result.stop_reason)
    return result


async def prepare(runtime, live=False, stream=False):
    team, clients = build_team(runtime, live)
    try:
        result = await drive(team, f"Check weather and book a mock flight to {runtime.city}.", stream)
        runtime.pending_request()
        write_json(runtime.directory / "team-session.json", await team.save_state())
        write_json(runtime.directory / "checkpoint.json", {"status": "pending",
                                                            "operation_id": runtime.operation_id})
        log("answer", text=result.messages[-1].content)
    finally:
        for client in clients:
            await client.close()


async def resume(runtime, live=False, stream=False):
    team, clients = build_team(runtime, live)
    try:
        await team.load_state(read_json(runtime.directory / "team-session.json"))
        result = await drive(team, f"Resume for {runtime.city}; approval status is "
                             f"{runtime.status()}. The executor MUST invoke book_flight again now. "
                             "Earlier PENDING_APPROVAL results are obsolete, not new tool results. "
                             "Reviewer must let executor run before ending this resumed task.", stream)
        write_json(runtime.directory / "team-session.json", await team.save_state())
        log("answer", text=result.messages[-1].content)
    finally:
        for client in clients:
            await client.close()
