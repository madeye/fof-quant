from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from fof_quant.env import LLMEnv

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExplanationPrompt:
    system: str
    user: str


def build_explanation_prompt(summary: dict[str, object]) -> ExplanationPrompt:
    """Generic prompt for legacy callers (kept for backwards compatibility)."""
    return ExplanationPrompt(
        system=(
            "You explain ETF FOF research outputs. Do not provide investment advice. "
            "Do not change scores, weights, or backtest metrics."
        ),
        user=(
            "Summarize the factor drivers, allocation changes, and key risks for this "
            f"deterministic run:\n{json.dumps(summary, ensure_ascii=False, sort_keys=True)}"
        ),
    )


def build_broad_index_prompt(payload: dict[str, object]) -> ExplanationPrompt:
    """Build a Chinese-language prompt for a broad-index pipeline run.
    payload is the JSON manifest already produced (config, sleeve picks,
    target plan, rebalance lines, optionally backtest metrics + attribution).
    """
    return ExplanationPrompt(
        system=(
            "你是一位中文 ETF FOF 研究报告解读员。"
            "你的任务是基于已经计算好的确定性数据，写一段简洁的中文解读，"
            "覆盖：(1) 当前持仓与目标的偏离情况；(2) 各 sleeve 的贡献与效率；"
            "(3) 主要风险与建议关注点。"
            "你不能改写任何数值，不能提供投资建议，不能给出价格预测，"
            "不要重复表格里的所有原始数字，只要给出有洞察的总结。"
            "回答控制在 250 字以内，使用 Markdown，分小标题。"
        ),
        user=(
            "以下是一次确定性运行的结果，请基于此撰写解读：\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)
        ),
    )


def optional_explanation(*, enabled: bool, env: LLMEnv, summary: dict[str, object]) -> str:
    """Backwards-compat shim used by the legacy ReportGenerator."""
    if not enabled or not env.configured:
        return ""
    prompt = build_explanation_prompt(summary)
    return _call_llm(env, prompt)


def explain_broad_index(
    *,
    enabled: bool,
    env: LLMEnv,
    payload: dict[str, object],
) -> str:
    if not enabled:
        return ""
    if not env.configured:
        return "(LLM_API_KEY not set; skipped narrative.)"
    prompt = build_broad_index_prompt(payload)
    return _call_llm(env, prompt)


def _call_llm(env: LLMEnv, prompt: ExplanationPrompt) -> str:
    try:
        if env.provider in ("openai", "custom"):
            return _call_openai(env, prompt)
        return _call_anthropic(env, prompt)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        logger.warning("LLM call failed: %s", exc)
        return f"(LLM call failed: {type(exc).__name__}; narrative skipped.)"


def _call_openai(env: LLMEnv, prompt: ExplanationPrompt) -> str:
    body: dict[str, Any] = {
        "model": env.model,
        "messages": [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        "temperature": 0.3,
        "max_tokens": 800,
    }
    base = env.api_base.rstrip("/")
    response = _post_json(
        f"{base}/chat/completions",
        body,
        headers={
            "Authorization": f"Bearer {env.api_key}",
            "Content-Type": "application/json",
        },
    )
    choices = response.get("choices") or []
    if not choices:
        raise ValueError(f"LLM returned no choices: {response}")
    return str(choices[0].get("message", {}).get("content", "")).strip()


def _call_anthropic(env: LLMEnv, prompt: ExplanationPrompt) -> str:
    body: dict[str, Any] = {
        "model": env.model,
        "max_tokens": 800,
        "system": prompt.system,
        "messages": [{"role": "user", "content": prompt.user}],
        "temperature": 0.3,
    }
    base = env.api_base.rstrip("/")
    response = _post_json(
        f"{base}/v1/messages",
        body,
        headers={
            "x-api-key": env.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    content = response.get("content") or []
    parts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
    return "".join(parts).strip()


def _post_json(
    url: str,
    body: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError(f"refusing to call non-http(s) URL: {url}")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for key, value in headers.items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310 - configured base URL
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"LLM response was not a JSON object: {raw[:200]}")
    return parsed


def _json_default(value: object) -> object:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Cannot JSON-encode {type(value).__name__}")
