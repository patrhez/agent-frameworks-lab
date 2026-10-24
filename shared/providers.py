"""Provider settings stay outside prompts/checkpoints; no secret values are logged."""
import os
from pathlib import Path
import re
import shlex

DEEPSEEK_NAMES = ("DEEPSEEK_API_KEY", "DEEPSEEK_API_BASE_URL", "DEEPSEEK_DEFAULT_MODEL")


def usable(value: str | None) -> bool:
    return bool(value and value.strip() and value.strip() != "...")


def shell_literals(path: Path) -> dict[str, str]:
    """Read only allowed literal assignments; never source scripts or expand commands."""
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"\s*(?:export\s+)?(" + "|".join(DEEPSEEK_NAMES) + r")=(.*)", line)
        if not match:
            continue
        name, expression = match.groups()
        try:
            parts = shlex.split(expression, comments=True)
        except ValueError:
            values.pop(name, None)
            continue
        # Computed or multiline shell values must be explicitly exported instead.
        if len(parts) != 1 or any(char in parts[0] for char in ("$", "`", "\n")):
            values.pop(name, None)
            continue
        values[name] = parts[0]
    return values


def load_provider_environment(env_file: Path | None = None, shell_file: Path | None = None) -> None:
    """Environment > root .env > allowed ~/.zshrc literals. Explicit OpenAI wins fallback."""
    from dotenv import load_dotenv
    load_dotenv(env_file if env_file is not None else Path(__file__).resolve().parents[1] / ".env")
    if usable(os.getenv("OPENAI_API_KEY")) and not usable(os.getenv("DEEPSEEK_API_KEY")):
        return
    values = shell_literals(shell_file if shell_file is not None else Path.home() / ".zshrc")
    for name, value in values.items():
        if not usable(os.getenv(name)) and usable(value):
            os.environ[name] = value


def configure_beginner_environment(**paths) -> None:
    """Map DeepSeek credentials to OpenAI-compatible client settings, never to prompts."""
    load_provider_environment(**paths)
    if usable(os.getenv("DEEPSEEK_API_KEY")):
        os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
        os.environ["OPENAI_BASE_URL"] = os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com")
        os.environ["OPENAI_MODEL"] = os.getenv("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat")


def live_settings() -> tuple[str, str, str | None]:
    if os.getenv("RUN_LIVE") != "1":
        raise RuntimeError("Live model calls require RUN_LIVE=1")
    load_provider_environment()
    if usable(os.getenv("DEEPSEEK_API_KEY")):
        settings = (os.getenv("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat"),
                    os.environ["DEEPSEEK_API_KEY"],
                    os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com"))
    else:
        settings = (os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                    os.getenv("OPENAI_API_KEY", ""), os.getenv("OPENAI_BASE_URL"))
    if not settings[1] or settings[1] == "...":
        raise RuntimeError("Live smoke requires a configured provider API key")
    return settings
