"""Fail-closed split/purpose isolation for M9 scientific evaluators."""
SCIENTIFIC_SPLITS = frozenset({"pilot", "calibration", "formal"})
ENGINEERING_PURPOSE = "fixture_validation_only"

def require_scientific_artifact(record: dict) -> None:
    if record.get("purpose") == ENGINEERING_PURPOSE or record.get("split") == "fixture_validation":
        raise PermissionError("fixture-validation artifacts are forbidden in scientific evaluation")
    if record.get("split") not in SCIENTIFIC_SPLITS:
        raise ValueError("unknown scientific split")
