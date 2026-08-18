from evaluation.cvc_q5_qualification import contiguous_runs, gate_results, onset_opportunity


def test_contiguous_runs_are_exact():
    assert contiguous_runs([7, 2, 3, 4, 9, 9]) == [(2, 4), (7, 7), (9, 9)]


def test_opportunity_is_strictly_pre_onset_and_reports_persistence():
    flags = [False] * 20
    flags[10:15] = [True] * 5
    flags[15] = True  # onset itself must not count
    row = onset_opportunity(flags, 15, max_lead_steps=8, step_s=.032)
    assert row["active_samples"] == 5
    assert row["lead_s"] == 5 * .032
    assert row["strict_jitter_robustness"]["plus_minus_2_steps"]
    assert not row["strict_jitter_robustness"]["plus_minus_3_steps"]


def test_missed_opportunity():
    row = onset_opportunity([False] * 12, 10, max_lead_steps=5, step_s=.032)
    assert not row["covered"] and row["opportunity_class"] == "missed"


def test_gate_boundary_is_inclusive():
    metrics = {
        "pooled_coverage": .75, "median_lead_s": .25, "active_fraction": .02,
        "event_free_episode_activation_fraction": .25, "covered_usable_fraction": .5,
        "per_family": {str(i): {"onset_count": 1, "coverage": .5} for i in range(3)},
    }
    gates = {
        "A_pooled_onset_coverage_min": .75, "B_family_coverage_min": .5,
        "B_positive_families_meeting_min": 3, "C_median_lead_s_min": .25,
        "D_active_fraction_max": .02, "E_event_free_episode_activation_max": .25,
        "F_covered_onsets_usable_opportunity_min": .5,
    }
    assert all(gate_results(metrics, gates).values())
