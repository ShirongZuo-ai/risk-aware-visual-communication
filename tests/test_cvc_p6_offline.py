from __future__ import annotations

import inspect

from scripts.qualify_cvc_p6_offline import image_age_summary, replay


def test_image_age_schedule_resets_only_at_transmissions() -> None:
    summary = image_age_summary([0, 2, 4], 6, step_ms=10)
    assert summary == {"mean_ms": 5, "maximum_ms": 10}


def test_offline_replay_does_not_read_navigation_outcomes() -> None:
    source = inspect.getsource(replay)
    for forbidden in ("evaluator", "clearance", "collision", "task_success", "forward_progress"):
        assert forbidden not in source
