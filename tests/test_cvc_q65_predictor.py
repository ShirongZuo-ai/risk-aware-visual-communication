from dataclasses import dataclass
import math

import pytest

from communication.cvc_q65_predictor import FrozenOpportunityPredictor
from communication.cvc_q65_scheduler import OpportunityValueScheduler


def predictor(intercept=0.0):
    return FrozenOpportunityPredictor({
        "feature_names": ["x"], "imputer_median": [0.0],
        "standardizer_mean": [0.0], "standardizer_scale": [2.0],
        "coefficients": [2.0], "intercept": intercept,
        "decision_threshold": 0.5,
    })


def test_pure_python_probability_matches_logistic_formula():
    value = predictor().probability({"x": 2.0})
    assert value == pytest.approx(1 / (1 + math.exp(-2.0)))
    assert predictor().send({"x": 2.0})


def test_invalid_model_dimensions_rejected():
    with pytest.raises(ValueError):
        FrozenOpportunityPredictor({"feature_names":["x"],"imputer_median":[],
            "standardizer_mean":[0],"standardizer_scale":[1],"coefficients":[1],
            "intercept":0,"decision_threshold":.5})


@dataclass
class Signals:
    precursor_active: bool = False


@dataclass
class Q6Context:
    signals: Signals


class FeatureState:
    def __init__(self): self.q6_context = Q6Context(Signals())
    def features(self, step, last_send_step, fallback_step): return {"x": 1.0}


@dataclass
class Value:
    triggered: bool = False


def test_scheduler_spends_at_first_positive_clock_opportunity():
    scheduler = OpportunityValueScheduler(total_steps=230, predictor=predictor(),
        feature_state=FeatureState(), candidate_start_step=24,
        candidate_end_step=180, clock_steps=(80,109,144), fallback_step=217,
        reserve_step=218)
    decisions = [scheduler.decide(step, 0.0, Value()) for step in range(230)]
    assert [i for i,row in enumerate(decisions) if row.transmit] == [0,80,218]
    assert decisions[80].opportunity_probability is not None


def test_scheduler_holds_negative_opportunities_until_fallback():
    scheduler = OpportunityValueScheduler(total_steps=230, predictor=predictor(-10.0),
        feature_state=FeatureState(), candidate_start_step=24,
        candidate_end_step=180, clock_steps=(80,109,144), fallback_step=217,
        reserve_step=218)
    decisions = [scheduler.decide(step, 0.0, Value()) for step in range(230)]
    assert [i for i,row in enumerate(decisions) if row.transmit] == [0,217,218]
