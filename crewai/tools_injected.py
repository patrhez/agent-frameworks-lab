"""CrewAI tool instances receive per-run dependencies through excluded model fields."""
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from shared.dependencies import AppDeps


class CityInput(BaseModel):
    city: str


class WeatherTool(BaseTool):
    name: str = "get_weather"
    description: str = "Read mock weather for a city using an injected mock client."
    args_schema: Type[BaseModel] = CityInput
    deps: AppDeps = Field(exclude=True, repr=False)

    def _run(self, city: str) -> str:
        return self.deps.read_weather(city)


class BookingTool(BaseTool):
    name: str = "book_flight"
    description: str = "Request a mock booking; pre-tool approval blocks unapproved effects."
    args_schema: Type[BaseModel] = CityInput
    deps: AppDeps = Field(exclude=True, repr=False)

    def _run(self, city: str) -> str:
        return self.deps.require_runtime().guarded_book(city)
