import copy
import inspect
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.m6a_trusted_artifacts import digest
from scripts.m8_evaluator_reference import (
    CCORFConfig,
    CCORFInput,
    evaluate_ccorf,
    validate_ccorf_evidence,
)
from scripts.m8_proxy_common import (
    ProxyIdentity,
    load_canonical_evidence,
    persist_canonical_evidence,
    sequence_diagnostics,
)
from scripts.m8_proxy_synthetic import (
    JPEG_QUALITY_LADDER,
    controlled_perturbations,
    jpeg_reconstruction,
    synthetic_fixture,
    synthetic_identity,
)
from scripts.m8_sender_proxies import (
    FROPUConfig,
    FROPUInput,
    STRCFConfig,
    STRCFInput,
    evaluate_fropu,
    evaluate_strcf,
    validate_fropu_evidence,
    validate_strcf_evidence,
)
from scripts.validate_m8b0_proxies import build_report, validate_report


class M8ProxyPrimitiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = synthetic_fixture()
        cls.perturbations = controlled_perturbations(cls.fixture)

    def fropu_input(self, name: str = "perfect") -> FROPUInput:
        return FROPUInput.create(
            identity=synthetic_identity(name),
            original=self.fixture["original"],
            reconstruction=self.perturbations[name],
            union_corridor=self.fixture["union_corridor"],
        )

    def strcf_input(self, name: str = "perfect") -> STRCFInput:
        return STRCFInput.create(
            identity=synthetic_identity(name),
            original=self.fixture["original"],
            reconstruction=self.perturbations[name],
            union_risk=self.fixture["union_risk"],
            union_uncertainty=self.fixture["union_uncertainty"],
        )

    def ccorf_input(self, name: str = "perfect") -> CCORFInput:
        return CCORFInput.create(
            identity=synthetic_identity(name),
            original=self.fixture["original"],
            reconstruction=self.perturbations[name],
            critical_obstacle_mask=self.fixture["critical_obstacle_mask"],
            critical_boundary_mask=self.fixture["critical_boundary_mask"],
            geometry_digest=self.fixture["geometry_digest"],
        )

    def test_frozen_config_constants(self) -> None:
        fropu = FROPUConfig()
        strcf = STRCFConfig()
        ccorf = CCORFConfig()
        fropu.validate()
        strcf.validate()
        ccorf.validate()
        self.assertEqual((fropu.canny_low, fropu.canny_high), (50, 150))
        self.assertEqual((fropu.iou_weight, fropu.centroid_weight, fropu.boundary_weight), (0.4, 0.3, 0.3))
        self.assertEqual((strcf.weight_floor, strcf.risk_weight, strcf.uncertainty_weight), (0.05, 0.475, 0.475))
        self.assertEqual((ccorf.soft_boundary_weight, ccorf.obstacle_ssim_weight, ccorf.inverse_rgb_error_weight), (0.5, 0.3, 0.2))

    def test_frozen_config_tampering_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "frozen FROPU"):
            FROPUConfig(centroid_scale_px=19.0).validate()
        with self.assertRaisesRegex(ValueError, "frozen STRCF"):
            STRCFConfig(risk_weight=0.474, uncertainty_weight=0.476).validate()
        with self.assertRaisesRegex(ValueError, "frozen CCORF"):
            CCORFConfig(soft_boundary_weight=0.49, obstacle_ssim_weight=0.31).validate()

    def test_all_three_perfect_scores_are_one(self) -> None:
        self.assertEqual(evaluate_fropu(self.fropu_input())["score"], 1.0)
        self.assertEqual(evaluate_strcf(self.strcf_input())["score"], 1.0)
        self.assertEqual(evaluate_ccorf(self.ccorf_input())["score"], 1.0)

    def test_evidence_is_deterministic(self) -> None:
        for evaluator, value in (
            (evaluate_fropu, self.fropu_input("compression_q15")),
            (evaluate_strcf, self.strcf_input("compression_q15")),
            (evaluate_ccorf, self.ccorf_input("compression_q15")),
        ):
            with self.subTest(evaluator=evaluator.__name__):
                self.assertEqual(evaluator(value), evaluator(value))

    def test_sender_boundary_rejects_every_frozen_forbidden_field(self) -> None:
        fields = (
            "actual_future_trajectory",
            "future_frame",
            "ground_truth_obstacle_geometry",
            "tcobr",
            "eligibility_label",
            "ccorf",
            "evaluator_mask",
            "navigation_outcome",
        )
        for field in fields:
            with self.subTest(proxy="fropu", field=field), self.assertRaisesRegex(ValueError, "forbidden"):
                FROPUInput.create(
                    identity=synthetic_identity(),
                    original=self.fixture["original"],
                    reconstruction=self.fixture["original"],
                    union_corridor=self.fixture["union_corridor"],
                    **{field: object()},
                )
            with self.subTest(proxy="strcf", field=field), self.assertRaisesRegex(ValueError, "forbidden"):
                STRCFInput.create(
                    identity=synthetic_identity(),
                    original=self.fixture["original"],
                    reconstruction=self.fixture["original"],
                    union_risk=self.fixture["union_risk"],
                    union_uncertainty=self.fixture["union_uncertainty"],
                    **{field: object()},
                )

    def test_sender_module_has_no_evaluator_reference_import(self) -> None:
        import scripts.m8_sender_proxies as sender

        source = inspect.getsource(sender)
        self.assertNotIn("m8_evaluator_reference", source)
        self.assertFalse(hasattr(sender, "CCORFInput"))
        self.assertNotIn("m7_visual_voi", source)

    def test_unknown_and_missing_sender_inputs_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown"):
            FROPUInput.create(
                identity=synthetic_identity(),
                original=self.fixture["original"],
                reconstruction=self.fixture["original"],
                union_corridor=self.fixture["union_corridor"],
                arbitrary_payload=1,
            )
        with self.assertRaises(TypeError):
            FROPUInput.create(
                identity=synthetic_identity(),
                original=self.fixture["original"],
                reconstruction=self.fixture["original"],
            )

    def test_invalid_shapes_and_nonfinite_fields_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "shape"):
            FROPUInput.create(
                identity=synthetic_identity(),
                original=self.fixture["original"][:-1],
                reconstruction=self.fixture["original"][:-1],
                union_corridor=self.fixture["union_corridor"][:-1],
            )
        bad = np.array(self.fixture["union_risk"], copy=True)
        bad[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            STRCFInput.create(
                identity=synthetic_identity(),
                original=self.fixture["original"],
                reconstruction=self.fixture["original"],
                union_risk=bad,
                union_uncertainty=self.fixture["union_uncertainty"],
            )

    def test_identity_mismatch_rejected(self) -> None:
        value = self.fropu_input()
        evidence = evaluate_fropu(value)
        wrong = ProxyIdentity.create(
            identity_id=value.identity.identity_id,
            split=value.identity.split,
            scene=value.identity.scene,
            episode_id=value.identity.episode_id,
            seed=value.identity.seed,
            snapshot_id=value.identity.snapshot_id,
            reconstruction_id="different",
        )
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            validate_fropu_evidence(evidence, expected_identity=wrong)

    def test_empty_fropu_domain_is_undefined(self) -> None:
        blank = np.zeros((120, 160, 3), dtype=np.uint8)
        value = FROPUInput.create(
            identity=synthetic_identity("blank"),
            original=blank,
            reconstruction=blank,
            union_corridor=self.fixture["union_corridor"],
        )
        evidence = evaluate_fropu(value)
        self.assertIsNone(evidence["score"])
        self.assertFalse(evidence["defined"])
        self.assertEqual(evidence["undefined_reason"], "no_original_proposals")
        validate_fropu_evidence(evidence, source_input=value)

    def test_ineligible_ccorf_is_explicitly_undefined(self) -> None:
        small = np.zeros((120, 160), dtype=bool)
        small[10:14, 10:14] = True
        value = CCORFInput.create(
            identity=synthetic_identity("ineligible"),
            original=self.fixture["original"],
            reconstruction=self.fixture["original"],
            critical_obstacle_mask=small,
            critical_boundary_mask=small,
            geometry_digest=self.fixture["geometry_digest"],
        )
        evidence = evaluate_ccorf(value)
        self.assertFalse(evidence["eligible"])
        self.assertIsNone(evidence["score"])
        self.assertEqual(evidence["exclusion_reason"], "projected_pixels_below_64")
        validate_ccorf_evidence(evidence, source_input=value)

    def test_recomputed_digest_cannot_hide_internal_tamper(self) -> None:
        evidence = evaluate_strcf(self.strcf_input("blur"))
        tampered = copy.deepcopy(evidence)
        tampered["score"] = 0.75
        base = {key: value for key, value in tampered.items() if key != "canonical_digest"}
        tampered["canonical_digest"] = digest(base)
        with self.assertRaisesRegex(ValueError, "inconsistent STRCF score"):
            validate_strcf_evidence(tampered)

    def test_recomputed_digest_cannot_hide_unknown_schema_field(self) -> None:
        evidence = evaluate_ccorf(self.ccorf_input("blur"))
        tampered = copy.deepcopy(evidence)
        tampered["allocator_selected"] = True
        base = {key: value for key, value in tampered.items() if key != "canonical_digest"}
        tampered["canonical_digest"] = digest(base)
        with self.assertRaisesRegex(ValueError, "unexpected CCORF evidence fields"):
            validate_ccorf_evidence(tampered)

    def test_source_recomputation_rejects_plausible_tamper(self) -> None:
        source = self.fropu_input("localization_shift")
        evidence = evaluate_fropu(source)
        tampered = copy.deepcopy(evidence)
        tampered["input_digests"]["reconstruction"] = "0" * 64
        base = {key: value for key, value in tampered.items() if key != "canonical_digest"}
        tampered["canonical_digest"] = digest(base)
        with self.assertRaisesRegex(ValueError, "does not match source"):
            validate_fropu_evidence(tampered, source_input=source)

    def test_canonical_persistence_reload_and_tamper_rejection(self) -> None:
        source = self.strcf_input("compression_q15")
        evidence = evaluate_strcf(source)
        validator = lambda value: validate_strcf_evidence(
            value,
            expected_identity=source.identity,
            source_input=source,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "strcf.json"
            persist_canonical_evidence(path, evidence, validator=validator)
            self.assertEqual(load_canonical_evidence(path, validator=validator), evidence)
            self.assertNotIn(b"\r\n", path.read_bytes())
            tampered = json.loads(path.read_text(encoding="utf-8"))
            tampered["score"] = 0.0
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_canonical_evidence(path, validator=validator)


class M8ControlledPerturbationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_report(build_report())
        cls.cases = {row["name"]: row for row in cls.report["controlled_perturbations"]}

    def test_blur_compression_and_contrast_loss_are_recorded(self) -> None:
        for name in ("blur", "compression_q15", "contrast_loss"):
            with self.subTest(name=name):
                self.assertLess(self.cases[name]["strcf"], self.cases["perfect"]["strcf"])
                self.assertLess(self.cases[name]["ccorf"], self.cases["perfect"]["ccorf"])

    def test_localization_shift_reduces_all_scores(self) -> None:
        shifted = self.cases["localization_shift"]
        for metric in ("fropu", "strcf", "ccorf"):
            self.assertLess(shifted[metric], self.cases["perfect"][metric])

    def test_irrelevant_background_has_negligible_ccorf_effect(self) -> None:
        self.assertGreater(self.cases["irrelevant_background"]["ccorf"], 0.99)
        self.assertGreater(
            self.cases["irrelevant_background"]["ccorf"],
            self.cases["occlusion"]["ccorf"],
        )

    def test_fropu_blur_and_internal_occlusion_blind_spot_is_not_hidden(self) -> None:
        self.assertEqual(self.cases["blur"]["fropu"], 1.0)
        self.assertEqual(self.cases["occlusion"]["fropu"], 1.0)

    def test_jpeg_monotonicity_and_saturation_diagnostics_are_persisted(self) -> None:
        diagnostics = self.report["jpeg_quality_ladder"]["diagnostics"]
        self.assertTrue(diagnostics["strcf"]["nondecreasing"])
        self.assertEqual(diagnostics["strcf"]["spearman_with_quality_order"], 1.0)
        self.assertGreater(diagnostics["fropu"]["endpoint_fraction"], 0.10)
        self.assertLess(diagnostics["fropu"]["range"], 0.15)
        self.assertEqual(self.report["unit_gate_notes"]["g3_monotonicity"], "DIAGNOSTIC_ONLY")

    def test_jpeg_ladder_is_exact_and_deterministic(self) -> None:
        self.assertEqual(
            self.report["jpeg_quality_ladder"]["qualities"],
            list(JPEG_QUALITY_LADDER),
        )
        self.assertTrue(self.report["deterministic_repeat"]["digests_match"])
        self.assertEqual(build_report(), build_report())

    def test_sequence_diagnostics_rejects_nonfinite_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            sequence_diagnostics([0.1, float("nan")])

    def test_unit_report_does_not_claim_scientific_qualification(self) -> None:
        self.assertEqual(
            self.report["scientific_qualification"],
            "NOT_EVALUATED_REQUIRES_810XXX_CALIBRATION",
        )
        self.assertEqual(self.report["candidate_selection"], "NOT_PERFORMED")


if __name__ == "__main__":
    unittest.main()
