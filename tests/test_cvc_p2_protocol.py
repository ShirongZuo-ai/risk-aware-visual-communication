from __future__ import annotations

from PIL import Image, ImageDraw

from communication.cvc_p2_protocol import ExactQuotaScheduler, predictive_risk, spatial_qualities


def test_uniform_and_adaptive_schedulers_finish_with_exact_same_quota() -> None:
    risks = [0.0] * 15 + [0.3] * 10 + [0.0] * 15
    schedules = []
    for adaptive in (False, True):
        scheduler = ExactQuotaScheduler(len(risks), 8, adaptive)
        schedule = [scheduler.decide(step, risk)[0] for step, risk in enumerate(risks)]
        assert sum(schedule) == 8
        schedules.append(schedule)
    assert schedules[0] != schedules[1]


def test_spatial_allocation_uses_only_image_localized_roi() -> None:
    image = Image.new("RGB", (160, 120), "white")
    ImageDraw.Draw(image).rectangle((68, 45, 91, 82), fill=(220, 10, 10))
    qualities, roi = spatial_qualities(image, "S", 0.4)
    assert roi
    assert set(qualities) == {7, 82}
    assert all(qualities[tile] == 82 for tile in roi)


def test_predictive_risk_is_causal_bounded_and_anticipates_growth() -> None:
    assert predictive_risk(0.10, 0.05, 0.0) > 0.10
    assert predictive_risk(0.10, 0.12, 0.0) == 0.10
    assert predictive_risk(0.9, 0.0, 0.0) == 1.0
