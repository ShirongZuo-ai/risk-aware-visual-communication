from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.freeze_cvc_p7_suite import build_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_p7_suite_has_deterministic_distinct_balanced_identities() -> None:
    config = json.loads((ROOT / "config" / "cvc_p7_development.json").read_text(encoding="utf-8"))
    manifest = build_manifest(enforce_preoutcome=False)
    assert manifest["category_counts"] == {category: 3 for category in "ABCD"}
    assert len({item["id"] for item in config["scenarios"]}) == 12
    assert len({item["seed"] for item in config["scenarios"]}) == 12
    assert manifest["outcome_fields_used_for_construction"] == []


def test_p7_cost_and_physical_rule_are_frozen() -> None:
    config = json.loads((ROOT / "config" / "cvc_p7_development.json").read_text(encoding="utf-8"))
    baseline = config["frozen_p6_baseline"]
    assert baseline["packet_count"] * baseline["packet_bytes"] == baseline["episode_wire_bytes"] == 72000
    assert config["physical_safety_window"] == {
        "clearance_threshold_m": .12,
        "future_horizon_steps": 63,
        "justification": config["physical_safety_window"]["justification"],
    }


def test_suite_cannot_be_newly_frozen_after_comparative_outcomes() -> None:
    with pytest.raises(RuntimeError, match="comparative outcomes already exist"):
        build_manifest(enforce_preoutcome=True)
