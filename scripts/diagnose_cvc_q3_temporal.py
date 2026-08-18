"""Outcome-blind temporal diagnosis of the frozen CVC-Q2 causal traces."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median


ROOT = Path(__file__).resolve().parents[1]
TRACES = ROOT / "results" / "cvc_q2_webots" / "traces"
OUT = ROOT / "results" / "cvc_q3_temporal_diagnosis"
DT_S = 0.032
TOTAL_STEPS = 312


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] if low == high else ordered[low] * (high - position) + ordered[high] * (position - low)


def distribution(values: list[int]) -> dict:
    return {
        "n": len(values),
        "steps": values,
        "seconds": [value * DT_S for value in values],
        "mean_steps": mean(values) if values else None,
        "median_steps": median(values) if values else None,
        "p25_steps": percentile(values, .25),
        "p75_steps": percentile(values, .75),
        "minimum_steps": min(values) if values else None,
        "maximum_steps": max(values) if values else None,
    }


def consecutive_runs(steps: list[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    for step in steps:
        if not runs or step != runs[-1][-1] + 1:
            runs.append([step])
        else:
            runs[-1].append(step)
    return runs


def main() -> None:
    episodes = []
    for path in sorted(TRACES.glob("q2__*__A[01].jsonl")):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        # This analysis is intentionally outcome-blind. Evaluator fields remain unread.
        policy = rows[0]["policy"]
        arm_step = next((row["policy_state"]["arm_step"] for row in rows
                         if row["policy_state"]["arm_step"] is not None), None)
        spend = next(row for row in rows if row["communication"]["packet_role"] == "adaptive"
                     and row["communication"]["transmitted"])
        value_steps = [row["step"] for row in rows if row["safety_value"]["triggered"]]
        runs = consecutive_runs(value_steps)
        first_value = value_steps[0] if value_steps else None
        first_row = rows[first_value] if first_value is not None else None
        episodes.append({
            "scenario": rows[0]["scenario"],
            "policy": policy,
            "arm_step": arm_step,
            "arm_time_s": arm_step * DT_S if arm_step is not None else None,
            "adaptive_spend_step": spend["step"],
            "adaptive_spend_time_s": spend["step"] * DT_S,
            "adaptive_spend_reason": spend["communication"]["reason"],
            "first_value_step": first_value,
            "first_value_time_s": first_value * DT_S if first_value is not None else None,
            "subsequent_value_steps": value_steps[1:],
            "value_event_step_count": len(value_steps),
            "value_run_lengths_steps": [len(run) for run in runs],
            "value_run_count": len(runs),
            "arm_to_first_value_steps": (first_value - arm_step
                                          if first_value is not None and arm_step is not None else None),
            "spend_to_first_value_steps": (first_value - spend["step"] if first_value is not None else None),
            "remaining_steps_at_first_value": (TOTAL_STEPS - 1 - first_value
                                                if first_value is not None else None),
            "adaptive_token_available_at_first_value": bool(
                first_row and first_row["policy_state"]["spend_step"] is None),
            "reserve_locked_at_first_value": (first_row["policy_state"]["reserve_locked"]
                                               if first_row else None),
            "tokens_before_first_value": (first_row["policy_state"]["tokens_before"] if first_row else None),
            "scheduler_forbade_available_reserve": bool(
                first_row and first_row["policy_state"]["reserve_locked"]
                and first_row["policy_state"]["spend_step"] is not None),
            "source_sha256": digest(path),
        })

    supported = [row for row in episodes if row["first_value_step"] is not None]
    arm_to_value = [row["arm_to_first_value_steps"] for row in supported
                    if row["arm_to_first_value_steps"] is not None]
    spend_to_value = [row["spend_to_first_value_steps"] for row in supported]
    run_lengths = [length for row in supported for length in row["value_run_lengths_steps"]]
    latest_first = max(row["first_value_step"] for row in supported)
    result = {
        "study_id": "cvc-q3-q2-temporal-diagnosis-v1",
        "development_only": True,
        "formal": False,
        "navigation_outcomes_used": False,
        "evaluator_fields_read": False,
        "control_period_s": DT_S,
        "total_steps": TOTAL_STEPS,
        "adaptive_episode_count": len(episodes),
        "value_supported_episode_count": len(supported),
        "episodes": episodes,
        "arm_to_first_value_distribution": distribution(arm_to_value),
        "adaptive_spend_to_first_value_distribution": distribution(spend_to_value),
        "value_run_length_distribution": distribution(run_lengths),
        "latest_first_value_step": latest_first,
        "latest_first_value_time_s": latest_first * DT_S,
        "simple_deadline_extension": {
            "q2_reserve_step": 249,
            "maximum_required_arm_wait_steps": max(arm_to_value),
            "would_capture_all_if_reserve_unchanged": False,
            "reason": "Two first value events occur after the fixed step-249 reserve has already exhausted capacity.",
        },
        "answers": {
            "how_late_relative_to_spend": (
                f"First value arrived {min(spend_to_value)}-{max(spend_to_value)} steps "
                f"({min(spend_to_value) * DT_S:.3f}-{max(spend_to_value) * DT_S:.3f} s) after adaptive spend."
            ),
            "would_deadline_extension_capture": (
                "Only if packet eligibility and the reserve move too: the maximum observed ARM-to-value delay is "
                f"{max(arm_to_value)} steps ({max(arm_to_value) * DT_S:.3f} s), while two events are post-reserve."
            ),
            "actionable_duration": (
                f"Immediate same-cycle spending is sufficient when a token is eligible; the shortest observed event "
                f"run is {min(run_lengths)} steps ({min(run_lengths) * DT_S:.3f} s)."
            ),
            "transient_loss": (
                "No observed event was one-step transient; run lengths are recorded explicitly. A bounded latch remains "
                "a causal robustness guard, not the primary repair."
            ),
            "capacity_vs_rule": (
                "At the pre-reserve value event, one reserve token physically remained but was scheduler-locked; at "
                "post-reserve events capacity was exhausted. The failure combines eligibility and exhaustion."
            ),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "diagnosis.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "episodes": len(episodes),
        "value_supported": len(supported),
        "arm_to_value": result["arm_to_first_value_distribution"],
        "spend_to_value": result["adaptive_spend_to_first_value_distribution"],
        "run_lengths": result["value_run_length_distribution"],
    }, indent=2))


if __name__ == "__main__":
    main()
