"""CVC-P3 sender-only allocator qualification.

This script deliberately never reads ``evaluator``, ``perception``, ``control``,
or task-summary fields.  It projects P2 traces to causal sender risk and
communication fields, freezes a qualification decision, and stops before any
downstream Webots outcome comparison.
"""
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

from communication.cvc_p2_protocol import ExactQuotaScheduler
from communication.cvc_p3_allocator import AllocatorSpec, CausalRiskAllocator, uniform_schedule


CONFIG_PATH = ROOT / "config" / "cvc_p3_development.json"
P2_TRACES = ROOT / "results" / "cvc_p2_development" / "traces"
OUTPUT = ROOT / "results" / "cvc_p3_offline_qualification"


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - index) + ordered[high] * (index - low)


def read_sender_projection(path: Path) -> dict:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        source = json.loads(line)
        sender = source["sender"]
        communication = source["communication"]
        rows.append({
            "step": int(source["step"]),
            "time_s": float(source["time_s"]),
            "r0": float(sender["r0"]),
            "r1": float(sender["r1"]),
            "selected_risk": float(sender["selected_risk"]),
            "transmitted": bool(communication["transmitted"]),
            "reason": str(communication["reason"]),
            "wire_bytes": int(communication["wire_bytes"]),
            "quality_min": int(communication["quality_min"]),
            "quality_max": int(communication["quality_max"]),
            "roi_tile_ids": tuple(int(value) for value in communication["roi_tile_ids"]),
        })
    if not rows:
        raise ValueError(f"empty trace: {path}")
    parts = path.stem.split("__")
    if len(parts) != 4 or parts[0] != "matrix":
        raise ValueError(f"unexpected trace identity: {path.name}")
    return {"path": path, "scenario": parts[1], "mechanism": parts[2], "risk_signal": parts[3], "rows": rows}


