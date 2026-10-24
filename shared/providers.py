"""Provider settings stay outside prompts/checkpoints; no secret values are logged."""
import os
from pathlib import Path


def live_settings() -> tuple[str, str, str | None]:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    if os.getenv("RUN_LIVE") != "1":
        raise RuntimeError("Live model calls require RUN_LIVE=1")
    if os.getenv("DEEPSEEK_API_KEY"):
        settings = (os.getenv("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat"),
                    os.environ["DEEPSEEK_API_KEY"],
                    os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com"))
    else:
        settings = (os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                    os.getenv("OPENAI_API_KEY", ""), os.getenv("OPENAI_BASE_URL"))
    if not settings[1] or settings[1] == "...":
        raise RuntimeError("Live smoke requires a configured provider API key")
    return settings
