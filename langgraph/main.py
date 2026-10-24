"""A short model -> tool -> model weather graph."""
import os
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.providers import configure_beginner_environment

calls: list[str] = []


@tool
def get_weather(city: str) -> str:
    """Return mock weather for the requested city, never live weather."""
    print(f"[tool.call] get_weather(city={city!r})", flush=True)
    result = f"{city}: sunny, 22 C (mock data)."
    calls.append(city)
    print(f"[tool.return] {result}", flush=True)
    return result


def build_graph(model):
    def ask(state):
        used_tool = any(isinstance(m, ToolMessage) for m in state["messages"])
        client = model if used_tool else model.bind_tools([get_weather], tool_choice="required")
        return {"messages": [client.invoke(state["messages"])]}

    graph = StateGraph(MessagesState)
    graph.add_node("model", ask)
    graph.add_node("tools", ToolNode([get_weather]))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "model")
    return graph.compile()


def main() -> None:
    configure_beginner_environment()
    message = " ".join(sys.argv[1:]) or "What is the weather in Shanghai?"
    print(f"[user] {message}", flush=True)
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "...":
        raise SystemExit("Configure a provider key in the environment, root .env, or ~/.zshrc.")
    calls.clear()
    model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=60, max_retries=1,
        extra_body={"thinking": {"type": "disabled"}} if os.getenv("DEEPSEEK_API_KEY") else {})
    result = build_graph(model).invoke({"messages": [
        SystemMessage(content="Call get_weather, then answer in English and identify mock data."),
        HumanMessage(content=message),
    ]}, config={"recursion_limit": 6})
    if not calls:
        raise RuntimeError("The model skipped get_weather; this run did not pass.")
    print(f"[final] {result['messages'][-1].content}", flush=True)


if __name__ == "__main__":
    main()
