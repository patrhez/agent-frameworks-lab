"""Mock only the chat provider; graph nodes, routing, interrupts and tools stay real."""
import os

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI

from shared.providers import live_settings


class ScriptChatModel(BaseChatModel):
    city: str
    reviewer: bool = False

    @property
    def _llm_type(self):
        return "offline-travel-provider"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        results = [m for m in messages if isinstance(m, ToolMessage)]
        if self.reviewer:
            message = AIMessage(content=f"Mock travel outcome: {results[-1].content}")
        else:
            name = "book_flight" if any(m.name == "get_weather" for m in results) else "get_weather"
            message = AIMessage(content="", tool_calls=[{
                "name": name, "args": {"city": self.city}, "id": f"call_{name}", "type": "tool_call",
            }])
        return ChatResult(generations=[ChatGeneration(message=message)])


def chat_model(city: str, live=False, reviewer=False):
    if not live:
        return ScriptChatModel(city=city, reviewer=reviewer)
    name, key, base = live_settings()
    return ChatOpenAI(model=name, api_key=key, base_url=base, timeout=60, max_retries=1,
        extra_body={"thinking": {"type": "disabled"}} if os.getenv("DEEPSEEK_API_KEY") else {})
