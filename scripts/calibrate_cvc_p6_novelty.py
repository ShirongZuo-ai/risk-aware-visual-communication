"""Outcome-blind signal calibration for the bounded CVC-P6 novelty panel."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_p2_perception import VisualObstacle, detect_red_obstacle
from communication.cvc_p3_codec import decode_p3_packet, encode_p3_packet
from communication.cvc_p6_allocator import NoveltyThresholds, RiskArmedNoveltyAllocator, task_novelty


CONFIG = ROOT / "config" / "cvc_p6_calibration.json"
P5_TRACES = ROOT / "results" / "cvc_p5_diagnostic" / "traces"
RESULTS = ROOT / "results" / "cvc_p6_calibration"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def as_obstacle(value: dict) -> VisualObstacle:
    bbox = tuple(value["bbox_xyxy"]) if value.get("bbox_xyxy") is not None else None
    centroid = tuple(value["centroid_xy"]) if value.get("centroid_xy") is not None else None
    proximity = float(value.get("proximity") or 0.0)
    return VisualObstacle(bool(value["detected"]), value.get("bearing"), proximity, bbox,
                          int(value.get("pixel_count", 0)), centroid,
                          int(value.get("component_count", 0)), float(value.get("confidence", 0.0)), proximity)


def q25_step(values: list[float]) -> int | None:
    total = sum(values)
    if total <= 0:
        return None
    target, running = total * 0.25, 0.0
    for step, value in enumerate(values):
        running += value
        if running >= target:
            return step
    return len(values) - 1


def decoded(image: Image.Image, identity: str) -> Image.Image:
    packet = encode_p3_packet(image, 0, 0.0, "U0", 45, 24000)
    result, _ = decode_p3_packet(packet.payload)
    if len(packet.payload) != 24000:
        raise RuntimeError(f"fixture packet mismatch: {identity}")
    return result


def fixture_diagnostics() -> dict:
    matches = sorted((ROOT / "results" / "cvc_p1_webots" / "traces").glob(
        "fixture_center__U0__HIGH.frame000.png"))
    if len(matches) != 1:
        raise RuntimeError("expected one real CVC center fixture")
    source_path = matches[0]
    source = Image.open(source_path).convert("RGB")
    base = decoded(source, "base")
    base_obstacle = detect_red_obstacle(base)
    stable = []
    for index in range(16):
        repeated = decoded(source.copy(), f"stable_{index}")
        novelty = task_novelty(base_obstacle, detect_red_obstacle(repeated), base.size)
        stable.append(novelty.__dict__)
    irrelevant = []
    source_array = np.asarray(source, dtype=np.uint8).copy()
    for index in range(16):
        changed = source_array.copy()
        y, x = index // 4, index % 4
        changed[y, x, 1] = np.uint8((int(changed[y, x, 1]) + 1) % 256)
        perturbed = decoded(Image.fromarray(changed), f"irrelevant_{index}")
        irrelevant.append(task_novelty(base_obstacle, detect_red_obstacle(perturbed), base.size).__dict__)
    controlled = []
    fill = tuple(int(value) for value in np.asarray(source)[0, 0])
    for pixels in (4, 8, 12):
        shifted = Image.new("RGB", source.size, fill)
        shifted.paste(source, (pixels, 0))
        moved = decoded(shifted, f"shift_{pixels}")
        controlled.append({"operation": "horizontal_shift", "pixels": pixels,
                           **task_novelty(base_obstacle, detect_red_obstacle(moved), base.size).__dict__})
    for scale in (1.05, 1.10, 1.20):
        enlarged = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.BILINEAR)
        x0, y0 = (enlarged.width - source.width) // 2, (enlarged.height - source.height) // 2
        scaled = enlarged.crop((x0, y0, x0 + source.width, y0 + source.height))
        changed = decoded(scaled, f"scale_{scale}")
        controlled.append({"operation": "center_scale", "scale": scale,
                           **task_novelty(base_obstacle, detect_red_obstacle(changed), base.size).__dict__})
    noise_keys = ("delta_bearing", "delta_proximity", "delta_area_relative")
    noise = stable + irrelevant
    maxima = {key: max(float(row[key]) for row in noise) for key in noise_keys}
    return {
        "real_fixture": str(source_path.relative_to(ROOT)),
        "real_fixture_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "stable_reencodes": stable,
        "irrelevant_background_lsb_changes": irrelevant,
        "stable_and_irrelevant_noise_maxima": maxima,
        "controlled_image_space_changes": controlled,
        "navigation_outcomes_used": False,
    }


def simulate(path: Path, candidate: dict, config: dict) -> dict:
    rows = read_jsonl(path)
    scenario, policy = path.stem.split("__")[1:]
    thresholds = NoveltyThresholds(float(candidate["bearing"]), float(candidate["proximity"]),
                                   float(candidate["area_relative"]))
    allocator = RiskArmedNoveltyAllocator(len(rows), float(config["risk_threshold"]),
                                          int(config["deadline_steps"]), int(config["reserve_step"]), thresholds)
    held = as_obstacle(rows[0]["counterfactual"]["current_perception"])
    decisions = []
    for row in rows:
        current = as_obstacle(row["counterfactual"]["current_perception"])
        decisions.append(allocator.decide(int(row["step"]), float(row["sender"]["selected_risk"]),
                                          task_novelty(held, current)))
    sends = [(step, decision) for step, decision in enumerate(decisions) if decision.transmit]
    adaptive_step, adaptive = next((step, decision) for step, decision in sends
                                   if decision.packet_role == "adaptive")
    p4_step = next(int(row["step"]) for row in rows
                   if row["communication"]["packet_role"] == "adaptive")
    perception_q25 = q25_step([float(row["counterfactual"]["perception"]["combined_l2"]) for row in rows])
    control_q25 = q25_step([float(row["counterfactual"]["control"]["control_l2"]) for row in rows])
    return {
        "scenario": scenario, "policy": policy, "arm_step": adaptive.arm_step,
        "spend_step": adaptive_step,
        "arm_to_spend_steps": adaptive_step - adaptive.arm_step if adaptive.arm_step is not None else None,
        "spend_reason": adaptive.reason, "p4_immediate_step": p4_step,
        "perception_q25_step": perception_q25, "control_q25_step": control_q25,
        "p4_abs_distance_to_perception_q25": abs(p4_step - perception_q25),
        "p6_abs_distance_to_perception_q25": abs(adaptive_step - perception_q25),
        "p4_abs_distance_to_control_q25": abs(p4_step - control_q25),
        "p6_abs_distance_to_control_q25": abs(adaptive_step - control_q25),
        "send_steps": [step for step, _ in sends], "packet_count": len(sends),
        "wire_bytes": len(sends) * int(config["packet_bytes"]),
        "reserve_step": next(step for step, decision in sends if decision.packet_role == "reserve"),
    }


def main() -> None:
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    fixture = fixture_diagnostics()
    trace_paths = sorted(P5_TRACES.glob("diagnostic__*.jsonl"))
    if len(trace_paths) != 12:
        raise RuntimeError("P6 calibration requires all 12 P5 A0/A1 traces")
    candidates = []
    gate = config["selection_gate"]
    for candidate in config["candidate_panel"]:
        episodes = [simulate(path, candidate, config) for path in trace_paths]
        a1 = [row for row in episodes if row["policy"] == "A1"]
        delays = [row["arm_to_spend_steps"] for row in a1 if row["arm_to_spend_steps"] is not None]
        tests = {
            "a1_non_immediate_fraction": sum(value > 0 for value in delays) / len(a1),
            "median_arm_to_spend_steps": statistics.median(delays),
            "perception_q25_closer_fraction": sum(
                row["p6_abs_distance_to_perception_q25"] < row["p4_abs_distance_to_perception_q25"]
                for row in a1) / len(a1),
            "all_spends_before_reserve": all(row["spend_step"] < row["reserve_step"] for row in episodes),
            "all_exact_three_packets": all(row["packet_count"] == 3 and row["wire_bytes"] == 72000
                                            for row in episodes),
        }
        passed = (tests["a1_non_immediate_fraction"] >= gate["minimum_a1_non_immediate_fraction"] and
                  tests["median_arm_to_spend_steps"] >= gate["minimum_median_arm_to_spend_steps"] and
                  tests["perception_q25_closer_fraction"] >= gate["minimum_perception_q25_closer_fraction"] and
                  (tests["all_spends_before_reserve"] or not gate["require_all_spends_before_reserve"]) and
                  (tests["all_exact_three_packets"] or not gate["require_exact_three_packets"]))
        candidates.append({"candidate": candidate, "signal_only_tests": tests, "passed": passed,
                           "episodes": episodes})
    selected = next((row for row in candidates if row["passed"]), None)
    if selected is None:
        raise RuntimeError("no bounded P6 novelty candidate passes signal-only calibration")
    report = {
        "development_only": True, "formal": False, "navigation_outcomes_used": False,
        "forbidden_fields_used": [], "source_fields_used": [
            "sender.selected_risk", "counterfactual.current_perception",
            "counterfactual.perception.combined_l2", "counterfactual.control.control_l2",
            "communication.packet_role",
        ],
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "fixture_diagnostics": fixture, "candidate_results": candidates,
        "selected_candidate": selected["candidate"], "selection_rule": config["selection_rule"],
        "deadline_steps": config["deadline_steps"], "reserve_step": config["reserve_step"],
        "webots_outcome_comparison_authorized": True,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "calibration_results.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"selected_candidate": report["selected_candidate"],
                      "deadline_steps": report["deadline_steps"],
                      "selected_signal_only_tests": selected["signal_only_tests"],
                      "navigation_outcomes_used": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
