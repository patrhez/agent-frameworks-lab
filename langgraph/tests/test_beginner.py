import importlib.util
from pathlib import Path

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage


class WeatherModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def test_weather_graph_dispatches_mock_tool():
    path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("langgraph_weather_demo", path)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    model = WeatherModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "get_weather", "args": {"city": "Beijing"},
                                           "id": "weather_1", "type": "tool_call"}]),
        AIMessage(content="Mock weather in Beijing is sunny at 22 C."),
    ])
    result = demo.build_graph(model).invoke({"messages": [HumanMessage(content="Beijing weather?")]})
    assert demo.calls == ["Beijing"]
    assert "mock" in result["messages"][-1].content.lower()
