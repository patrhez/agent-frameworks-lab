"""Runner -> handoff -> needs_approval -> persisted RunState -> approve/reject."""
import json
import os

from agents import (
    Agent, GuardrailFunctionOutput, Model, ModelResponse, ModelSettings, OpenAIChatCompletionsModel,
    RunState, Runner, SQLiteSession, Usage, function_tool, input_guardrail,
    output_guardrail, set_tracing_disabled,
)
from openai import AsyncOpenAI
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from shared.logging_util import log
from shared.providers import live_settings
from shared.storage import read_json, write_json


class ScriptModel(Model):
    """Offline provider only: Runner still performs real handoffs and approvals."""
    def __init__(self, city):
        self.city = city

    async def get_response(self, system_instructions, input, model_settings, tools,
                           output_schema, handoffs, tracing, **kwargs):
        items = input if isinstance(input, list) else []
        calls = {i.get("call_id"): i.get("name") for i in items if i.get("type") == "function_call"}
        completed = {calls.get(i.get("call_id")): i.get("output") for i in items
                     if i.get("type") == "function_call_output"}
        if handoffs and "get_weather" not in completed:
            name, args = "get_weather", {"city": self.city}
        elif handoffs:
            name, args = handoffs[0].tool_name, {}
        elif "get_weather" not in completed:
            name, args = "get_weather", {"city": self.city}
        elif "book_flight" not in completed:
            name, args = "book_flight", {"city": self.city}
        else:
            text = f"Mock travel outcome: {completed['book_flight']}"
            return ModelResponse(output=[ResponseOutputMessage(
                id="final", type="message", role="assistant", status="completed",
                content=[ResponseOutputText(type="output_text", text=text, annotations=[])],
            )], usage=Usage(), response_id=None)
        return ModelResponse(output=[ResponseFunctionToolCall(
            type="function_call", name=name, arguments=json.dumps(args),
            call_id=f"call_{name}",
        )], usage=Usage(), response_id=None)

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError("Use LangGraph/Pydantic native event streams in this lab")
        yield


@input_guardrail(run_in_parallel=False)
async def input_check(ctx, agent, input):
    items = input if isinstance(input, list) else [{"role": "user", "content": input}]
    users = [i for i in items if i.get("role") == "user"]
    text = users[-1].get("content", "") if users else ""
    return GuardrailFunctionOutput(output_info="Nonempty input, at most 1000 characters",
                                  tripwire_triggered=not text or len(str(text)) > 1000)


@output_guardrail
async def mock_output_check(ctx, agent, output):
    return GuardrailFunctionOutput(output_info="Output must explicitly label mock execution",
                                  tripwire_triggered="mock" not in str(output).lower())


def build_agents(runtime, live=False):
    set_tracing_disabled(os.getenv("FRAMEWORK_TRACE", "0") != "1")
    if live:
        name, key, base = live_settings()
        model = OpenAIChatCompletionsModel(name, AsyncOpenAI(api_key=key, base_url=base,
                                                           timeout=60, max_retries=1))
    else:
        model = ScriptModel(runtime.city)
    extra = {"thinking": {"type": "disabled"}} if live and os.getenv("DEEPSEEK_API_KEY") else None

    @function_tool
    def get_weather(city: str) -> str:
        """Read low-risk mock weather."""
        return runtime.weather(city)

    async def require_approval(ctx, arguments, tool_name):
        runtime.request(arguments["city"])
        return True

    @function_tool(needs_approval=require_approval, failure_error_function=None)
    def book_flight(city: str) -> str:
        """Create a high-risk mock booking, only after approval."""
        return runtime.book(city)

    booking = Agent(name="Booking", model=model, tools=[book_flight],
                    model_settings=ModelSettings(tool_choice="book_flight", extra_body=extra),
                    instructions="You MUST call book_flight for the user's city. "
                    "After execution or denial, stop; your final answer MUST contain the word mock. "
                    "Never retry denial or invent a booking result.",
                    output_guardrails=[mock_output_check])
    router = Agent(name="Router", model=model, handoffs=[booking], tools=[get_weather],
                   model_settings=ModelSettings(tool_choice="required", extra_body=extra),
                   instructions="First call get_weather for the user's city, then immediately "
                   "transfer control to Booking using the handoff tool. Never answer the user yourself.",
                   input_guardrails=[input_check])
    return router


async def prepare(runtime, live=False, stream=False):
    agent = build_agents(runtime, live)
    session_id = f"{runtime.operation_id}:attempt-{runtime.attempts()}"
    session = SQLiteSession(session_id, runtime.directory / "session.sqlite")
    try:
        result = await Runner.run(agent, f"Check weather and book a mock flight to {runtime.city}.",
                                  session=session, max_turns=8)
        if not result.interruptions:
            raise RuntimeError(f"Expected native approval interruption, got: {result.final_output}")
        if not any(item.type == "handoff_output_item" for item in result.new_items):
            raise RuntimeError("The router did not execute a real SDK handoff")
        log("handoff", source="Router", target="Booking")
        write_json(runtime.directory / "checkpoint.json",
                   {"run_state": result.to_state().to_json(), "session_id": session_id})
    finally:
        session.close()


async def resume(runtime, live=False, stream=False):
    agent = build_agents(runtime, live)
    saved = read_json(runtime.directory / "checkpoint.json")
    state = await RunState.from_json(agent, saved["run_state"])
    for interruption in state.get_interruptions():
        if runtime.status() == "approved":
            state.approve(interruption)
        else:
            state.reject(interruption, rejection_message="Rejected by simulated approver; do not retry.")
    session = SQLiteSession(saved["session_id"], runtime.directory / "session.sqlite")
    try:
        result = await Runner.run(agent, state, session=session, max_turns=8)
        if result.interruptions:
            raise RuntimeError("Unexpected new approval request on resume")
        log("trace", guardrail="mock-output", passed=True)
        log("answer", text=result.final_output)
    finally:
        session.close()
