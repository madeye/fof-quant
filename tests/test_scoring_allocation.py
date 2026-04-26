from datetime import date

import pytest

from fof_quant.allocation.engine import AllocationEngine
from fof_quant.factors.engine import FactorSnapshot
from fof_quant.scoring.engine import ScoringEngine


def test_scoring_engine_normalizes_and_scores() -> None:
    snapshots = [
        FactorSnapshot("510300.SH", date(2024, 1, 31), {"momentum": 1.0}, {}, 1, "fund"),
        FactorSnapshot("510500.SH", date(2024, 1, 31), {"momentum": 3.0}, {}, 1, "fund"),
    ]

    scores = ScoringEngine({"momentum": 2.0}).score(snapshots)

    assert [row.etf_code for row in scores] == ["510500.SH", "510300.SH"]
    assert scores[0].score == pytest.approx(2.0)
    assert scores[1].score == pytest.approx(0.0)


def test_allocation_engine_respects_basic_constraints() -> None:
    snapshots = [
        FactorSnapshot("A", date(2024, 1, 31), {"momentum": 3.0}, {}, 1, "fund"),
        FactorSnapshot("B", date(2024, 1, 31), {"momentum": 2.0}, {}, 1, "fund"),
        FactorSnapshot("C", date(2024, 1, 31), {"momentum": 1.0}, {}, 1, "fund"),
    ]
    scores = ScoringEngine({"momentum": 1.0}).score(snapshots)

    plan = AllocationEngine(min_holdings=2, max_weight=0.4, cash_buffer=0.05).allocate(scores)

    assert [row.etf_code for row in plan.holdings] == ["A", "B"]
    assert all(row.weight <= 0.4 for row in plan.holdings)
    assert plan.cash_weight == pytest.approx(0.2)
    assert all(plan.constraint_checks.values())


def test_allocation_engine_handles_no_eligible_scores() -> None:
    plan = AllocationEngine(min_holdings=2, max_weight=0.4, cash_buffer=0.05).allocate([])

    assert plan.holdings == []
    assert plan.cash_weight == 1.0
    assert plan.constraint_checks["min_holdings"] is False
