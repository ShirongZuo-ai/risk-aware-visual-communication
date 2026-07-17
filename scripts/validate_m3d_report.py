"""Validate Milestone 3D generated artifacts and report."""

from __future__ import annotations

import csv
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from m3d_world_risk_common import (  # noqa: E402
    OUTPUT_DIR,
    SENSITIVITY_CSV,
    SUMMARY_CSV,
    SUMMARY_JSON,
    TRAJECTORY_CSV,
    evaluate_all,
)


REPORT = PROJECT_ROOT / "docs" / "m3_world_risk_validation_report.md"
SUCCESS_CSV = PROJECT_ROOT / "data" / "logs" / "m3" / "risk_validation_episode_0002.csv"
FIGURES = (
    "world_risk_overview.png",
    "planned_vs_state_risk.png",
    "risk_decomposition_planned.png",
    "risk_decomposition_state.png",
    "early_vs_late_conflict.png",
    "clearance_risk_curve.png",
    "trajectory_disagreement_over_time.png",
    "parameter_sensitivity.png",
)
REQUIRED_REPORT_HEADINGS = (
    "## 1. Research Purpose",
    "## 2. Successful Episode",
    "## 3. Rejected Calibration Episode",
    "## 4. Analysis Snapshot",
    "## 5. Trajectory Generation",
    "## 6. Data-Leakage Protection",
    "## 7. Trajectory Disagreement",
    "## 8. Corridor Radius",
    "## 9. Obstacles",
    "## 10. Obstacle Risk Results",
    "## 11. EARLY vs LATE",
    "## 12. Planned and State Dominance",
    "## 13. NEAR_BOUNDARY",
    "## 14. OUTSIDE_BOTH",
    "## 15. Formula Recalculation",
    "## 16. Parameter Sensitivity",
    "## 17. Milestone 3 Acceptance",
    "## 18. GUI Human Acceptance",
    "## 19. Known Limitations",
    "## 20. Why Camera Projection Comes Next",
)
FORBIDDEN_REPORT_PHRASES = (
    "collision probability",
    "calibrated probability",
    "guaranteed safety",
)
FORBIDDEN_CODE_TOKENS = (
    "future_actual",
    "actual_future",
    "future_x",
    "future_y",
    "future_yaw",
    "future_velocity",
)


def fail(message: str) -> None:
    raise AssertionError(message)


def ensure_exists(path: Path) -> None:
    if not path.exists():
        fail(f"missing required artifact: {path}")


def is_ignored(path: Path) -> bool:
    import subprocess

    result = subprocess.run(
        ["C:\\Program Files\\Git\\cmd\\git.exe", "check-ignore", "-q", str(path)],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode == 0


def validate_generated_artifacts() -> None:
    for path in (SUCCESS_CSV, TRAJECTORY_CSV, SUMMARY_CSV, SUMMARY_JSON, SENSITIVITY_CSV):
        ensure_exists(path)
    for figure in FIGURES:
        path = OUTPUT_DIR / figure
        ensure_exists(path)
        if path.stat().st_size <= 0:
            fail(f"empty figure: {path}")
    if not is_ignored(TRAJECTORY_CSV):
        fail("trajectory CSV is not ignored by Git")
    if not is_ignored(OUTPUT_DIR / FIGURES[0]):
        fail("results figures are not ignored by Git")


def validate_sensitivity() -> None:
    with SENSITIVITY_CSV.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 9:
        fail("parameter sensitivity must contain 9 rows")
    if not all(row["all_key_checks_pass"] == "True" for row in rows):
        fail("not all parameter sensitivity checks pass")


def validate_report_text() -> None:
    ensure_exists(REPORT)
    text = REPORT.read_text(encoding="utf-8")
    for heading in REQUIRED_REPORT_HEADINGS:
        if heading not in text:
            fail(f"missing report section: {heading}")
    lowered = text.lower()
    for phrase in FORBIDDEN_REPORT_PHRASES:
        if phrase in lowered:
            fail(f"forbidden phrase in report: {phrase}")
    if "risk_validation_episode_0002.csv" not in text:
        fail("report does not cite accepted episode_0002")
    if "risk_validation_episode_0001.csv" not in text:
        fail("report does not explain rejected episode_0001")
    if "GUI validation: pending user confirmation" not in text:
        fail("report must keep GUI validation pending")


def validate_no_forbidden_scope() -> None:
    source_paths = [
        PROJECT_ROOT / "scripts" / "m3d_world_risk_common.py",
        PROJECT_ROOT / "scripts" / "evaluate_m3d_world_risk.py",
        PROJECT_ROOT / "scripts" / "plot_m3d_world_risk.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    for token in FORBIDDEN_CODE_TOKENS:
        if token in combined:
            fail(f"forbidden future-actual token in M3D scripts: {token}")
    forbidden_names = ["camera_projection", "risk_heatmap", "roi_compression", "dynamic_obstacle", "machine_learning"]
    tracked_or_untracked = [str(path).lower() for path in PROJECT_ROOT.rglob("*") if ".git" not in path.parts]
    for name in forbidden_names:
        if any(name in path for path in tracked_or_untracked):
            fail(f"forbidden scope artifact found: {name}")


def main() -> int:
    evaluate_all()
    validate_generated_artifacts()
    validate_sensitivity()
    validate_report_text()
    validate_no_forbidden_scope()
    print("OK: M3D report and generated artifacts validated")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
