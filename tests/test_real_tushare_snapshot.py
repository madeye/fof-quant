import json
from pathlib import Path

from fof_quant.data.datasets import dataset_spec
from fof_quant.data.normalization import normalize_rows

FIXTURE = Path("tests/fixtures/tushare/fund_daily_510300_20240102_20240105.json")


def test_real_tushare_fund_daily_snapshot_normalizes() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    table = normalize_rows(dataset_spec("etf_daily"), payload["rows"])

    assert table.dataset == "etf_daily"
    assert [row["trade_date"] for row in table.rows] == [
        "20240102",
        "20240103",
        "20240104",
        "20240105",
    ]
    assert table.rows[0]["ts_code"] == "510300.SH"
    assert table.rows[0]["close"] == 3.453
    assert table.rows[-1]["amount"] == 5796964.474
