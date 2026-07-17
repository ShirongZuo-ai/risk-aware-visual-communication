"""Evaluate Milestone 3D world-coordinate risk diagnostics."""

from __future__ import annotations

from m3d_world_risk_common import (
    SENSITIVITY_CSV,
    SUMMARY_CSV,
    SUMMARY_JSON,
    TRAJECTORY_CSV,
    evaluate_all,
    write_sensitivity_csv,
    write_summary_files,
    write_trajectory_csv,
)


def main() -> int:
    rows, trajectories, summary, sensitivity = evaluate_all()
    write_trajectory_csv(trajectories)
    write_summary_files(summary)
    write_sensitivity_csv(sensitivity)
    print(f"OK: M3D evaluated {len(rows)} obstacles")
    print(f"OK: wrote {TRAJECTORY_CSV}")
    print(f"OK: wrote {SUMMARY_CSV}")
    print(f"OK: wrote {SUMMARY_JSON}")
    print(f"OK: wrote {SENSITIVITY_CSV}")
    print(f"OK: max_disagreement_m={trajectories.max_disagreement_m:.9f}")
    print("M3_ROLE_ACCEPTANCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
