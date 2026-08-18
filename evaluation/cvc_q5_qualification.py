"""Frozen CVC-Q5 opportunity and generalization metric primitives."""
from __future__ import annotations

from collections.abc import Sequence


def contiguous_runs(indices: Sequence[int]) -> list[tuple[int, int]]:
    if not indices:
        return []
    ordered = sorted(set(indices))
    runs: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for index in ordered[1:]:
        if index != previous + 1:
            runs.append((start, previous))
            start = index
        previous = index
    runs.append((start, previous))
    return runs


def onset_opportunity(
    precursor: Sequence[bool], onset: int, *, max_lead_steps: int, step_s: float,
) -> dict:
    if onset < 0 or onset >= len(precursor) or max_lead_steps < 1 or step_s <= 0:
        raise ValueError("invalid precursor opportunity request")
    active = [index for index in range(max(0, onset - max_lead_steps), onset)
              if precursor[index]]
    runs = contiguous_runs(active)
    longest = max((end - start + 1 for start, end in runs), default=0)
    covered = bool(active)
    return {
        "onset_step": onset,
        "covered": covered,
        "first_active_step": active[0] if active else None,
        "last_active_step": active[-1] if active else None,
        "lead_s": (onset - active[0]) * step_s if active else None,
        "last_gap_s": (onset - active[-1]) * step_s if active else None,
        "active_samples": len(active),
        "active_duration_s": len(active) * step_s,
        "run_count": len(runs),
        "longest_run_samples": longest,
        "longest_run_s": longest * step_s,
        "persistent_2_samples": longest >= 2,
        "persistent_3_samples": longest >= 3,
        "usable_opportunity": longest >= 2,
        "opportunity_class": (
            "missed" if not active else "isolated" if len(active) == 1
            else "stable" if longest >= 3 else "intermittent"
        ),
        "strict_jitter_robustness": {
            "plus_minus_1_step": longest >= 3,
            "plus_minus_2_steps": longest >= 5,
            "plus_minus_3_steps": longest >= 7,
        },
    }


def gate_results(metrics: dict, gates: dict) -> dict[str, bool]:
    per_family = metrics["per_family"]
    family_passes = sum(
        row["onset_count"] > 0 and row["coverage"] >= gates["B_family_coverage_min"]
        for row in per_family.values()
    )
    return {
        "A_pooled_coverage": metrics["pooled_coverage"] >= gates["A_pooled_onset_coverage_min"],
        "B_cross_family_coverage": family_passes >= gates["B_positive_families_meeting_min"],
        "C_median_lead": metrics["median_lead_s"] is not None
        and metrics["median_lead_s"] >= gates["C_median_lead_s_min"],
        "D_active_fraction": metrics["active_fraction"] <= gates["D_active_fraction_max"],
        "E_event_free_activation": metrics["event_free_episode_activation_fraction"]
        <= gates["E_event_free_episode_activation_max"],
        "F_usable_opportunity": metrics["covered_usable_fraction"]
        >= gates["F_covered_onsets_usable_opportunity_min"],
    }