def stream_digest(rows: list[dict]) -> str:
    payload = json.dumps(
        [[row["step"], row["time_s"], row["r0"], row["r1"]] for row in rows],
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def first_crossing(rows: list[dict], key: str, threshold: float) -> int | None:
    return next((row["step"] for row in rows if row[key] >= threshold), None)


def old_schedule(rows: list[dict], key: str, adaptive: bool) -> list[int]:
    scheduler = ExactQuotaScheduler(len(rows), 2, adaptive)
    return [row["step"] for row in rows if scheduler.decide(row["step"], row[key])[0]]


def p2_trace_diagnosis(traces: list[dict]) -> dict:
    detail = []
    for trace in traces:
        rows = trace["rows"]
        adaptive = trace["mechanism"] in ("T", "TS")
        r0_schedule = old_schedule(rows, "r0", adaptive)
        r1_schedule = old_schedule(rows, "r1", adaptive)
        r0_cross = first_crossing(rows, "r0", 0.16)
        r1_cross = first_crossing(rows, "r1", 0.16)
        first_eligible = max(1, len(rows) // 2 // 3)
        r0_eligible = next((row["step"] for row in rows if row["step"] >= first_eligible and row["r0"] >= 0.16), None)
        r1_eligible = next((row["step"] for row in rows if row["step"] >= first_eligible and row["r1"] >= 0.16), None)
        signal_equal = all(abs(row["r0"] - row["r1"]) <= 1e-12 for row in rows)
        send_steps = [row["step"] for row in rows if row["transmitted"]]
        r0_bins = [int(rows[step]["r0"] >= 0.16) for step in r0_schedule]
        r1_bins = [int(rows[step]["r1"] >= 0.16) for step in r1_schedule]
        if signal_equal:
            classification = "functionally_indistinguishable_allocator_input"
        elif r0_schedule == r1_schedule and r0_bins == r1_bins:
            classification = "different_risk_quantized_to_same_temporal_and_quality_actions"
        elif r0_schedule == r1_schedule:
            classification = "temporal_collapse_with_potential_quality_difference"
        else:
            classification = "hypothetically_distinguishable"
        detail.append({
            "trace": str(trace["path"].relative_to(ROOT)),
            "scenario": trace["scenario"],
            "mechanism": trace["mechanism"],
            "risk_signal": trace["risk_signal"],
            "r0_crossing_step_0_16": r0_cross,
            "r1_crossing_step_0_16": r1_cross,
            "prediction_lead_steps": r0_cross - r1_cross if r0_cross is not None and r1_cross is not None else None,
            "minimum_risk_eligible_step_after_initial": first_eligible,
            "r0_first_eligible_above_threshold_step": r0_eligible,
            "r1_first_eligible_above_threshold_step": r1_eligible,
            "hypothetical_r0_send_steps": r0_schedule,
            "hypothetical_r1_send_steps": r1_schedule,
            "actual_send_steps": send_steps,
            "r0_quality_bins_at_send": r0_bins,
            "r1_quality_bins_at_send": r1_bins,
            "packet_count": 2,
            "tokens_after_initial": 1,
            "adaptive_refractory_steps": first_eligible,
            "debounce": False,
            "spatial_roi_rule": "same causal decoded red-component bbox expanded by one tile; risk cannot move the ROI",
            "quality_quantization": "two bins split at 0.16 for S/TS; fixed quality 34 for U0/T",
            "signals_identical": signal_equal,
            "classification": classification,
        })
    leads = [row["prediction_lead_steps"] for row in detail if row["prediction_lead_steps"] is not None]
    return {
        "development_only": True,
        "p2_preserved": True,
        "trace_count": len(detail),
        "classification_counts": dict(sorted((key, sum(row["classification"] == key for row in detail))
                                                for key in {row["classification"] for row in detail})),
        "warning_lead_steps": {
            "count": len(leads), "minimum": min(leads) if leads else None,
            "median": median(leads), "maximum": max(leads) if leads else None,
            "q25": percentile(leads, 0.25), "q75": percentile(leads, 0.75),
        },
        "collapse_explanation": (
            "P2 had one startup packet and only one remaining token. Adaptive timing imposed a 72-step "
            "eligibility delay (one third of the 218-step uniform gap). Earlier R1 crossings therefore waited "
            "until the same eligibility boundary as R0, or both signals reached forced end reconciliation. "
            "At the shared send steps the 0.16 two-level quality threshold and image-derived ROI also matched."
        ),
        "traces": detail,
    }


def spec_from_json(item: dict) -> AllocatorSpec:
    values = dict(item)
    if "hazard_thresholds" in values:
        values["hazard_thresholds"] = tuple(values["hazard_thresholds"])
    return AllocatorSpec(**values)


def spec_identity(spec: AllocatorSpec) -> str:
    if spec.family == "threshold":
        return f"threshold_{spec.threshold:.3f}"
    if spec.family == "derivative":
        return f"derivative_{spec.derivative_threshold:.3f}"
    if spec.family == "integral":
        return f"integral_{spec.integral_threshold:.3f}"
    return "hazard_" + "_".join(f"{value:.3f}" for value in spec.hazard_thresholds)


def simulate(risks: list[float], transmissions: int, spec: AllocatorSpec) -> dict:
    allocator = CausalRiskAllocator(len(risks), transmissions, spec)
    decisions = [allocator.decide(step, risk) for step, risk in enumerate(risks)]
    send_steps = [step for step, value in enumerate(decisions) if value.transmit]
    trigger_steps = [step for step, value in enumerate(decisions) if value.trigger_event]
    risk_send_steps = [step for step, value in enumerate(decisions) if value.transmit and value.reason.startswith("risk_")]
    if len(send_steps) != transmissions or allocator.sent != transmissions:
        raise AssertionError("allocator failed exact quota")
    return {
        "send_steps": send_steps,
        "trigger_steps": trigger_steps,
        "first_trigger_step": trigger_steps[0] if trigger_steps else None,
        "first_risk_send_step": risk_send_steps[0] if risk_send_steps else None,
        "reasons": [decisions[step].reason for step in send_steps],
    }


def lead_summary(values: list[float]) -> dict:
    return {
        "count": len(values), "minimum": min(values) if values else None,
        "q25": percentile(values, 0.25), "median": median(values),
        "q75": percentile(values, 0.75), "maximum": max(values) if values else None,
    }


def evaluate_candidate(streams: list[dict], spec: AllocatorSpec, transmissions: int,
                       packet_bytes: int, gate: dict) -> dict:
    episodes = []
    for stream in streams:
        rows = stream["rows"]
        r0 = simulate([row["r0"] for row in rows], transmissions, spec)
        r1 = simulate([row["r1"] for row in rows], transmissions, spec)
        p0, p1 = r0["first_trigger_step"], r1["first_trigger_step"]
        c0, c1 = r0["first_risk_send_step"], r1["first_risk_send_step"]
        prediction_lead = p0 - p1 if p0 is not None and p1 is not None else None
        communication_lead = c0 - c1 if c0 is not None and c1 is not None else None
        efficiency = (communication_lead / prediction_lead
                      if prediction_lead not in (None, 0) and communication_lead is not None else None)
        episodes.append({
            "stream_id": stream["stream_id"], "aliases": stream["aliases"],
            "r0_trigger_step": p0, "r1_trigger_step": p1,
            "prediction_lead_steps": prediction_lead,
            "r0_send_steps": r0["send_steps"], "r1_send_steps": r1["send_steps"],
            "r0_first_risk_send_step": c0, "r1_first_risk_send_step": c1,
            "communication_lead_steps": communication_lead,
            "conversion_efficiency": efficiency,
            "schedule_differs": r0["send_steps"] != r1["send_steps"],
            "distinct_packet_step_decisions": len(set(r0["send_steps"]) ^ set(r1["send_steps"])),
            "r0_reasons": r0["reasons"], "r1_reasons": r1["reasons"],
            "r0_wire_bytes": transmissions * packet_bytes,
            "r1_wire_bytes": transmissions * packet_bytes,
        })
    positive = [row for row in episodes if row["prediction_lead_steps"] is not None and row["prediction_lead_steps"] > 0]
    converted = [row for row in positive if row["communication_lead_steps"] is not None and row["communication_lead_steps"] > 0]
    efficiencies = [row["conversion_efficiency"] for row in positive if row["conversion_efficiency"] is not None]
    comm_leads = [row["communication_lead_steps"] for row in positive if row["communication_lead_steps"] is not None]
    support_required = math.ceil(len(streams) * float(gate["minimum_positive_lead_support_fraction"]))
    conversion_fraction = len(converted) / len(positive) if positive else 0.0
    exact_cost = all(row["r0_wire_bytes"] == row["r1_wire_bytes"] == 72000 for row in episodes)
    passed = (
        len(positive) >= support_required
        and conversion_fraction >= float(gate["required_conversion_fraction"])
        and median(comm_leads) is not None and median(comm_leads) > 0
        and median(efficiencies) is not None
        and median(efficiencies) >= float(gate["minimum_median_conversion_efficiency"])
        and exact_cost
    )
    return {
        "spec_id": spec_identity(spec), "family": spec.family,
        "spec": {"family": spec.family, "threshold": spec.threshold,
                 "derivative_threshold": spec.derivative_threshold,
                 "integral_threshold": spec.integral_threshold,
                 "hazard_thresholds": list(spec.hazard_thresholds)},
        "transmissions": transmissions, "packet_bytes": packet_bytes,
        "episode_wire_bytes": transmissions * packet_bytes,
        "unique_streams": len(streams), "positive_prediction_lead_support": len(positive),
        "required_support": support_required,
        "schedule_difference_fraction_all": sum(row["schedule_differs"] for row in episodes) / len(episodes),
        "schedule_difference_fraction_positive_lead": (sum(row["schedule_differs"] for row in positive) / len(positive)
                                                        if positive else 0.0),
        "conversion_fraction": conversion_fraction,
        "prediction_lead_steps": lead_summary([row["prediction_lead_steps"] for row in positive]),
        "communication_lead_steps": lead_summary(comm_leads),
        "conversion_efficiency": lead_summary(efficiencies),
        "exact_cost_match": exact_cost, "gate_pass": passed, "episodes": episodes,
    }


def spatial_actionability(streams: list[dict], packetizations: list[dict]) -> list[dict]:
    output = []
    thresholds = (0.14, 0.20)
    for packetization in packetizations:
        transmissions = int(packetization["transmissions"])
        pairs = []
        for stream in streams:
            steps = uniform_schedule(len(stream["rows"]), transmissions)
            r0_levels = [sum(stream["rows"][step]["r0"] >= value for value in thresholds) for step in steps]
            r1_levels = [sum(stream["rows"][step]["r1"] >= value for value in thresholds) for step in steps]
            pairs.append({"stream_id": stream["stream_id"], "send_steps": list(steps),
                          "r0_quality_levels": r0_levels, "r1_quality_levels": r1_levels,
                          "quality_allocation_differs": r0_levels != r1_levels,
                          "distinct_quality_decisions": sum(a != b for a, b in zip(r0_levels, r1_levels))})
        output.append({
            "transmissions": transmissions,
            "quality_difference_fraction": sum(row["quality_allocation_differs"] for row in pairs) / len(pairs),
            "distinct_quality_decisions": sum(row["distinct_quality_decisions"] for row in pairs),
            "note": "Image-derived ROI is identical at a shared send step; only the causal risk quality tier can differ.",
            "episodes": pairs,
        })
    return output


def main() -> None:
    config_bytes = CONFIG_PATH.read_bytes()
    config = json.loads(config_bytes)
    traces = [read_sender_projection(path) for path in sorted(P2_TRACES.glob("matrix__*.jsonl"))]
    if len(traces) != 42:
        raise RuntimeError(f"expected 42 preserved P2 traces, found {len(traces)}")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for trace in traces:
        grouped[stream_digest(trace["rows"])].append(trace)
    streams = []
    for digest, members in sorted(grouped.items()):
        aliases = sorted(str(member["path"].relative_to(ROOT)) for member in members)
        streams.append({"stream_id": digest[:16], "aliases": aliases, "rows": members[0]["rows"]})

    diagnosis = p2_trace_diagnosis(traces)
    candidates = []
    for item in config["candidate_specs"]:
        spec = spec_from_json(item)
        for packetization in config["packetizations"]:
            candidates.append(evaluate_candidate(
                streams, spec, int(packetization["transmissions"]), int(packetization["packet_bytes"]),
                config["qualification_gate"],
            ))

    by_spec: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        by_spec[candidate["spec_id"]].append(candidate)
    robust = []
    for spec_id, rows in by_spec.items():
        passed = [row for row in rows if row["gate_pass"]]
        if len(passed) >= int(config["qualification_gate"]["minimum_qualified_packetizations"]):
            exemplar = rows[0]
            robust.append({
                "spec_id": spec_id, "family": exemplar["family"], "spec": exemplar["spec"],
                "qualified_packetizations": sorted(row["transmissions"] for row in passed),
                "positive_prediction_lead_support": max(row["positive_prediction_lead_support"] for row in passed),
                "median_communication_lead_steps": max(row["communication_lead_steps"]["median"] for row in passed),
            })
    family_order = {"threshold": 0, "derivative": 1, "integral": 2, "hazard_bucket": 3}
    robust.sort(key=lambda row: (
        -row["positive_prediction_lead_support"], -len(row["qualified_packetizations"]),
        -row["median_communication_lead_steps"], family_order[row["family"]],
        abs((row["spec"].get("threshold") or 0.16) - 0.16), row["spec_id"],
    ))
    selected = None
    if robust:
        chosen = robust[0]
        selected_count = min(chosen["qualified_packetizations"])
        selected = next(row for row in candidates
                        if row["spec_id"] == chosen["spec_id"] and row["transmissions"] == selected_count)
        selected = {key: value for key, value in selected.items() if key != "episodes"}

    risk_leads = {}
    for threshold in (0.12, 0.14, 0.16, 0.18, 0.20):
        values = []
        for stream in streams:
            r0 = first_crossing(stream["rows"], "r0", threshold)
            r1 = first_crossing(stream["rows"], "r1", threshold)
            if r0 is not None and r1 is not None:
                values.append(r0 - r1)
        risk_leads[f"{threshold:.2f}"] = {
            **lead_summary(values), "positive": sum(value > 0 for value in values),
            "zero": sum(value == 0 for value in values), "negative": sum(value < 0 for value in values),
        }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "p2_trace_diagnosis.json").write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "development_only": True, "formal": False, "downstream_outcomes_used": False,
        "config": str(CONFIG_PATH.relative_to(ROOT)),
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "source_trace_count": len(traces), "distinct_causal_stream_count": len(streams),
        "deduplication": "Exact SHA-256 over step/time/R0/R1; aliases retain all 42 P2 traces.",
        "qualification_gate": config["qualification_gate"], "selection_rule": config["selection_rule"],
        "risk_prediction_lead_distributions_steps": risk_leads,
        "candidate_count": len(candidates), "candidates": candidates,
        "robust_qualified_specs": robust, "selected": selected,
        "offline_actuation_gate_passed": selected is not None,
        "spatial_actionability": spatial_actionability(streams, config["packetizations"]),
        "webots_authorized": selected is not None,
    }
    (OUTPUT / "qualification_results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_trace_count": len(traces), "distinct_causal_stream_count": len(streams),
        "offline_actuation_gate_passed": report["offline_actuation_gate_passed"],
        "robust_qualified_specs": robust, "selected": selected,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
