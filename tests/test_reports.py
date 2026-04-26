from pathlib import Path
from zipfile import ZipFile

from fof_quant.config import load_config
from fof_quant.env import LLMEnv
from fof_quant.reports.generator import ReportGenerator
from fof_quant.reports.llm import build_explanation_prompt, optional_explanation


def test_report_generator_writes_excel_and_html(tmp_path: Path) -> None:
    config_text = Path("configs/example.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "reports"
    config_path.write_text(
        config_text.replace("output_dir: reports", f"output_dir: {output_dir}"),
        encoding="utf-8",
    )

    bundle = ReportGenerator(load_config(config_path)).generate()

    assert bundle.excel_path.exists()
    assert bundle.html_path.exists()
    assert "ETF FOF Report" in bundle.html_path.read_text(encoding="utf-8")
    with ZipFile(bundle.excel_path) as archive:
        assert "xl/workbook.xml" in archive.namelist()


def test_llm_prompt_is_narrative_only() -> None:
    prompt = build_explanation_prompt({"score": 1.0})

    assert "Do not change scores" in prompt.system
    assert "deterministic run" in prompt.user


def test_optional_explanation_requires_enabled_and_configured_env() -> None:
    env = LLMEnv(provider="minimax", api_key="", api_base="", model="MiniMax-M2.5")

    assert optional_explanation(enabled=True, env=env, summary={}) == ""
