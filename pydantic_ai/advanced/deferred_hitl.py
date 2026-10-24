"""Typed tools -> DeferredToolRequests -> saved messages -> DeferredToolResults."""
import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic import BaseModel
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, RunContext
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from shared.logging_util import log
from shared.providers import live_settings
from shared.runtime import ToolRuntime
from shared.storage import read_json, write_json


class TravelAnswer(BaseModel):
    answer: str
    is_mock: bool


def mock_model(city):
    def respond(messages, info):
        returns = [part for message in messages for part in message.parts
                   if isinstance(part, ToolReturnPart)]
        if any(p.tool_name == "book_flight" for p in returns):
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,
                {"answer": f"Mock travel outcome: {returns[-1].content}", "is_mock": True})])
        name = "book_flight" if any(p.tool_name == "get_weather" for p in returns) else "get_weather"
        return ModelResponse(parts=[ToolCallPart(name, {"city": city}, tool_call_id=f"call_{name}")])
    return FunctionModel(respond)


def build_agent(runtime, live=False):
    if live:
        name, key, base = live_settings()
        model = OpenAIChatModel(name, provider=OpenAIProvider(api_key=key, base_url=base),
                               profile=OpenAIModelProfile(openai_supports_strict_tool_definition=False))
    else:
        model = mock_model(runtime.city)
    settings = {"extra_body": {"thinking": {"type": "disabled"}}} if live and os.getenv("DEEPSEEK_API_KEY") else {}
    agent = Agent(model, deps_type=ToolRuntime, output_type=[TravelAnswer, DeferredToolRequests],
                  model_settings=settings,
                  instructions="Call get_weather then book_flight for the requested city. "
                  "After execution or denial, return a structured mock answer. Never retry denial.")

    @agent.tool
    def get_weather(ctx: RunContext[ToolRuntime], city: str) -> str:
        """Read low-risk mock weather using dependency injection."""
        return ctx.deps.weather(city)

    @agent.tool(requires_approval=True)
    def book_flight(ctx: RunContext[ToolRuntime], city: str) -> str:
        """Create a high-risk mock booking after native deferred approval."""
        return ctx.deps.book(city)

    return agent


async def run_agent(agent, runtime, stream=False, **kwargs):
    async with agent.iter(deps=runtime, usage_limits=UsageLimits(request_limit=8), **kwargs) as run:
        async for node in run:
            if stream:
                log("stream", framework="pydantic-ai", event=type(node).__name__)
        return run.result


async def prepare(runtime, live=False, stream=False):
    result = await run_agent(build_agent(runtime, live), runtime, stream,
                             user_prompt=f"Check weather and book a mock flight to {runtime.city}.")
    if not isinstance(result.output, DeferredToolRequests) or not result.output.approvals:
        raise RuntimeError("Expected native deferred approvals")
    pending = result.output.approvals
    if len(pending) != 1 or pending[0].tool_name != "book_flight":
        raise RuntimeError("Unexpected deferred tool request")
    runtime.request(pending[0].args_as_dict()["city"])
    # History lives separately from the pending tool ID checkpoint and policy ledger.
    (runtime.directory / "messages.json").write_bytes(result.all_messages_json())
    write_json(runtime.directory / "checkpoint.json", {"tool_call_id": pending[0].tool_call_id})


async def resume(runtime, live=False, stream=False):
    history = ModelMessagesTypeAdapter.validate_json((runtime.directory / "messages.json").read_bytes())
    pending = read_json(runtime.directory / "checkpoint.json")
    results = DeferredToolResults(approvals={pending["tool_call_id"]: runtime.status() == "approved"})
    result = await run_agent(build_agent(runtime, live), runtime, stream,
                             message_history=history, deferred_tool_results=results)
    if not isinstance(result.output, TravelAnswer) or not result.output.is_mock:
        raise RuntimeError("Expected a validated mock final answer")
    (runtime.directory / "messages.json").write_bytes(result.all_messages_json())
    log("answer", **result.output.model_dump())
