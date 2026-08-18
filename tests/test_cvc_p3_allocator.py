from __future__ import annotations

from communication.cvc_p3_allocator import AllocatorSpec, CausalRiskAllocator, uniform_schedule


def run(risks: list[float], quota: int, spec: AllocatorSpec) -> tuple[list[int], CausalRiskAllocator]:
    allocator = CausalRiskAllocator(len(risks), quota, spec)
    sent = [step for step, risk in enumerate(risks) if allocator.decide(step, risk).transmit]
    return sent, allocator


def test_threshold_converts_prediction_lead_without_future_debt() -> None:
    r0 = [0.05] * 8 + [0.2] * 12
    r1 = [0.05] * 5 + [0.2] * 15
    spec = AllocatorSpec("threshold", threshold=0.14)
    s0, a0 = run(r0, 3, spec)
    s1, a1 = run(r1, 3, spec)
    assert s0[1] - s1[1] == 3
    assert len(s0) == len(s1) == 3
    assert a0.sent == a1.sent == 3


def test_all_simple_families_finish_with_exact_quota() -> None:
    risks = [0.05] * 5 + [0.08, 0.12, 0.18, 0.26] + [0.2] * 31
    specs = (
        AllocatorSpec("threshold", threshold=0.14),
        AllocatorSpec("derivative", derivative_threshold=0.03),
        AllocatorSpec("integral", integral_threshold=0.08),
        AllocatorSpec("hazard_bucket", hazard_thresholds=(0.12, 0.18, 0.24)),
    )
    for spec in specs:
        schedule, allocator = run(risks, 6, spec)
        assert len(schedule) == 6
        assert allocator.sent == 6
        assert schedule[0] == 0


def test_uniform_schedule_is_exact_and_ordered() -> None:
    for count in (3, 4, 6):
        schedule = uniform_schedule(437, count)
        assert len(schedule) == count
        assert schedule[0] == 0
        assert schedule[-1] == 436
        assert list(schedule) == sorted(set(schedule))
