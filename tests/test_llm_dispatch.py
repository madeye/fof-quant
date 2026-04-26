from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fof_quant.env import LLMEnv, LLMProvider
from fof_quant.reports.llm import (
    build_broad_index_prompt,
    explain_broad_index,
    optional_explanation,
)


def _env(provider: LLMProvider = "openai") -> LLMEnv:
    return LLMEnv(
        provider=provider,
        api_key="sk-test",
        api_base="https://api.example.com/v1",
        model="m",
    )


def test_explain_skips_when_disabled() -> None:
    assert explain_broad_index(enabled=False, env=_env(), payload={}) == ""


def test_explain_skips_when_no_key() -> None:
    env = LLMEnv(provider="openai", api_key="", api_base="", model="m")
    out = explain_broad_index(enabled=True, env=env, payload={})
    assert "skipped" in out.lower()


def test_optional_explanation_disabled_returns_empty() -> None:
    assert optional_explanation(enabled=False, env=_env(), summary={"a": 1}) == ""


def test_build_broad_index_prompt_includes_payload() -> None:
    prompt = build_broad_index_prompt({"sleeve_weights": {"A": 0.5}})
    assert "中文" in prompt.system
    assert "0.5" in prompt.user
    assert "确定性" in prompt.system or "确定" in prompt.system


def test_openai_dispatch_posts_to_chat_completions() -> None:
    captured: dict[str, Any] = {}

    def fake_post(
        url: str,
        body: dict[str, Any],
        *,
        headers: dict[str, str],
        timeout_seconds: float = 60.0,
    ) -> dict[str, Any]:
        captured["url"] = url
        captured["body"] = body
        captured["headers"] = headers
        return {"choices": [{"message": {"content": "test reply"}}]}

    with patch("fof_quant.reports.llm._post_json", side_effect=fake_post):
        out = explain_broad_index(enabled=True, env=_env("openai"), payload={"k": "v"})

    assert out == "test reply"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"].startswith("Bearer ")


def test_anthropic_dispatch_posts_to_messages() -> None:
    captured: dict[str, Any] = {}

    def fake_post(
        url: str,
        body: dict[str, Any],
        *,
        headers: dict[str, str],
        timeout_seconds: float = 60.0,
    ) -> dict[str, Any]:
        captured["url"] = url
        captured["headers"] = headers
        return {"content": [{"text": "hello"}, {"text": " world"}]}

    env = LLMEnv(
        provider="claude",
        api_key="sk-test",
        api_base="https://api.example.com",
        model="m",
    )
    with patch("fof_quant.reports.llm._post_json", side_effect=fake_post):
        out = explain_broad_index(enabled=True, env=env, payload={"k": "v"})

    assert out == "hello world"
    assert captured["url"].endswith("/v1/messages")
    assert captured["headers"]["x-api-key"] == "sk-test"


def test_dispatch_returns_friendly_message_on_http_error() -> None:
    import urllib.error

    def fake_post(*_: Any, **__: Any) -> dict[str, Any]:
        raise urllib.error.URLError("simulated failure")

    with patch("fof_quant.reports.llm._post_json", side_effect=fake_post):
        out = explain_broad_index(enabled=True, env=_env("openai"), payload={})

    assert "LLM call failed" in out
