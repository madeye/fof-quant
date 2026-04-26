import os
from pathlib import Path

import pytest

from fof_quant.env import llm_env, load_env_file, tushare_token


def test_load_env_file_does_not_override_existing_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text("TUSHARE_TOKEN=from-file\n", encoding="utf-8")

    load_env_file(env_file)

    assert os.environ["TUSHARE_TOKEN"] == "from-shell"


def test_tushare_token_loads_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    (tmp_path / ".env").write_text("TUSHARE_TOKEN='token-from-file'\n", encoding="utf-8")

    assert tushare_token() == "token-from-file"


def test_llm_env_uses_provider_specific_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for key in ["LLM_PROVIDER", "LLM_API_KEY", "MINIMAX_API_KEY", "LLM_API_BASE", "LLM_MODEL"]:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "LLM_PROVIDER=minimax\nMINIMAX_API_KEY=provider-key\n",
        encoding="utf-8",
    )

    config = llm_env()

    assert config.configured is True
    assert config.provider == "minimax"
    assert config.api_key == "provider-key"
    assert config.api_base == "https://api.minimaxi.com/anthropic"
    assert config.model == "MiniMax-M2.5"
