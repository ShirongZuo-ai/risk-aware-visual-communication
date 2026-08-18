"""Evaluator-only physical reference and post-hoc CVC-P7 classifications."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicalSafetyReference:
    relevant: tuple[bool, ...]
    danger_onset_step: int | None
    minimum_clearance_step: int
    minimum_clearance_m: float


def physical_safety_reference(
    clearances_m: list[float],
    contacts: list[bool],
    threshold_m: float = 0.12,
    future_horizon_steps: int = 63,
) -> PhysicalSafetyReference:
    """Label pre-danger windows using evaluator truth unavailable to the sender."""
    if not clearances_m or len(clearances_m) != len(contacts):
        raise ValueError("aligned non-empty clearance/contact series required")
    if threshold_m <= 0.0 or future_horizon_steps < 1:
        raise ValueError("invalid physical safety-window definition")
    danger = next((index for index, (clearance, contact) in enumerate(zip(clearances_m, contacts))
                   if clearance <= threshold_m or contact), None)
    minimum_step = min(range(len(clearances_m)), key=clearances_m.__getitem__)
    relevant: list[bool] = []
    for step in range(len(clearances_m)):
        end = min(len(clearances_m), step + future_horizon_steps + 1)
        future_danger = any(
            clearances_m[index] <= threshold_m or contacts[index]
            for index in range(step, end)
        )
        relevant.append(bool(future_danger and step <= minimum_step))
    return PhysicalSafetyReference(tuple(relevant), danger, minimum_step, clearances_m[minimum_step])


def classify_spend(
    safety_relevant: bool,
    delta_v_m_s: float,
    slowdown_event: bool,
    increased_turn_event: bool,
    turn_away_from_obstacle: bool,
    progress_threshold_m_s: float = 0.005,
) -> str:
    """Classify a P6 spend from frozen diagnostics, never as sender logic."""
    progress = delta_v_m_s >= abs(progress_threshold_m_s)
    protective = safety_relevant and (slowdown_event or (increased_turn_event and turn_away_from_obstacle))
    if progress and protective:
        return "mixed"
    if protective:
        return "mainly_safety_protective"
    if progress:
        return "mainly_progress_enabling"
    return "negligible_or_ambiguous"
