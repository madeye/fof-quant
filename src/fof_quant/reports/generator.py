from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from fof_quant.config import AppConfig
from fof_quant.env import llm_env
from fof_quant.reports.llm import optional_explanation
from fof_quant.reports.xlsx import SheetRows, write_xlsx


@dataclass(frozen=True)
class ReportBundle:
    excel_path: Path
    html_path: Path


class ReportGenerator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def generate(self) -> ReportBundle:
        output_dir = self.config.reports.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = self._summary()
        explanation = optional_explanation(
            enabled=self.config.reports.llm_explanations,
            env=llm_env(),
            summary=summary,
        )
        excel_path = output_dir / "fof_quant_report.xlsx"
        html_path = output_dir / "fof_quant_report.html"
        write_xlsx(excel_path, self._sheets(summary, explanation))
        html_path.write_text(self._html(summary, explanation), encoding="utf-8")
        return ReportBundle(excel_path=excel_path, html_path=html_path)

    def _summary(self) -> dict[str, object]:
        return {
            "project": self.config.project.name,
            "provider": self.config.data.provider,
            "start_date": self.config.data.start_date.isoformat(),
            "end_date": self.config.data.end_date.isoformat() if self.config.data.end_date else "",
            "benchmark": self.config.strategy.benchmark,
            "cash_buffer": self.config.strategy.cash_buffer,
            "max_weight": self.config.strategy.max_weight,
            "min_holdings": self.config.strategy.min_holdings,
            "llm_explanations": self.config.reports.llm_explanations,
        }

    def _sheets(self, summary: dict[str, object], explanation: str) -> dict[str, SheetRows]:
        rows: SheetRows = [["Field", "Value"]]
        rows.extend([[key, str(value)] for key, value in summary.items()])
        return {
            "Summary": rows,
            "Risk Notes": [
                ["Topic", "Note"],
                ["LLM", "Narrative only; not used for scores, weights, or backtests."],
                ["Data", "Holdings and index weights must be point-in-time."],
                ["Explanation", explanation],
            ],
        }

    def _html(self, summary: dict[str, object], explanation: str) -> str:
        rows = "\n".join(
            f"<tr><th>{escape(key)}</th><td>{escape(str(value))}</td></tr>"
            for key, value in summary.items()
        )
        explanation_html = escape(explanation or "LLM explanations disabled or not configured.")
        return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>fof-quant report</title></head>
<body>
<h1>ETF FOF Report</h1>
<h2>Configuration</h2>
<table>{rows}</table>
<h2>Risk Notes</h2>
<p>LLM text is narrative assistance only and never feeds scores, weights, or backtests.</p>
<h2>LLM Explanation</h2>
<pre>{explanation_html}</pre>
</body>
</html>
"""
