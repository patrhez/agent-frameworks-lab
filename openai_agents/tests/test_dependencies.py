import asyncio
import importlib.util
from pathlib import Path

from agents import Agent, Model, ModelResponse, Runner, Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from shared.dependencies import AppDeps, WeatherClient


class WeatherModel(Model):
    async def get_response(self, system_instructions, input, *args, **kwargs):
        completed = [item for item in input if item.get("type") == "function_call_output"]
        if completed:
            output = [ResponseOutputMessage(id="final", role="assistant", type="message", status="completed",
                content=[ResponseOutputText(type="output_text", annotations=[], text=str(completed[-1]["output"]))])]
        else:
            output = [ResponseFunctionToolCall(type="function_call", call_id="weather_1",
                name="get_weather", arguments='{"city":"Beijing"}')]
        return ModelResponse(output=output, usage=Usage(), response_id=None)

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError
        yield


def test_runner_context_injects_mock_weather(capsys):
    spec = importlib.util.spec_from_file_location("sdk_weather_demo", Path(__file__).resolve().parents[1] / "main.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    tool = demo.get_weather
    assert set(tool.params_json_schema["properties"]) == {"city"}
    agent = Agent(name="Weather", model=WeatherModel(), tools=[tool])
    first = AppDeps(weather=WeatherClient(cache={"Beijing": "First injected mock weather."}))
    second = AppDeps(weather=WeatherClient(cache={"Beijing": "Second injected mock weather."}))
    result = asyncio.run(Runner.run(agent, "Weather?", context=first))
    assert result.final_output == "First injected mock weather."
    assert first.weather.calls == ["Beijing"] and second.weather.calls == []
    result = asyncio.run(Runner.run(agent, "Weather?", context=second))
    assert result.final_output == "Second injected mock weather."
    assert second.weather.calls == ["Beijing"]
    assert "[deps.weather]" in capsys.readouterr().out
