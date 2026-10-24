from shared.dependencies import AppDeps, WeatherClient
from tools_injected import WeatherTool


def test_tool_model_fields_inject_mock_dependencies(capsys):
    first = AppDeps(weather=WeatherClient(cache={"Beijing": "First mock dependency."}))
    second = AppDeps(weather=WeatherClient(cache={"Beijing": "Second mock dependency."}))
    first_tool, second_tool = WeatherTool(deps=first), WeatherTool(deps=second)
    assert first_tool.run(city="Beijing") == "First mock dependency."
    assert second.weather.calls == []
    assert second_tool.run(city="Beijing") == "Second mock dependency."
    assert first.weather.calls == second.weather.calls == ["Beijing"]
    assert "deps" not in first_tool.model_dump()
    assert set(first_tool.args_schema.model_fields) == {"city"}
    assert "[deps.weather]" in capsys.readouterr().out
