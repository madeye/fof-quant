from __future__ import annotations

import json
from dataclasses import dataclass

from fof_quant.env import LLMEnv


@dataclass(frozen=True)
class ExplanationPrompt:
    system: str
    user: str


def build_explanation_prompt(summary: dict[str, object]) -> ExplanationPrompt:
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


def optional_explanation(*, enabled: bool, env: LLMEnv, summary: dict[str, object]) -> str:
    if not enabled or not env.configured:
        return ""
    prompt = build_explanation_prompt(summary)
    return (
        "LLM narrative assistance enabled. Send the prepared prompt to "
        f"{env.provider}/{env.model} outside the deterministic calculation path.\n\n"
        f"System: {prompt.system}\n\nUser: {prompt.user}"
    )
