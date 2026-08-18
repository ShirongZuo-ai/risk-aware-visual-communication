"""Component runtime audit for the Q2/Q3 causal decision pipeline."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import platform
from statistics import mean
import sys
from time import perf_counter_ns

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_p2_perception import detect_red_obstacle
from communication.cvc_q1_visual_geometry import VisualRangeCalibration, visual_obstacle_estimates
from communication.cvc_q2_allocator import RiskArmedSafetyValueAllocator, evaluate_safety_decision_value
from communication.cvc_q3_allocator import TemporalRepairAllocator
from navigation.cvc_q1_local_planner import plan_local_action


OUT = ROOT / "results" / "cvc_q3_runtime_profile"
CONTROL_PERIOD_MS = 32.0
ITERATIONS = 2_000
WARMUP = 100
FRAME_PATHS = (
    ROOT / "results" / "cvc_p1_webots" / "traces" / "fixture_absent__U0__HIGH.frame000.png",
    ROOT / "results" / "cvc_p1_webots" / "traces" / "fixture_left__U0__HIGH.frame000.png",
    ROOT / "results" / "cvc_p1_webots" / "traces" / "fixture_center__U0__HIGH.frame000.png",
    ROOT / "results" / "cvc_p1_webots" / "traces" / "fixture_right__U0__HIGH.frame000.png",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] if low == high else ordered[low] * (high - position) + ordered[high] * (position - low)


def timed_calls(functions: list, iterations: int = ITERATIONS) -> tuple[dict, list[object]]:
    for index in range(WARMUP):
        functions[index % len(functions)]()
    durations = []
    outputs = []
    for index in range(iterations):
        fn = functions[index % len(functions)]
        start = perf_counter_ns()
        output = fn()
        durations.append((perf_counter_ns() - start) / 1_000_000)
        if index < len(functions):
            outputs.append(output)
    return ({
        "iterations": iterations,
        "mean_ms": mean(durations),
        "p95_ms": percentile(durations, .95),
        "maximum_ms": max(durations),
        "deadline_misses": sum(value > CONTROL_PERIOD_MS for value in durations),
    }, outputs)


def scheduler_profile(kind: str, no_value) -> dict:
    durations = []
    for _ in range(ITERATIONS):
        if kind == "q2":
            allocator = RiskArmedSafetyValueAllocator(312, .14, 47, 249)
        else:
            allocator = TemporalRepairAllocator(312, .14, 63, 295, 311)
        allocator.decide(0, .1, no_value)
        start = perf_counter_ns()
        allocator.decide(1, .15, no_value)
        durations.append((perf_counter_ns() - start) / 1_000_000)
    return {
        "iterations": ITERATIONS,
        "mean_ms": mean(durations),
        "p95_ms": percentile(durations, .95),
        "maximum_ms": max(durations),
        "deadline_misses": sum(value > CONTROL_PERIOD_MS for value in durations),
        "measured_transition": "risk crossing at step 1 without Safety Value",
    }


def main() -> None:
    if not all(path.is_file() for path in FRAME_PATHS):
        raise FileNotFoundError("runtime fixture frame missing")
    config = json.loads((ROOT / "config" / "cvc_q1_planner_v2.json").read_text(encoding="utf-8"))
    planner = config["planner"]
    visual = config["visual_geometry"]
    frames = [Image.open(path).convert("RGB") for path in FRAME_PATHS]
    detector_functions = [lambda frame=frame: detect_red_obstacle(frame) for frame in frames]
    detector_stats, detections = timed_calls(detector_functions)
    calibration = VisualRangeCalibration(
        visual["inverse_height_coefficient_m_px"], visual["intercept_m"], visual["uncertainty_bound_m"])
    obstacle_sets = [visual_obstacle_estimates(
        detection, calibration,
        camera_horizontal_fov_rad=visual["camera_horizontal_fov_rad"],
        known_obstacle_radius_m=visual["known_obstacle_radius_m"])
        for detection in detections]
    common = dict(
        horizon_s=planner["horizon_s"], step_s=planner["rollout_step_s"],
        robot_radius_m=planner["robot_radius_m"], hard_clearance_m=planner["hard_clearance_m"],
        preferred_clearance_m=planner["preferred_clearance_m"],
        near_slowdown_range_m=planner["near_slowdown_range_m"],
        near_max_speed_m_s=planner["near_max_speed_m_s"])
    held_functions = [lambda obstacles=obstacles: plan_local_action(obstacles, 0.0, **common)
                      for obstacles in obstacle_sets]
    current_functions = [lambda obstacles=obstacles: plan_local_action(obstacles, .25, **common)
                         for obstacles in reversed(obstacle_sets)]
    held_stats, held_plans = timed_calls(held_functions)
    current_stats, current_plans = timed_calls(current_functions)
    plan_pairs = list(zip(held_plans, current_plans))
    value_functions = [lambda pair=pair: evaluate_safety_decision_value(pair[0], pair[1])
                       for pair in plan_pairs]
    value_stats, values = timed_calls(value_functions)
    no_value = evaluate_safety_decision_value(held_plans[0], held_plans[0])
    q2_scheduler = scheduler_profile("q2", no_value)
    q3_scheduler = scheduler_profile("q3", no_value)
    components = {
        "detector": detector_stats,
        "held_planner": held_stats,
        "current_hypothetical_planner": current_stats,
        "safety_decision_value": value_stats,
        "q2_scheduler_decision": q2_scheduler,
        "q3_scheduler_decision": q3_scheduler,
    }
    q2_p95_sum = sum(components[name]["p95_ms"] for name in (
        "detector", "held_planner", "current_hypothetical_planner",
        "safety_decision_value", "q2_scheduler_decision"))
    q3_p95_sum = sum(components[name]["p95_ms"] for name in (
        "detector", "held_planner", "current_hypothetical_planner",
        "safety_decision_value", "q3_scheduler_decision"))
    result = {
        "study_id": "cvc-q3-runtime-profile-v1",
        "development_only": True, "formal": False,
        "control_period_ms": CONTROL_PERIOD_MS,
        "warmup_iterations_per_component": WARMUP,
        "fixture_frame_sha256": {str(path.relative_to(ROOT)): digest(path) for path in FRAME_PATHS},
        "platform": {"python": platform.python_version(), "platform": platform.platform()},
        "components": components,
        "conservative_sum_of_component_p95_ms": {"q2": q2_p95_sum, "q3": q3_p95_sum},
        "q2_p95_headroom_ms": CONTROL_PERIOD_MS - q2_p95_sum,
        "q3_p95_headroom_ms": CONTROL_PERIOD_MS - q3_p95_sum,
        "any_component_deadline_miss": any(row["deadline_misses"] for row in components.values()),
        "classification": "logical_scheduler_timing" if q2_p95_sum < CONTROL_PERIOD_MS else "computation_latency",
        "scope_note": (
            "Offline wall-clock microprofile of the exact detector/planner/value/scheduler functions on four saved "
            "actual Webots camera fixtures. JPEG encode/decode and simulator stepping are outside the requested "
            "component list and are not attributed to Safety Value computation."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "profile.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"classification": result["classification"], "components": components,
                      "q2_p95_sum_ms": q2_p95_sum, "headroom_ms": result["q2_p95_headroom_ms"]}, indent=2))


if __name__ == "__main__":
    main()
