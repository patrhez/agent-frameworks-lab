"""Per-run mock services; no HTTP clients, credentials, or global singletons."""
from dataclasses import dataclass, field
from typing import Any

from .logging_util import log
from .tools_mock import get_weather, validate_city


@dataclass
class WeatherClient:
    """A replaceable in-memory weather/cache dependency, never a network client."""
    calls: list[str] = field(default_factory=list)
    cache: dict[str, str] = field(default_factory=dict)

    def get(self, city: str) -> str:
        city = validate_city(city)
        self.calls.append(city)
        log("deps.weather", city=city, cache_hit=city in self.cache)
        if city not in self.cache:
            self.cache[city] = get_weather(city)
        return self.cache[city]


@dataclass
class AppDeps:
    weather: WeatherClient = field(default_factory=WeatherClient)
    runtime: Any = field(default=None, repr=False)

    @classmethod
    def for_runtime(cls, runtime):
        return cls(weather=runtime.weather_client, runtime=runtime)

    def require_runtime(self):
        if self.runtime is None:
            raise RuntimeError("This tool requires an injected approval runtime")
        return self.runtime

    def read_weather(self, city: str) -> str:
        if self.runtime is not None:
            return self.runtime.weather(city, client=self.weather)
        log("tool.call", tool="get_weather", city=city)
        result = self.weather.get(city)
        log("tool.return", tool="get_weather", result=result)
        return result
