import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from scripts.m6a_trusted_artifacts import digest
from scripts.m7_visual_voi import VisualVoIInput, _tile_cache
from scripts.m7_visual_voi_v2 import (
    CANDIDATES,
    CANDIDATE_CONFIGS,
    FAIRNESS_FRACTION,
    PROVENANCE_PATH,
    QUALITY_LADDER,
    SUMMARY_PATH,
    V1_SUMMARY_PATH,
    V1_SUMMARY_SHA256,
    MatchedByteEnvelope,
    _container,
    _metadata,
    allocate_v2,
    choose_candidate,
    load_v2_summary,
    prepare_v2,
    validate_v2_provenance,
    validate_v2_provenance_bundle,
    validate_v2_provenance_record,
)


class M7VisualVoIV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        y, x = np.indices((120, 160))
        image = np.stack(((3 * x + y) % 256, (x + 4 * y) % 256, (2 * x + 3 * y) % 256), axis=-1).astype(np.uint8)
        snapshot = SimpleNamespace(snapshot_id="0", image=image,
                                   raw_image_sha256=hashlib.sha256(image.tobytes()).hexdigest())
        state = np.zeros((120, 160), dtype=float); state[35:65, 45:95] = 1
        command = np.zeros_like(state); command[45:80, 65:125] = 1
        cls.value = VisualVoIInput.create(snapshot=snapshot, state_mask=tuple(state.ravel()),
                                          command_mask=tuple(command.ravel()),
                                          state_mask_sha256=digest(tuple(state.ravel())),
                                          command_mask_sha256=digest(tuple(command.ravel())))
        cls.prepared = prepare_v2(cls.value, tile_cache=_tile_cache(image))

    def _envelope(self, candidate_id="v2_corridor_edges"):
        _, payload = _container(self.prepared["encoded"], [35] * 48)
        reference = len(payload) + len(_metadata(candidate_id)) + 100
        return MatchedByteEnvelope.create(budget="high", budget_bytes=50_000,
                                          state_only_bytes=reference - 10,
                                          command_conditioned_bytes=reference + 10)

    def test_candidate_set_is_frozen_and_limited(self):
        self.assertEqual(CANDIDATES, ("v2_global_only", "v2_visible_edges", "v2_corridor_edges"))
        self.assertEqual(CANDIDATE_CONFIGS["v2_corridor_edges"],
                         {"corridor_edges": .5, "projected_corridor": .3, "whole_tile": .2})
        self.assertEqual(QUALITY_LADDER, (1, 5, 15, 25, 35, 45, 55, 65, 75, 95))

    def test_envelope_uses_lower_integer_midpoint(self):
        envelope = MatchedByteEnvelope.create(budget="low", budget_bytes=32_374,
                                              state_only_bytes=32_101, command_conditioned_bytes=32_110)
        self.assertEqual(envelope.midpoint_cap_bytes, 32_105)
        self.assertEqual(envelope.tolerance_bytes, FAIRNESS_FRACTION * 32_374)
        self.assertIs(envelope.validate(), envelope)

    def test_envelope_tamper_is_rejected(self):
        envelope = self._envelope()
        bad = copy.copy(envelope)
        object.__setattr__(bad, "midpoint_cap_bytes", envelope.midpoint_cap_bytes + 1)
        with self.assertRaises(ValueError):
            bad.validate()

    def test_allocator_is_deterministic_and_byte_matched(self):
        envelope = self._envelope()
        first = allocate_v2(self.value, "v2_corridor_edges", envelope, prepared=self.prepared)
        second = allocate_v2(self.value, "v2_corridor_edges", envelope, prepared=self.prepared)
        self.assertEqual(first.case_digest, second.case_digest)
        self.assertEqual(first.payload, second.payload)
        self.assertLessEqual(first.charged_bytes, envelope.midpoint_cap_bytes)
        self.assertLessEqual(abs(first.charged_bytes - envelope.state_only_bytes), envelope.tolerance_bytes)
        self.assertLessEqual(abs(first.charged_bytes - envelope.command_conditioned_bytes), envelope.tolerance_bytes)

    def test_minimum_quality_floor_is_never_violated(self):
        case = allocate_v2(self.value, "v2_visible_edges", self._envelope("v2_visible_edges"), prepared=self.prepared)
        floor = case.provenance["minimum_quality_floor"]
        self.assertTrue(all(quality >= floor for quality in case.qualities))
        self.assertEqual(min(case.qualities), floor)

    def test_every_selected_increment_recomputes_exact_container_bytes(self):
        case = allocate_v2(self.value, "v2_global_only", self._envelope("v2_global_only"), prepared=self.prepared)
        for transition in case.provenance["chosen_transitions"]:
            self.assertEqual(transition["charged_bytes_after"] - transition["charged_bytes_before"],
                             transition["exact_delta_bytes"])
        self.assertGreaterEqual(case.provenance["exact_container_recomputations"],
                                len(case.provenance["chosen_transitions"]))

    def test_provenance_tamper_is_rejected(self):
        case = allocate_v2(self.value, "v2_corridor_edges", self._envelope(), prepared=self.prepared)
        tampered = copy.deepcopy(case.provenance); tampered["minimum_quality_floor"] = 95
        with self.assertRaises(ValueError):
            validate_v2_provenance(tampered)

    def test_record_tamper_is_rejected_even_after_inner_validation(self):
        case = allocate_v2(self.value, "v2_corridor_edges", self._envelope(), prepared=self.prepared)
        record = {"schema_version": "m7-v2-allocation-record-v1", "episode_id": "episode",
                  "scene": "M7C1", "seed": 1, "deterministic_double_run": True,
                  "allocation": case.provenance}
        record["record_digest"] = digest(record)
        validate_v2_provenance_record(record)
        record["scene"] = "M7C2"
        with self.assertRaises(ValueError):
            validate_v2_provenance_record(record)

    def test_provenance_bundle_rejects_incomplete_or_tampered_records(self):
        case = allocate_v2(self.value, "v2_corridor_edges", self._envelope(), prepared=self.prepared)
        record = {"schema_version": "m7-v2-allocation-record-v1", "episode_id": "episode",
                  "scene": "M7C1", "seed": 1, "deterministic_double_run": True,
                  "allocation": case.provenance}
        record["record_digest"] = digest(record)
        bundle = {"schema_version": "m7-visual-voi-v2-provenance-v1", "allocations": [record]}
        bundle["canonical_digest"] = digest(bundle)
        with self.assertRaises(ValueError):
            validate_v2_provenance_bundle(bundle)

    def test_future_and_evaluator_inputs_are_rejected(self):
        snapshot = SimpleNamespace(snapshot_id="0", image=self.value.image,
                                   raw_image_sha256=self.value.raw_image_sha256)
        for forbidden in ("actual_future", "evaluator_only_geometry", "tcobr_labels", "evaluation_mask"):
            with self.subTest(forbidden=forbidden), self.assertRaises(ValueError):
                VisualVoIInput.create(snapshot=snapshot, state_mask=self.value.state_mask,
                                      command_mask=self.value.command_mask,
                                      state_mask_sha256=self.value.state_mask_sha256,
                                      command_mask_sha256=self.value.command_mask_sha256,
                                      **{forbidden: object()})

    def test_nonzero_leakage_fails_closed(self):
        bad = copy.copy(self.value); object.__setattr__(bad, "actual_future_usage", 1)
        with self.assertRaises(ValueError):
            allocate_v2(bad, "v2_corridor_edges", self._envelope(), prepared=self.prepared)

    def test_candidate_selection_requires_all_nine_gates(self):
        def result(minimum, critical, failed=False):
            gates = [{"passed": not failed} for _ in range(9)]
            return {"gates": gates, "details": {"leave_one_scene_out": {"M7C1": minimum, "M7C2": minimum + .01},
                                                  "critical_psnr_db": {"severe": critical, "low": critical + .01}}}
        results = {"v2_global_only": result(.01, -.1), "v2_visible_edges": result(.02, -.2),
                   "v2_corridor_edges": result(.03, -.05, failed=True)}
        self.assertEqual(choose_candidate(results), "v2_visible_edges")
        for item in results.values(): item["gates"][0]["passed"] = False
        self.assertIsNone(choose_candidate(results))

    def test_persisted_summary_and_provenance_reload(self):
        summary = load_v2_summary(SUMMARY_PATH)
        self.assertEqual(summary["decision"], "NO-GO")
        self.assertIsNone(summary["selected_candidate"])
        validate_v2_provenance_bundle(json.loads(PROVENANCE_PATH.read_text(encoding="utf-8")))

    def test_summary_json_tamper_is_rejected(self):
        value = json.loads(SUMMARY_PATH.read_text(encoding="utf-8")); value["decision"] = "GO"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_v2_summary(path)

    def test_frozen_v1_summary_is_unchanged(self):
        self.assertEqual(hashlib.sha256(V1_SUMMARY_PATH.read_bytes()).hexdigest(), V1_SUMMARY_SHA256)


if __name__ == "__main__":
    unittest.main()
