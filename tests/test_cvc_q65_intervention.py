from dataclasses import dataclass
import pytest

from communication.cvc_q65_intervention import OpportunityInterventionScheduler, opportunity_label


@dataclass
class Signals:
    precursor_active: bool = False


@dataclass
class Context:
    signals: Signals


@dataclass
class Value:
    triggered: bool = False


def scheduler(branch, probe=40):
    return OpportunityInterventionScheduler(
        total_steps=80, branch=branch, probe_step=None if branch == "D" else probe,
        min_later_gap_steps=5, candidate_start_step=10, candidate_end_step=60,
        fallback_step=65, reserve_step=66, context=Context(Signals()),
    )


def run(item, signals=()):
    decisions = []
    for step in range(80):
        item.context.signals.precursor_active = step in signals
        decisions.append(item.decide(step, 0.0, Value(False)))
    return decisions


def test_send_branch_spends_at_probe_and_exactly_three_packets():
    rows = run(scheduler("S"))
    assert [i for i, row in enumerate(rows) if row.transmit] == [0, 40, 66]


def test_hold_branch_waits_for_next_causal_onset():
    rows = run(scheduler("H"), signals=(50, 51))
    assert [i for i, row in enumerate(rows) if row.transmit] == [0, 51, 66]
    assert rows[51].reason == "next_causal_opportunity"


def test_hold_and_discovery_use_fallback_without_later_event():
    assert [i for i, row in enumerate(run(scheduler("H"))) if row.transmit] == [0, 65, 66]
    assert [i for i, row in enumerate(run(scheduler("D"))) if row.transmit] == [0, 65, 66]


def test_invalid_probe_rejected():
    with pytest.raises(ValueError):
        OpportunityInterventionScheduler(total_steps=80, branch="S", probe_step=9,
            min_later_gap_steps=5, candidate_start_step=10, candidate_end_step=60,
            fallback_step=65, reserve_step=66, context=Context(Signals()))


def metrics(collision=False, danger=10, clearance=.2, progress=.5):
    return {"collision": collision, "danger_steps": danger,
            "min_clearance_m": clearance, "goal_progress_m": progress}


def test_utility_is_lexicographic_and_progress_noncompensatory():
    assert opportunity_label(metrics(False, 100, .01), metrics(True, 0, .5))["label"] == "helpful"
    result = opportunity_label(metrics(False, 6, .20, .40), metrics(False, 10, .40, .50))
    assert result["label"] == "helpful"
    assert result["basis"] == "danger_steps"
    assert result["task_adverse"]


def test_utility_indifference_bands():
    assert opportunity_label(metrics(danger=8, clearance=.2005), metrics(danger=10, clearance=.2))["label"] == "neutral"
    assert opportunity_label(metrics(danger=10, clearance=.198), metrics(danger=10, clearance=.2))["label"] == "harmful"
