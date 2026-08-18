import json
from pathlib import Path
import tempfile
import unittest

from evaluation.m9a_ground_truth import *
from navigation.trajectory_prediction import _time_offsets
from risk_map.models import ObstacleFootprint
from scripts.m9a_formal_access import authorize_once, sha256_file
from simulator.m9a_config import *
from simulator.m9a_logging import DenseStepLogger
from simulator.m9a_scenarios import SCENARIO_GRID

class M9AI1Tests(unittest.TestCase):
    def test_grid_and_seed_matrix(self):
        self.assertEqual(len(SCENARIO_GRID), 48)
        self.assertEqual({sum(c["family_id"] == f.value for c in SCENARIO_GRID) for f in ScenarioFamily}, {6})
        seen = set()
        counts = {Split.PILOT: 1, Split.CALIBRATION: 2, Split.FORMAL: 3}
        for split, reps in counts.items():
            for family in ScenarioFamily:
                for p in range(1, 7):
                    for replicate in range(reps):
                        seed = seed_for(split, family, f"P{p:02d}", replicate)
                        self.assertEqual(seed, seed_for(split, family, f"P{p:02d}", replicate)); self.assertNotIn(seed, seen); seen.add(seed)
        self.assertEqual(len(seen), 288)

    def test_contact_cases_and_grouping(self):
        obstacle = EligibleCounterpart("BOX", 10, "obstacle")
        def paired(t):
            raw = (RawContactObservation(t, 99, None, (0,0,0)),)
            return match_dual_sided_contacts(ContactSet("ROBOT", 1, raw), {obstacle: ContactSet("BOX", 10, raw)})
        events = group_collision_events([paired(1.0), paired(1.1), paired(2.0)])
        self.assertEqual(len(events), 2); self.assertEqual(events[0].end_s, 1.1)
        self.assertEqual(group_collision_events([]), ())  # stationary/safe pass

    def test_exact_horizons_and_labels(self):
        states = [ActualState(i*.032, i*.032, .08) for i in range(80)]
        expected = {0.5:(16,.625), 1.0:(32,.25), 2.0:(63,.5)}
        box = ObstacleFootprint("box", .3, .06, .04, .04)
        for horizon, (points, fraction) in expected.items():
            window = extract_exact_horizon(states, 0, horizon)
            self.assertEqual(len(_time_offsets(horizon, .032)), points)
            self.assertAlmostEqual(window.states[-1].timestamp_s, horizon)
            self.assertEqual(window.full_intervals, points-1); self.assertAlmostEqual(window.interpolation_fraction, fraction)
        window = extract_exact_horizon(states, 3, .5); self.assertAlmostEqual(window.states[-1].timestamp_s, states[3].timestamp_s+.5)
        clearance = actual_future_min_clearance(window, [box]); self.assertTrue(near_collision_within_H(clearance, False, .026))
        event = ValidatedCollisionEvent(states[3].timestamp_s+.5, states[3].timestamp_s+.6, (10,))
        self.assertTrue(collision_within_H(states[3].timestamp_s, .5, [event]))
        self.assertFalse(collision_within_H(event.start_s, .5, [event]))
        self.assertIsNone(extract_exact_horizon(states[:18], 3, .5))

    def test_logger_and_formal_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); log=root/"steps.jsonl"
            record={k:{} for k in []}; record.update({"schema_version":"m9a-step-log-v2","protocol_version":"m9a-p-v1","episode_id":"e","split":"pilot","scenario_family":"F1","parameter_set_id":"P01","seed":910000,"timestep_index":0,"timestamp_s":.032,"basic_timestep_s":.032,"robot_state":{},"applied_command":{},"future_command_schedule":{},"obstacles":[],"robot_footprint":{},"raw_contact_observation":{"raw_contact_point_count":0,"points":[]},"validated_collision_event":{"collision_active":False},"provenance":{}})
            DenseStepLogger(log).append(record); self.assertEqual(len(log.read_text().splitlines()),1)
            artifacts={}; expected={}
            for name in ("protocol","schema","manifest","calibration"):
                path=root/f"{name}.json"; path.write_text(name); artifacts[name]=path; expected[name]=sha256_file(path)
            ledger=root/"ledger.jsonl"
            with self.assertRaises(PermissionError): authorize_once(formal_unlock=False, authorization_id="M9A-ABCDEFGH", actor="test", ledger=ledger, expected_digests=expected, artifact_paths=artifacts)
            authorize_once(formal_unlock=True, authorization_id="M9A-ABCDEFGH", actor="test", ledger=ledger, expected_digests=expected, artifact_paths=artifacts)
            self.assertEqual(json.loads(ledger.read_text())["new_state"],"authorized_once")
            with self.assertRaises(PermissionError): authorize_once(formal_unlock=True, authorization_id="M9A-IJKLMNOP", actor="test", ledger=ledger, expected_digests=expected, artifact_paths=artifacts)

if __name__ == "__main__": unittest.main()
