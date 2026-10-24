from shared.dependencies import AppDeps, WeatherClient
from shared.runtime import ToolRuntime


def test_mock_client_cache_and_per_run_isolation(capsys):
    first, second = AppDeps(), AppDeps()
    assert first.weather is not second.weather
    first.weather.cache["Beijing"] = "Injected cache result (mock)."
    assert first.read_weather("Beijing") == "Injected cache result (mock)."
    assert first.weather.calls == ["Beijing"]
    assert second.weather.calls == [] and second.weather.cache == {}
    assert "[deps.weather]" in capsys.readouterr().out


def test_approval_runtime_uses_injected_client(tmp_path):
    client = WeatherClient(cache={"Shanghai": "Injected runtime weather (mock)."})
    runtime = ToolRuntime(tmp_path, "op", "Shanghai", weather=client)
    deps = AppDeps.for_runtime(runtime)
    assert deps.weather is client
    assert deps.read_weather("Shanghai") == "Injected runtime weather (mock)."
    assert client.calls == ["Shanghai"]
    assert runtime.effect_count() == 0
