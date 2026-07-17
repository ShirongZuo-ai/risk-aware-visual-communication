import math
from pathlib import Path
import tempfile
import unittest

from scripts.m3d_world_risk_common import (
    ROLE_ORDER,
    SUCCESS_CSV,
    dominant_trajectory,
    evaluate_all,
    load_success_rows,
    parse_bool,
    parse_optional_float,
    rebuild_trajectories,
    recompute_scores,
    role_acceptance,
    sensitivity_rows,
)


class M3DEvaluationHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_success_rows(SUCCESS_CSV)

    def test_parse_bool_and_optional_float(self):
        self.assertTrue(parse_bool("true"))
        self.assertFalse(parse_bool("false"))
        self.assertIsNone(parse_optional_float(""))
        self.assertAlmostEqual(parse_optional_float("0.25"), 0.25)
        with self.assertRaises(ValueError):
            parse_bool("yes")
        with self.assertRaises(ValueError):
            parse_optional_float("nan")

    def test_risk_recomputation_matches_csv(self):
        early = next(row for row in self.rows if row["obstacle_id"] == "EARLY_CONFLICT")
        planned = recompute_scores(early, "planned")
        self.assertAlmostEqual(planned["spatial_score"], float(early["planned_spatial_score"]), places=8)
        self.assertAlmostEqual(planned["temporal_score"], float(early["planned_temporal_score"]), places=8)
        self.assertAlmostEqual(planned["risk_score"], float(early["planned_risk_score"]), places=8)

    def test_dominant_trajectory(self):
        self.assertEqual(dominant_trajectory(0.5, 0.4), "planned")
        self.assertEqual(dominant_trajectory(0.4, 0.5), "state")
        self.assertEqual(dominant_trajectory(0.5, 0.5 + 1e-10, tolerance=1e-9), "tie")

    def test_role_acceptance(self):
        checks = role_acceptance({row["obstacle_id"]: row for row in self.rows})
        self.assertEqual(set(checks), set(ROLE_ORDER))
        self.assertTrue(all(checks.values()))

    def test_parameter_sensitivity_has_nine_passing_combinations(self):
        rows = sensitivity_rows(self.rows)
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(row["all_key_checks_pass"] for row in rows))
        self.assertEqual({row["sigma_distance_m"] for row in rows}, {0.025, 0.05, 0.10})
        self.assertEqual({row["tau_time_s"] for row in rows}, {0.5, 1.0, 2.0})

    def test_trajectory_rebuild_and_disagreement_consistency(self):
        trajectories = rebuild_trajectories(self.rows)
        csv_disagreement = float(self.rows[0]["trajectory_disagreement_m"])
        self.assertAlmostEqual(trajectories.max_disagreement_m, csv_disagreement, places=8)
        self.assertEqual(len(trajectories.planned), len(trajectories.state))
        self.assertGreater(trajectories.max_disagreement_m, 0.0)

    def test_disagreement_over_time_reaches_csv_max(self):
        trajectories = rebuild_trajectories(self.rows)
        max_by_series = max(distance for _time, distance in trajectories.disagreement_by_time)
        self.assertAlmostEqual(max_by_series, trajectories.max_disagreement_m, places=12)

    def test_episode_0001_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bad_path = Path(directory) / "risk_validation_episode_0001.csv"
            bad_path.write_text("episode_id,obstacle_id\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_success_rows(bad_path)

    def test_evaluate_all_returns_expected_artifacts(self):
        rows, trajectories, summary, sensitivity = evaluate_all()
        self.assertEqual(len(rows), 6)
        self.assertTrue(math.isclose(trajectories.max_disagreement_m, float(rows[0]["trajectory_disagreement_m"]), abs_tol=1e-8))
        self.assertEqual(len(summary), 6)
        self.assertEqual(len(sensitivity), 9)


if __name__ == "__main__":
    unittest.main()
