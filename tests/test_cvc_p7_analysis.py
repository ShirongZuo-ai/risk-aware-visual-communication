from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_cvc_p7 import historical_p6_tradeoff, median_or_none


ROOT = Path(__file__).resolve().parents[1]


def test_historical_tradeoff_reconstructs_fixed_schedule_different_pairs() -> None:
    result = historical_p6_tradeoff()
    assert result["schedule_different_count"] == 3
    assert result["schedule_different_all_gain_progress"]
    assert result["schedule_different_all_lose_clearance"]
    assert result["schedule_different_all_turn_toward_component_at_a1_spend"]


def test_diagnostic_replay_is_deterministic() -> None:
    assert historical_p6_tradeoff() == historical_p6_tradeoff()
    assert median_or_none([None, 1, 3]) == 2


def test_frozen_matrix_reconciles_exact_bytes_without_physical_window_support() -> None:
    matrix = json.loads((ROOT / "results" / "cvc_p7_webots" / "matrix_summary.json").read_text(encoding="utf-8"))
    assert len(matrix["runs"]) == 36
    assert all(row["wire_bytes"] == 72000 and row["byte_reconciliation"] for row in matrix["runs"])
    analysis = json.loads((ROOT / "results" / "cvc_p7_analysis" / "mechanistic_analysis.json").read_text(encoding="utf-8"))
    assert analysis["suite_support"]["a1_physical_danger_cells"] == 0
    assert analysis["feature_discrimination"]["status"] == "not_estimable"
    assert analysis["classification"] == "CASE D"
