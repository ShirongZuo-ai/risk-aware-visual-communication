from __future__ import annotations

from communication.cvc_p4_allocator import ReserveSpec, SingleAdaptiveReserveAllocator, p4_uniform_schedule


def schedule(risks: list[float], spec: ReserveSpec) -> tuple[list[int], list[str]]:
    allocator = SingleAdaptiveReserveAllocator(len(risks), spec)
    decisions = [allocator.decide(step, risk) for step, risk in enumerate(risks)]
    return ([step for step, decision in enumerate(decisions) if decision.transmit],
            [decision.packet_role for decision in decisions if decision.transmit])


def test_fixed_late_converts_lead_but_exhaustion_time_is_identical() -> None:
    r0 = [0.05] * 20 + [0.2] * 40
    r1 = [0.05] * 8 + [0.2] * 52
    spec = ReserveSpec("fixed_late", fixed_late_step=40)
    s0, roles0 = schedule(r0, spec)
    s1, roles1 = schedule(r1, spec)
    assert s0 == [0, 20, 40]
    assert s1 == [0, 8, 40]
    assert roles0 == roles1 == ["startup", "adaptive", "reserve"]


def test_repeated_crossings_cannot_spend_the_reserve_early() -> None:
    risks = [0.05, 0.2, 0.05, 0.2, 0.05, 0.2] + [0.05] * 54
    sent, roles = schedule(risks, ReserveSpec("fixed_late", fixed_late_step=40))
    assert sent == [0, 1, 40]
    assert roles == ["startup", "adaptive", "reserve"]


def test_no_trigger_uses_adaptive_deadline_without_losing_reserve() -> None:
    sent, _ = schedule([0.05] * 60, ReserveSpec("fixed_late", fixed_late_step=40))
    assert sent == [0, 39, 40]


def test_uniform_schedule_shares_startup_and_late_reserve() -> None:
    assert p4_uniform_schedule(218) == (0, 109, 218)
