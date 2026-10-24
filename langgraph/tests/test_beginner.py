import importlib.util
from pathlib import Path

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


class WeatherModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        assert kwargs.get("tool_choice") in (None, "auto"), "Tool usage must remain model-selected"
        return self


def load_demo():
    path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("langgraph_weather_demo", path)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    return demo


def test_create_agent_dispatches_tool_and_keeps_thread_history():
    demo = load_demo()
    model = WeatherModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "get_weather", "args": {"city": "Beijing"},
                                           "id": "weather_1", "type": "tool_call"}]),
        AIMessage(content="Mock weather in Beijing is sunny at 22 C."),
        AIMessage(content="The earlier mock reading was 22 C."),
    ])
    agent = demo.build_agent(model)
    config = {"configurable": {"thread_id": "weather-test"}}
    result = agent.invoke({"messages": [HumanMessage(content="Beijing weather?")]}, config=config)
    assert demo.calls == ["Beijing"]
    assert any(isinstance(message, ToolMessage) and message.name == "get_weather"
               for message in result["messages"])
    assert "mock" in result["messages"][-1].content.lower()
    follow_up = agent.invoke({"messages": [HumanMessage(content="What temperature did you report?")]},
                             config=config)
    assert len([m for m in follow_up["messages"] if isinstance(m, HumanMessage)]) == 2
    assert any(isinstance(m, ToolMessage) for m in follow_up["messages"])
    assert demo.calls == ["Beijing"]


def test_create_agent_can_reply_without_calling_tools():
    demo = load_demo()
    agent = demo.build_agent(WeatherModel(responses=[AIMessage(content="Hello!")]))
    result = agent.invoke({"messages": [HumanMessage(content="Hello!")]},
                          config={"configurable": {"thread_id": "greeting-test"}})
    assert result["messages"][-1].content == "Hello!"
    assert not any(isinstance(message, ToolMessage) for message in result["messages"])
    assert demo.calls == []
