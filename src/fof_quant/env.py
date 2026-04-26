from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

LLMProvider = Literal["openai", "claude", "minimax", "kimi", "custom"]

_LLM_DEFAULTS: dict[LLMProvider, tuple[str, str, str]] = {
    "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
    "claude": ("ANTHROPIC_API_KEY", "https://api.anthropic.com", "claude-sonnet-4-6"),
    "minimax": ("MINIMAX_API_KEY", "https://api.minimaxi.com/anthropic", "MiniMax-M2.5"),
    "kimi": ("MOONSHOT_API_KEY", "https://api.kimi.com/coding", "kimi-k2.5"),
    "custom": ("LLM_API_KEY", "", ""),
}


@dataclass(frozen=True)
class LLMEnv:
    provider: LLMProvider
    api_key: str
    api_base: str
    model: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


def load_env_file(path: Path = Path(".env"), *, override: bool = False) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_optional_quotes(value.strip())
        if key and (override or key not in os.environ):
            os.environ[key] = value


def tushare_token() -> str:
    load_env_file()
    return os.environ.get("TUSHARE_TOKEN", "")


def llm_env() -> LLMEnv:
    load_env_file()
    provider = _provider_from_env(os.environ.get("LLM_PROVIDER", "openai"))
    provider_key, default_base, default_model = _LLM_DEFAULTS[provider]
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get(provider_key, "")
    api_base = os.environ.get("LLM_API_BASE") or default_base
    model = os.environ.get("LLM_MODEL") or default_model
    return LLMEnv(provider=provider, api_key=api_key, api_base=api_base, model=model)


def _provider_from_env(value: str) -> LLMProvider:
    normalized = value.strip().lower()
    if normalized in _LLM_DEFAULTS:
        return normalized
    return "custom"


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
