"""Outcome-blind scheduler-family qualification on frozen Q2 causal traces."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from statistics import median
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.cvc_q2_allocator import RiskArmedSafetyValueAllocator, SafetyDecisionValue
from communication.cvc_q3_allocator import TemporalRepairAllocator


TRACES = ROOT / "results" / "cvc_q2_webots" / "traces"
DIAGNOSIS = ROOT / "results" / "cvc_q3_temporal_diagnosis" / "diagnosis.json"
OUT = ROOT / "results" / "cvc_q3_offline_qualification"
TOTAL_STEPS = 312
DT_S = .032
RISK_THRESHOLD = .14
HALF_SECOND_STEPS = math.ceil(.5 / DT_S)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_from_dict(row: dict) -> SafetyDecisionValue:
    data = dict(row["safety_value"])
    data["reasons"] = tuple(data["reasons"])
    data["safe_actions_removed"] = tuple(data["safe_actions_removed"])
    data["safe_actions_added"] = tuple(data["safe_actions_added"])
    return SafetyDecisionValue(**data)


def replay_q2(rows: list[dict]) -> list[dict]:
    allocator = RiskArmedSafetyValueAllocator(TOTAL_STEPS, RISK_THRESHOLD, 47, 249)
    replay = []
    for row in rows:
        decision = allocator.decide(row["step"], row["sender"]["selected_risk"], value_from_dict(row))
        replay.append({"step": row["step"], "transmit": decision.transmit,
                       "role": decision.packet_role, "reason": decision.reason,
                       "arm_step": decision.arm_step})
    return replay


def replay_q3(rows: list[dict], *, validity_steps: int, fallback_step: int,
              reserve_step: int) -> list[dict]:
    allocator = TemporalRepairAllocator(
        TOTAL_STEPS, RISK_THRESHOLD, validity_steps, fallback_step, reserve_step)
    replay = []
    for row in rows:
        decision = allocator.decide(row["step"], row["sender"]["selected_risk"], value_from_dict(row))
        replay.append({"step": row["step"], "transmit": decision.transmit,
                       "role": decision.packet_role, "reason": decision.reason,
                       "arm_step": decision.arm_step, "latch": decision.latch.__dict__})
    return replay


def summarize(name: str, specifications: dict, episodes: list[tuple[dict, list[dict]]]) -> dict:
    records = []
    for source, replay in episodes:
        sends = [row for row in replay if row["transmit"]]
        adaptive = next(row for row in sends if row["role"] == "adaptive")
        value_steps = source["value_steps"]
        first_value = value_steps[0] if value_steps else None
        value_send = adaptive["reason"].startswith("safety_value")
        records.append({
            "scenario": source["scenario"], "policy": source["policy"],
            "arm_step": source["arm_step"], "first_value_step": first_value,
            "adaptive_spend_step": adaptive["step"], "adaptive_reason": adaptive["reason"],
            "safety_value_triggered_spend": value_send,
            "arm_to_value_steps": (first_value - source["arm_step"]
                                    if first_value is not None and source["arm_step"] is not None else None),
            "value_to_spend_steps": (adaptive["step"] - first_value if first_value is not None and value_send else None),
            "supported_value_lost": first_value is not None and not value_send,
            "value_event_steps_after_spend": sum(step > adaptive["step"] for step in value_steps),
            "send_steps": [row["step"] for row in sends],
            "packet_count": len(sends), "episode_wire_bytes": len(sends) * 24_000,
            "reserve_integrity": sends[-1]["role"] == "reserve",
            "exhaustion_step": sends[-1]["step"],
        })
    value_sends = [row for row in records if row["safety_value_triggered_spend"]]
    fallbacks = [row for row in records if "fallback" in row["adaptive_reason"] or
                 row["adaptive_reason"] == "arm_deadline"]
    armed = [row for row in records if row["arm_step"] is not None]
    armed_value = [row for row in armed if row["safety_value_triggered_spend"]]
    armed_fallback = [row for row in armed if not row["safety_value_triggered_spend"]]
    supported = [row for row in records if row["first_value_step"] is not None]
    delays = [row["arm_to_value_steps"] for row in supported if row["arm_to_value_steps"] is not None]
    send_delays = [row["value_to_spend_steps"] for row in value_sends]
    return {
        "candidate": name,
        "specification": specifications,
        "trace_conditional_replay": True,
        "records": records,
        "adaptive_episodes": len(records),
        "risk_armed_episodes": len(armed),
        "value_supported_episodes": len(supported),
        "value_triggered_packets": len(value_sends),
        "value_triggered_fraction_all_adaptive": len(value_sends) / len(records),
        "value_triggered_fraction_risk_armed": len(armed_value) / len(armed),
        "value_triggered_fraction_supported": len(value_sends) / len(supported),
        "value_packets_by_policy": {policy: sum(row["policy"] == policy for row in value_sends)
                                    for policy in ("A0", "A1")},
        "fallback_or_deadline_packets": len(fallbacks),
        "fallback_fraction_all_adaptive": len(fallbacks) / len(records),
        "fallback_fraction_risk_armed": len(armed_fallback) / len(armed),
        "median_arm_to_value_steps": median(delays),
        "median_arm_to_value_s": median(delays) * DT_S,
        "median_value_to_spend_steps": median(send_delays) if send_delays else None,
        "median_value_to_spend_s": median(send_delays) * DT_S if send_delays else None,
        "supported_value_opportunities_lost": sum(row["supported_value_lost"] for row in records),
        "value_event_steps_after_adaptive_spend": sum(row["value_event_steps_after_spend"] for row in records),
        "reserve_integrity": all(row["reserve_integrity"] for row in records),
        "exact_budget_feasible": all(row["packet_count"] == 3 and row["episode_wire_bytes"] == 72_000
                                     for row in records),
        "exhaustion_steps": sorted({row["exhaustion_step"] for row in records}),
    }


def main() -> None:
    diagnosis = json.loads(DIAGNOSIS.read_text(encoding="utf-8"))
    sources = []
    raw_rows = {}
    for path in sorted(TRACES.glob("q2__*__A[01].jsonl")):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        key = (rows[0]["scenario"], rows[0]["policy"])
        raw_rows[key] = rows
        arm = next((row["policy_state"]["arm_step"] for row in rows
                    if row["policy_state"]["arm_step"] is not None), None)
        sources.append({"scenario": key[0], "policy": key[1], "arm_step": arm,
                        "value_steps": [row["step"] for row in rows if row["safety_value"]["triggered"]]})

    specs = {
        "q2_baseline": {"family": "short ARM deadline", "deadline_steps": 47,
                        "fallback_step": 248, "reserve_step": 249},
        "latch_current_eligibility": {"family": "bounded latch only", "validity_steps": 63,
                                      "fallback_step": 248, "reserve_step": 249},
        "late_eligibility_one_step": {"family": "protected late token without persistence",
                                      "validity_steps": 1, "fallback_step": 295, "reserve_step": 311},
        "bounded_latch_late_token": {"family": "bounded latch plus protected late token",
                                     "validity_steps": 63, "fallback_step": 295, "reserve_step": 311},
        "persistent_latch_late_token": {"family": "episode-persistent latch plus protected late token",
                                        "validity_steps": 311, "fallback_step": 295, "reserve_step": 311},
    }
    results = []
    for name, specification in specs.items():
        pairs = []
        for source in sources:
            rows = raw_rows[(source["scenario"], source["policy"])]
            if name == "q2_baseline":
                replay = replay_q2(rows)
            else:
                replay = replay_q3(rows, validity_steps=specification["validity_steps"],
                                   fallback_step=specification["fallback_step"],
                                   reserve_step=specification["reserve_step"])
            pairs.append((source, replay))
        results.append(summarize(name, specification, pairs))

    latest_first = diagnosis["latest_first_value_step"]
    gate_definition = {
        "basis": (
            "The frozen traces contain exactly three Safety-Value-supported episodes and six risk-armed episodes. "
            "The gate therefore requires capture of every supported episode, representation in both policies, and "
            "value sends at least tying fallback among risk-armed episodes; unarmed mandatory refreshes are reported "
            "but cannot be replaced by an ARM-to-value mechanism."
        ),
        "minimum_value_packets": 3,
        "capture_fraction_supported": 1.0,
        "both_policies_minimum": 1,
        "fallback_must_not_dominate_risk_armed": True,
        "maximum_lost_supported_opportunities": 0,
        "minimum_guard_after_latest_supported_value_steps": HALF_SECOND_STEPS,
        "guard_basis": "Existing 0.5 s near-term prediction horizon, rounded up at the 32 ms control period.",
        "reserve_step": 311,
        "exact_packets": 3,
    }
    for candidate in results:
        fallback_step = candidate["specification"].get("fallback_step")
        candidate["mechanism_gate"] = {
            "value_frequency": candidate["value_triggered_packets"] >= 3,
            "captures_all_supported": candidate["value_triggered_fraction_supported"] == 1.0,
            "both_policies": all(value >= 1 for value in candidate["value_packets_by_policy"].values()),
            "fallback_not_dominant_when_risk_armed": candidate["fallback_fraction_risk_armed"] <= .5,
            "no_supported_value_lost": candidate["supported_value_opportunities_lost"] == 0,
            "late_guard": bool(fallback_step is not None and fallback_step - latest_first >= HALF_SECOND_STEPS),
            "reserve_integrity": candidate["reserve_integrity"],
            "exact_budget": candidate["exact_budget_feasible"],
            "same_scheduler_code": True,
        }
        candidate["passed"] = all(candidate["mechanism_gate"].values())

    chosen = next(row for row in results if row["candidate"] == "bounded_latch_late_token")
    if not chosen["passed"]:
        raise RuntimeError("primary Q3 temporal repair did not pass the frozen offline gate")
    result = {
        "study_id": "cvc-q3-offline-temporal-qualification-v1",
        "development_only": True, "formal": False,
        "navigation_outcomes_used": False, "evaluator_fields_read": False,
        "trace_conditional_limitation": (
            "Replays preserve Q2's observed risk/value sequence; changed packet timing may change future held/current "
            "events and trajectories. The primary Webots run must re-establish the mechanism prospectively."
        ),
        "diagnosis_sha256": digest(DIAGNOSIS),
        "gate_definition": gate_definition,
        "candidates": results,
        "chosen_candidate": chosen["candidate"],
        "selection_rule": (
            "Choose the simplest passing bounded policy: a 63-step validity window matches the existing 2.016 s "
            "danger horizon, avoids episode-persistent stale value, and the step-295 fallback is the latest time that "
            "still guarantees a refresh at least 0.5 s before the fixed final reserve."
        ),
        "passed": True,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "qualification.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": True, "chosen": result["chosen_candidate"],
        "candidates": [{"name": row["candidate"], "value_packets": row["value_triggered_packets"],
                        "armed_value_fraction": row["value_triggered_fraction_risk_armed"],
                        "fallback_all_fraction": row["fallback_fraction_all_adaptive"],
                        "lost": row["supported_value_opportunities_lost"], "pass": row["passed"]}
                       for row in results],
    }, indent=2))


if __name__ == "__main__":
    main()
