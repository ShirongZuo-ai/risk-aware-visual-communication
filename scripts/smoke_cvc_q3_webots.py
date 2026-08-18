"""Pre-freeze Q3 adapter smoke on a non-support, obstacle-free fixture."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "simulator" / "worlds" / "cvc_q3_runner.wbt"
OUT = ROOT / "results" / "cvc_q3_smoke"
WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")


def main() -> None:
    q3 = json.loads((ROOT / "config" / "cvc_q3_development.json").read_text(encoding="utf-8"))
    planner = json.loads((ROOT / "config" / "cvc_q1_planner_v2.json").read_text(encoding="utf-8"))
    records = []
    for policy in q3["policies"]:
        identity = f"q3-smoke-no-obstacle-{policy}"
        job = {"id": identity, "scenario": identity, "semantic": "non_support_adapter_smoke", "seed": 989930,
               "start": [-.65, 0, 0], "goal": [.65, 0], "objects": [], "duration_s": 10.0,
               "policy": policy, "jpeg_quality": q3["communication"]["jpeg_quality"],
               "packet_bytes": q3["communication"]["packet_bytes"],
               "planner": planner["planner"], "visual_geometry": planner["visual_geometry"],
               "q3": {"risk_threshold": q3["risk"]["threshold"],
                      "validity_steps": q3["scheduler"]["validity_steps"],
                      "fallback_step": q3["scheduler"]["fallback_step"],
                      "reserve_step": q3["scheduler"]["reserve_step"],
                      "u0_schedule": q3["scheduler"]["u0_schedule"],
                      "safety_decision_value_thresholds": {
                          "safe_set_contraction_fraction": q3["safety_decision_value"]["safe_set_contraction_fraction"],
                          "matched_margin_deterioration_m": q3["safety_decision_value"]["matched_margin_deterioration_m"],
                          "numerical_tolerance": q3["safety_decision_value"]["numerical_tolerance"]}}}
        for name in ("jobs", "traces", "logs"):
            (OUT / name).mkdir(parents=True, exist_ok=True)
        job_path = OUT / "jobs" / f"{identity}.json"; trace_path = OUT / "traces" / f"{identity}.jsonl"
        job_path.write_text(json.dumps(job, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        env = os.environ.copy(); env.update(CVC_CONFIG=str(job_path), CVC_OUTPUT=str(trace_path))
        process = subprocess.run([str(WEBOTS), "--batch", "--mode=fast", "--stdout", "--stderr", str(WORLD)],
                                 cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        (OUT / "logs" / f"{identity}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
        summary_path = trace_path.with_suffix(".summary.json")
        if process.returncode or not summary_path.is_file():
            raise RuntimeError(f"Q3 smoke failed for {policy}: {(process.stdout + process.stderr)[-3000:]}")
        records.append(json.loads(summary_path.read_text(encoding="utf-8")))
    result = {"development_only": True, "formal": False, "non_support_fixture": True, "records": records,
              "passed": all(row["wire_bytes"] == 72_000 and row["transmissions"] == 3 and
                            row["byte_reconciliation"] and row["mirror_all_steps_match"] and
                            not row["collision"] for row in records)}
    (OUT / "qualification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"],
                      "schedules": {row["policy"]: row["send_steps"] for row in records},
                      "runtime_max_ms": {row["policy"]: row["runtime_profile"]["communication_decision_total"]["maximum_ms"]
                                         for row in records}}, indent=2))


if __name__ == "__main__":
    main()
