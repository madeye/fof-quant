"""LLM-assisted parameter suggestion for the new-run form.

The user types a natural-language description ("低波防守仓 5 年回测，1bp 成本"),
the LLM returns a strict JSON object that validates against
``BroadIndexBacktestParams``, and the frontend pre-fills the form. The user
always reviews and submits — the LLM never bypasses the regular run path.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import date
from typing import Any

from pydantic import ValidationError

from fof_quant.env import LLMEnv
from fof_quant.web.schemas import BroadIndexBacktestParams

logger = logging.getLogger(__name__)


SLEEVE_LABELS: tuple[str, ...] = (
    "上证50",
    "沪深300",
    "中证500",
    "中证A500",
    "中证1000",
    "创业板指",
    "科创50",
    "中证红利低波",
)


class LLMSuggestionError(RuntimeError):
    """Raised when the LLM cannot produce a valid suggestion."""


def suggest_backtest_params(
    *,
    env: LLMEnv,
    user_prompt: str,
    today: date | None = None,
) -> BroadIndexBacktestParams:
    """Ask the configured LLM to fill BroadIndexBacktestParams from text.

    Returns a validated Pydantic model. Raises LLMSuggestionError on auth /
    network / schema-validation failures so the route can surface a clean
    HTTP error.
    """
    if not env.configured:
        raise LLMSuggestionError("LLM 未配置：请先在 .env 中设置 LLM_API_KEY 等变量。")
    user_prompt = user_prompt.strip()
    if not user_prompt:
        raise LLMSuggestionError("请填写实验描述。")

    today_iso = (today or date.today()).isoformat()
    system = _system_prompt(today_iso)
    user = f"用户描述：{user_prompt}\n\n请只返回 JSON，不要任何额外说明。"
    raw = _call_json_llm(env, system, user)
    payload = _extract_json_object(raw)
    try:
        params = BroadIndexBacktestParams.model_validate(payload)
    except ValidationError as exc:
        raise LLMSuggestionError(
            f"LLM 返回的参数不符合 schema：{exc.errors()[:3]}"
        ) from exc
    _validate_business_rules(params)
    return params


def _system_prompt(today_iso: str) -> str:
    schema = json.dumps(
        BroadIndexBacktestParams.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )
    sleeves = "、".join(SLEEVE_LABELS)
    return (
        "你是一位 ETF FOF 研究助手，负责把用户的中文/英文实验描述转换为一组宽基 ETF 回测参数。"
        f"今天是 {today_iso}。\n\n"
        "你必须只输出一个 JSON 对象，不要 Markdown 代码块、不要解释、不要前后空行。\n"
        "JSON 必须严格符合下面的 Pydantic schema：\n"
        f"```json\n{schema}\n```\n\n"
        "字段说明：\n"
        "- start_date / end_date: ISO 日期 (yyyy-mm-dd)；end_date 不晚于今天，"
        "start_date 距今至少 1 年（产生有意义的回测）。\n"
        "- initial_cash: 默认 1000000；不要超过 1e9。\n"
        f"- sleeve_weights: 板块权重映射，键必须来自 [{sleeves}]，"
        "值为 0~1 的浮点数；所有权重之和加上 cash_buffer "
        "应等于或略小于 1（系统会自动处理剩余现金）。\n"
        "- cash_buffer: 默认 0.01。max_weight: 单只 ETF 上限，默认 0.4。\n"
        "- abs_band_pp: 绝对偏离触发再平衡的 pp 阈值，默认 1.0。"
        "rel_band_pct: 相对偏离百分比阈值，默认 25.0。\n"
        "- transaction_cost_bps / slippage_bps: 一般 1~5 bps。\n"
        "- benchmark_label: 默认 \"沪深300\"，可改为 \"中证A500\" 等。\n"
        "- label: 一句中文标题，简洁概括用户意图（10 字以内）。\n\n"
        "如果用户没说时间区间，默认用 (今天-3年, 今天)。如果用户没说板块，"
        "默认 30% 中证A500、15% 中证1000、10% 创业板指、10% 科创50、35% 中证红利低波。"
    )


def _call_json_llm(env: LLMEnv, system: str, user: str) -> str:
    try:
        if env.provider in ("openai", "custom"):
            return _call_openai_json(env, system, user)
        return _call_anthropic_json(env, system, user)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        logger.warning("LLM suggestion failed: %s", exc)
        raise LLMSuggestionError(f"LLM 调用失败：{type(exc).__name__}") from exc


def _call_openai_json(env: LLMEnv, system: str, user: str) -> str:
    body: dict[str, Any] = {
        "model": env.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
        "response_format": {"type": "json_object"},
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
        raise ValueError(f"LLM returned no choices: {str(response)[:200]}")
    return str(choices[0].get("message", {}).get("content", "")).strip()


def _call_anthropic_json(env: LLMEnv, system: str, user: str) -> str:
    body: dict[str, Any] = {
        "model": env.model,
        "max_tokens": 600,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "temperature": 0.2,
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
    timeout_seconds: float = 30.0,
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


def _extract_json_object(text: str) -> dict[str, Any]:
    """LLMs sometimes wrap JSON in code fences despite instructions; be lenient.

    Strip common wrappers and return the first parseable JSON object.
    """
    if not text:
        raise LLMSuggestionError("LLM 返回为空。")
    cleaned = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMSuggestionError(f"无法解析 LLM 返回的 JSON：{exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise LLMSuggestionError("LLM 返回的不是 JSON 对象。")
    return parsed


def _validate_business_rules(params: BroadIndexBacktestParams) -> None:
    if params.sleeve_weights is not None:
        unknown = sorted(set(params.sleeve_weights) - set(SLEEVE_LABELS))
        if unknown:
            raise LLMSuggestionError(f"未知板块名称：{unknown}")
        total = sum(max(w, 0.0) for w in params.sleeve_weights.values())
        if total > 1.0 + 1e-6:
            raise LLMSuggestionError(f"sleeve_weights 总和 {total:.4f} 超过 1。")
    try:
        start = date.fromisoformat(params.start_date)
        end = date.fromisoformat(params.end_date)
    except ValueError as exc:
        raise LLMSuggestionError(f"日期格式无效：{exc}") from exc
    if start >= end:
        raise LLMSuggestionError("start_date 必须早于 end_date。")
