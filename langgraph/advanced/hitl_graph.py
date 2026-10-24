"""StateGraph -> interrupt -> SQLite checkpoint -> Command(resume) -> safe tool."""
import asyncio
from dataclasses import asdict
import os

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, messages_to_dict
from langchain.tools import ToolRuntime as ToolContext, tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.runtime import Runtime
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from shared.logging_util import log
from shared.storage import read_json, write_json
from shared.dependencies import AppDeps
from .models import chat_model


class TravelState(MessagesState):
    approved: bool


@tool
def get_weather(city: str, runtime: ToolContext[AppDeps]) -> str:
    """Read mock weather through the graph's injected run context."""
    return runtime.context.read_weather(city)


@tool
def book_flight(city: str, runtime: ToolContext[AppDeps]) -> str:
    """Create a mock receipt through the injected approval runtime."""
    return runtime.context.require_runtime().book(city)


def build_graph(runtime, checkpointer, live=False):
    if os.getenv("FRAMEWORK_TRACE") == "1":
        os.environ.setdefault("LANGSMITH_TRACING", "true")
    planner_model = chat_model(runtime.city, live)
    reviewer_model = chat_model(runtime.city, live, reviewer=True)

    def planner(state, runtime: Runtime[AppDeps]):
        weather_done = any(isinstance(m, ToolMessage) and m.name == "get_weather"
                           for m in state["messages"])
        expected = "book_flight" if weather_done else "get_weather"
        bound = planner_model.bind_tools([get_weather, book_flight], tool_choice=expected,
                                         parallel_tool_calls=False)
        result = bound.invoke([SystemMessage(content="Plan one requested mock travel tool call."),
                               *state["messages"]])
        if len(result.tool_calls) != 1 or result.tool_calls[0]["name"] != expected:
            raise RuntimeError("Planner did not emit the expected single typed tool call")
        runtime.context.require_runtime().authorize(result.tool_calls[0]["name"])
        return {"messages": [result]}

    def approval(state, runtime: Runtime[AppDeps]):
        call = state["messages"][-1].tool_calls[0]
        policy = runtime.context.require_runtime()
        request = policy.request(call["args"]["city"])
        # This node restarts on resume. Registration is idempotent; NO effect before interrupt.
        decision = interrupt(asdict(request))
        approved = isinstance(decision, dict) and decision.get("approved") is True
        if approved != (policy.status() == "approved"):
            raise PermissionError("Native resume value disagrees with the persisted policy decision")
        return {"approved": approved}

    def rejected(state):
        call = state["messages"][-1].tool_calls[0]
        return {"messages": [ToolMessage(content="REJECTED: mock booking not executed.",
                                         tool_call_id=call["id"], name="book_flight")]}

    def reviewer(state):
        answer = reviewer_model.invoke([SystemMessage(content="Review the tool outcome. "
            "Answer briefly in English, include the word mock, and never invent an executed booking."),
            *state["messages"]])
        if "mock" not in str(answer.content).lower():
            raise ValueError("Reviewer must identify mock data")
        return {"messages": [answer]}

    graph = StateGraph(TravelState, context_schema=AppDeps)
    for name, node in {"planner": planner, "weather": ToolNode([get_weather]),
                       "approval": approval, "execute": ToolNode([book_flight]),
                       "rejected": rejected, "reviewer": reviewer}.items():
        graph.add_node(name, node)
    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", lambda s: "approval" if
        s["messages"][-1].tool_calls[0]["name"] == "book_flight" else "weather")
    graph.add_edge("weather", "planner")
    graph.add_conditional_edges("approval", lambda s: "execute" if s["approved"] else "rejected")
    graph.add_edge("execute", "reviewer")
    graph.add_edge("rejected", "reviewer")
    graph.add_edge("reviewer", END)
    return graph.compile(checkpointer=checkpointer)


def drive(runtime, live, stream, resuming):
    checkpoint = runtime.directory / "checkpoint.json"
    saved = read_json(checkpoint) if resuming else {
        "thread_id": f"{runtime.operation_id}:attempt-{runtime.attempts()}",
    }
    config = {"configurable": {"thread_id": saved["thread_id"]}, "recursion_limit": 16}
    payload = Command(resume={"approved": runtime.status() == "approved"}) if resuming else {
        "messages": [HumanMessage(content=f"Check weather and book a mock flight to {runtime.city}.")],
    }
    with SqliteSaver.from_conn_string(str(runtime.directory / "graph.sqlite")) as saver:
        graph = build_graph(runtime, saver, live)
        deps = AppDeps.for_runtime(runtime)
        if stream:
            for event in graph.stream(payload, config=config, context=deps, stream_mode="updates"):
                log("stream", framework="langgraph", nodes=list(event))
        else:
            graph.invoke(payload, config=config, context=deps)
        snapshot = graph.get_state(config)
        interrupted = any(task.interrupts for task in snapshot.tasks)
        # Native checkpoints include messages; this separate export is a conversation view,
        # not proof of a committed tool effect. approvals.sqlite remains authoritative.
        write_json(runtime.directory / "session.json", messages_to_dict(snapshot.values["messages"]))
        if resuming:
            if interrupted or snapshot.next:
                raise RuntimeError("Graph did not finish after its approval decision")
            log("answer", text=snapshot.values["messages"][-1].content)
        else:
            if not interrupted:
                raise RuntimeError("Expected a native LangGraph interrupt before booking")
            write_json(checkpoint, saved)


async def prepare(runtime, live=False, stream=False):
    await asyncio.to_thread(drive, runtime, live, stream, False)


async def resume(runtime, live=False, stream=False):
    await asyncio.to_thread(drive, runtime, live, stream, True)
