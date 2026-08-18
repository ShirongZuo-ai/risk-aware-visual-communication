from __future__ import annotations

import inspect

from scripts.calibrate_cvc_p6_novelty import q25_step, simulate


def test_q25_is_signal_only() -> None:
    assert q25_step([0.0, 1.0, 1.0, 2.0]) == 1
    assert q25_step([0.0, 0.0]) is None


def test_calibration_simulator_has_no_navigation_outcome_access() -> None:
    source = inspect.getsource(simulate)
    for forbidden in ("evaluator", "clearance", "collision", "task_success", "forward_progress"):
        assert forbidden not in source
