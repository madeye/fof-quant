import json
from pathlib import Path

from fof_quant.config import load_config
from fof_quant.pipeline import run_offline_pipeline


def test_offline_pipeline_writes_manifest(tmp_path: Path) -> None:
    config_text = Path("configs/example.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "reports"
    config_path.write_text(
        config_text.replace("output_dir: reports", f"output_dir: {output_dir}"),
        encoding="utf-8",
    )

    artifacts = run_offline_pipeline(load_config(config_path))
    manifest = Path(artifacts["manifest"])

    assert manifest.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert "html_report" in payload["artifacts"]
    assert Path(payload["artifacts"]["html_report"]).exists()
