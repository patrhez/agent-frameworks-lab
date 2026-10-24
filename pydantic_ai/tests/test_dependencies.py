import importlib.util
from pathlib import Path

from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from shared.dependencies import AppDeps, WeatherClient


def test_run_context_injects_mock_weather(capsys):
    spec = importlib.util.spec_from_file_location("pydantic_weather_demo", Path(__file__).resolve().parents[1] / "main.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    sentinel = "Injected Beijing weather (mock)."
    deps = AppDeps(weather=WeatherClient(cache={"Beijing": sentinel}))

    def respond(messages, info):
        returns = [part for message in messages for part in message.parts
                   if isinstance(part, ToolReturnPart)]
        if not returns:
            assert info.function_tools[0].parameters_json_schema["properties"] == {"city": {"type": "string"}}
            return ModelResponse(parts=[ToolCallPart("get_weather", {"city": "Beijing"})])
        assert returns[-1].content == sentinel
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,
            {"city": "Beijing", "answer": sentinel, "is_mock": True})])

    result = demo.build_agent(FunctionModel(respond)).run_sync("Beijing weather?", deps=deps)
    assert deps.weather.calls == ["Beijing"]
    assert result.output.answer == sentinel
    assert "[deps.weather]" in capsys.readouterr().out
