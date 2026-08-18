"""Run and fit the outcome-blind Q1 inverse-bbox-height range calibration."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "simulator" / "worlds" / "cvc_q1_range_calibration.wbt"
CONTROLLER = ROOT / "simulator" / "controllers" / "cvc_q1_range_calibration" / "cvc_q1_range_calibration.py"
OUT = ROOT / "results" / "cvc_q1_range_calibration"
DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--webots", type=Path, default=DEFAULT_WEBOTS)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "range_samples.json"
    environment = __import__("os").environ.copy()
    environment["CVC_OUTPUT"] = str(raw)
    process = subprocess.run([str(args.webots), "--batch", "--mode=fast", str(WORLD)], cwd=ROOT,
                             env=environment, capture_output=True, text=True, timeout=args.timeout)
    (OUT / "webots.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    if process.returncode != 0 or not raw.exists():
        raise RuntimeError((process.stdout + process.stderr)[-3000:])
    rows = json.loads(raw.read_text(encoding="utf-8"))["rows"]
    if any(not row["detected"] or row["bbox_height_px"] < 2 for row in rows):
        raise RuntimeError("range fixture detection failed")
    x = np.asarray([[1.0 / row["bbox_height_px"], 1.0] for row in rows], dtype=float)
    y = np.asarray([row["robot_to_obstacle_center_m"] for row in rows], dtype=float)
    coefficient, intercept = np.linalg.lstsq(x, y, rcond=None)[0]
    predicted = x @ np.asarray([coefficient, intercept])
    errors = predicted - y
    uncertainty = float(np.max(np.abs(errors)) + 0.01)
    fitted = []
    for row, prediction, error in zip(rows, predicted, errors):
        fitted.append({**row, "estimated_center_range_m": float(prediction), "error_m": float(error),
                       "absolute_error_m": float(abs(error))})
    result = {
        "study_id": "cvc-q1-range-calibration-v1", "development_only": True, "formal": False,
        "navigation_outcomes_used": False, "model": "range_m = coefficient / bbox_height_px + intercept",
        "inverse_height_coefficient_m_px": float(coefficient), "intercept_m": float(intercept),
        "uncertainty_bound_m": uncertainty, "bias_m": float(np.mean(errors)),
        "mae_m": float(np.mean(np.abs(errors))), "worst_absolute_error_m": float(np.max(np.abs(errors))),
        "rmse_m": float(np.sqrt(np.mean(errors * errors))), "rows": fitted,
        "world_sha256": hashlib.sha256(WORLD.read_bytes()).hexdigest(),
        "controller_sha256": hashlib.sha256(CONTROLLER.read_bytes()).hexdigest(),
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    target = OUT / "calibration_results.json"
    target.write_text(payload, encoding="utf-8")
    target.with_suffix(".json.sha256").write_text(hashlib.sha256(payload.encode()).hexdigest() + "\n", encoding="ascii")
    print(json.dumps({key: result[key] for key in (
        "inverse_height_coefficient_m_px", "intercept_m", "uncertainty_bound_m",
        "bias_m", "mae_m", "worst_absolute_error_m", "rmse_m")}, indent=2))


if __name__ == "__main__":
    main()
