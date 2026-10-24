from pathlib import Path

import pytest

from shared.providers import (
    DEEPSEEK_NAMES, configure_beginner_environment, load_provider_environment, shell_literals,
)


@pytest.fixture
def config(tmp_path, monkeypatch):
    for name in (*DEEPSEEK_NAMES, "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    # Track subsequent writes too, so process credentials are restored after each test.
    for name in (*DEEPSEEK_NAMES, "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"):
        monkeypatch.setenv(name, "")
    return {"env_file": tmp_path / ".env", "shell_file": tmp_path / ".zshrc"}


def test_unexported_deepseek_settings(config, capsys, monkeypatch):
    config["shell_file"].write_text(
        'DEEPSEEK_API_KEY="test-only-secret"\n'
        "export DEEPSEEK_API_BASE_URL='https://example.invalid/v1' # comment\n"
        'DEEPSEEK_DEFAULT_MODEL="test-model"\n'
        'UNRELATED_SECRET="do-not-import"\n')
    configure_beginner_environment(**config)
    import os
    assert os.environ["OPENAI_API_KEY"] == "test-only-secret"
    assert os.environ["OPENAI_BASE_URL"] == "https://example.invalid/v1"
    assert os.environ["OPENAI_MODEL"] == "test-model"
    assert os.getenv("UNRELATED_SECRET") != "do-not-import"
    assert "test-only-secret" not in capsys.readouterr().out


def test_placeholder_env_key_allows_deepseek_fallback(config):
    config["env_file"].write_text('OPENAI_API_KEY=...\n')
    config["shell_file"].write_text('DEEPSEEK_API_KEY=test-key\n')
    configure_beginner_environment(**config)
    import os
    assert os.environ["OPENAI_API_KEY"] == "test-key"


def test_explicit_openai_does_not_select_shell_fallback(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "explicit-openai")
    config["shell_file"].write_text('DEEPSEEK_API_KEY=shell-key\n')
    configure_beginner_environment(**config)
    import os
    assert os.environ["OPENAI_API_KEY"] == "explicit-openai"
    assert not os.getenv("DEEPSEEK_API_KEY")


def test_environment_then_dotenv_then_shell(config, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "environment-key")
    # Remove empty fixture variables so dotenv can populate its lower-priority values.
    monkeypatch.delenv("DEEPSEEK_DEFAULT_MODEL")
    config["env_file"].write_text('DEEPSEEK_API_KEY=dotenv-key\nDEEPSEEK_DEFAULT_MODEL=dotenv-model\n')
    config["shell_file"].write_text('DEEPSEEK_API_KEY=shell-key\nDEEPSEEK_DEFAULT_MODEL=shell-model\n')
    configure_beginner_environment(**config)
    import os
    assert os.environ["OPENAI_API_KEY"] == "environment-key"
    assert os.environ["OPENAI_MODEL"] == "dotenv-model"


def test_dotenv_key_precedes_shell_fallback(config, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    config["env_file"].write_text('DEEPSEEK_API_KEY=dotenv-key\n')
    config["shell_file"].write_text('DEEPSEEK_API_KEY=shell-key\n')
    configure_beginner_environment(**config)
    import os
    assert os.environ["OPENAI_API_KEY"] == "dotenv-key"


def test_shell_commands_are_never_executed(config, tmp_path):
    marker = tmp_path / "unexpected"
    config["shell_file"].write_text(
        f'DEEPSEEK_API_KEY="$(touch {marker})"\n'
        'DEEPSEEK_DEFAULT_MODEL=${OTHER_MODEL}\n'
        'DEEPSEEK_API_BASE_URL=`some_command`\n')
    assert shell_literals(config["shell_file"]) == {}
    assert not marker.exists()


def test_missing_or_malformed_shell_file(config):
    assert shell_literals(config["shell_file"]) == {}
    config["shell_file"].write_text('DEEPSEEK_API_KEY="unterminated\n')
    assert shell_literals(config["shell_file"]) == {}
    load_provider_environment(**config)
