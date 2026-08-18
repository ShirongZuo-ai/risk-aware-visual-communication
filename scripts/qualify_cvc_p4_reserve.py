"""Outcome-blind CVC-P4 reserve allocator qualification on P2/P3 risk traces."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_p4_allocator import ReserveSpec, SingleAdaptiveReserveAllocator, p4_uniform_schedule


CONFIG = ROOT / "config" / "cvc_p4_development.json"
TRACES = ROOT / "results" / "cvc_p2_development" / "traces"
OUTPUT = ROOT / "results" / "cvc_p4_offline_qualification"


def read_sender(path: Path) -> list[dict]:
    projected = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            source = json.loads(line)
            projected.append({"step": int(source["step"]), "time_s": float(source["time_s"]),
                              "r0": float(source["sender"]["r0"]), "r1": float(source["sender"]["r1"])})
    return projected


def digest(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def resolve(candidate: dict, total_steps: int, threshold: float) -> ReserveSpec:
    last = total_steps - 1
    family = candidate["family"]
    if family in ("fixed_late", "fixed_final"):
        return ReserveSpec(family, threshold=threshold,
                           fixed_late_step=round(float(candidate["late_fraction"]) * last))
    if family == "release_time":
        return ReserveSpec(family, threshold=threshold,
                           release_step=round(float(candidate["release_fraction"]) * last),
                           fallback_step=round(float(candidate["fallback_fraction"]) * last))
    return ReserveSpec(family, threshold=threshold, separation_steps=int(candidate["separation_steps"]))


def simulate(risks: list[float], spec: ReserveSpec) -> dict:
    allocator = SingleAdaptiveReserveAllocator(len(risks), spec)
    decisions = [allocator.decide(step, risk) for step, risk in enumerate(risks)]
    sent = [(step, value) for step, value in enumerate(decisions) if value.transmit]
    if len(sent) != 3 or allocator.sent != 3:
        raise AssertionError(f"reserve allocator did not send exactly three packets: {sent}")
    schedule = [step for step, _ in sent]
    roles = [value.packet_role for _, value in sent]
    if roles != ["startup", "adaptive", "reserve"]:
        raise AssertionError(f"invalid packet roles: {roles}")
    gaps = [right - left for left, right in zip(schedule, schedule[1:])]
    gaps.append((len(risks) - 1) - schedule[-1])
    trigger = next((step for step, value in enumerate(decisions) if value.adaptive_trigger_event), None)
    return {"schedule": schedule, "roles": roles, "adaptive_step": schedule[1],
            "reserve_step": schedule[2], "exhaustion_step": schedule[2],
            "first_trigger_step": trigger, "maximum_implied_image_age_steps": max(gaps),
            "maximum_implied_image_age_ms": max(gaps) * 32}


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def evaluate(candidate: dict, streams: list[dict], config: dict) -> dict:
    episodes = []
    for stream in streams:
        spec = resolve(candidate, len(stream["rows"]), float(config["threshold"]))
        r0 = simulate([row["r0"] for row in stream["rows"]], spec)
        r1 = simulate([row["r1"] for row in stream["rows"]], spec)
        p0, p1 = r0["first_trigger_step"], r1["first_trigger_step"]
        prediction_lead = p0 - p1 if p0 is not None and p1 is not None else None
        communication_lead = r0["adaptive_step"] - r1["adaptive_step"]
        efficiency = communication_lead / prediction_lead if prediction_lead not in (None, 0) else None
        episodes.append({
            "stream_id": stream["stream_id"], "aliases": stream["aliases"],
            "r0": r0, "r1": r1, "prediction_lead_steps": prediction_lead,
            "communication_lead_steps": communication_lead, "lead_conversion": efficiency,
            "schedule_differs": r0["schedule"] != r1["schedule"],
            "only_middle_packet_differs": (r0["schedule"][0] == r1["schedule"][0]
                                           and r0["reserve_step"] == r1["reserve_step"]),
            "r0_wire_bytes": 3 * int(config["packet_bytes"]),
            "r1_wire_bytes": 3 * int(config["packet_bytes"]),
        })
    positive = [row for row in episodes if row["prediction_lead_steps"] is not None and row["prediction_lead_steps"] > 0]
    conversion_fraction = (sum(row["communication_lead_steps"] > 0 for row in positive) / len(positive)
                           if positive else 0.0)
    schedule_fraction = sum(row["schedule_differs"] for row in episodes) / len(episodes)
    only_middle = all(row["only_middle_packet_differs"] for row in episodes)
    exact = all(row["r0_wire_bytes"] == row["r1_wire_bytes"] == int(config["episode_wire_bytes"])
                for row in episodes)
    minimum_exhaustion = min(min(row["r0"]["exhaustion_step"], row["r1"]["exhaustion_step"])
                             for row in episodes)
    exhaustion_equal = all(row["r0"]["exhaustion_step"] == row["r1"]["exhaustion_step"] for row in episodes)
    worst_age = max(max(row["r0"]["maximum_implied_image_age_steps"],
                        row["r1"]["maximum_implied_image_age_steps"]) for row in episodes)
    gate = config["qualification_gate"]
    required_exhaustion = math.ceil(float(gate["minimum_exhaustion_fraction"]) * (len(streams[0]["rows"]) - 1))
    passed = (len(positive) == len(streams)
              and conversion_fraction >= float(gate["required_positive_lead_conversion_fraction"])
              and schedule_fraction >= float(gate["required_schedule_difference_fraction"])
              and minimum_exhaustion >= required_exhaustion and exact)
    return {
        "candidate_id": candidate["id"], "family": candidate["family"], "candidate": candidate,
        "gate_pass": passed, "positive_lead_support": len(positive),
        "conversion_fraction": conversion_fraction, "schedule_difference_fraction": schedule_fraction,
        "median_prediction_lead_steps": median([row["prediction_lead_steps"] for row in positive]),
        "median_communication_lead_steps": median([row["communication_lead_steps"] for row in positive]),
        "median_lead_conversion": median([row["lead_conversion"] for row in positive]),
        "only_middle_packet_differs": only_middle, "exhaustion_times_equal": exhaustion_equal,
        "minimum_exhaustion_step": minimum_exhaustion, "required_exhaustion_step": required_exhaustion,
        "worst_implied_image_age_steps": worst_age, "worst_implied_image_age_ms": worst_age * 32,
        "exact_cost_match": exact, "episodes": episodes,
    }


def main() -> None:
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    grouped: dict[str, list[tuple[Path, list[dict]]]] = defaultdict(list)
    for path in sorted(TRACES.glob("matrix__*.jsonl")):
        rows = read_sender(path)
        grouped[digest(rows)].append((path, rows))
    streams = [{"stream_id": key[:16], "aliases": [str(path.relative_to(ROOT)) for path, _ in members],
                "rows": members[0][1]} for key, members in sorted(grouped.items())]
    if len(streams) != 18:
        raise RuntimeError(f"expected 18 distinct causal streams, found {len(streams)}")
    candidates = [evaluate(candidate, streams, config) for candidate in config["reserve_candidates"]]
    family_order = {"fixed_late": 0, "fixed_final": 1, "release_time": 2, "minimum_separation": 3}
    passing = [row for row in candidates if row["gate_pass"]]
    passing.sort(key=lambda row: (not (row["only_middle_packet_differs"] and row["exhaustion_times_equal"]),
                                  row["worst_implied_image_age_steps"], family_order[row["family"]],
                                  [item["id"] for item in config["reserve_candidates"]].index(row["candidate_id"])))
    selected = passing[0] if passing else None
    if selected:
        representative = selected["episodes"][0]
        selected_summary = {key: value for key, value in selected.items() if key != "episodes"}
        selected_summary["resolved_u0_schedule"] = list(p4_uniform_schedule(representative["r0"]["reserve_step"]))
        selected_summary["resolved_reserve_step"] = representative["r0"]["reserve_step"]
        selected_summary["resolved_adaptive_deadline"] = representative["r0"]["reserve_step"] - 1
    else:
        selected_summary = None
    report = {
        "development_only": True, "formal": False, "downstream_outcomes_used": False,
        "config": str(CONFIG.relative_to(ROOT)), "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "source_file_count": sum(len(value) for value in grouped.values()),
        "distinct_causal_stream_count": len(streams), "qualification_gate": config["qualification_gate"],
        "selection_rule": config["selection_rule"], "candidates": candidates, "selected": selected_summary,
        "offline_reserve_gate_passed": selected is not None, "webots_authorized": selected is not None,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "qualification_results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"offline_reserve_gate_passed": report["offline_reserve_gate_passed"],
                      "candidate_summaries": [{key: value for key, value in row.items() if key != "episodes"}
                                              for row in candidates],
                      "selected": selected_summary}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
