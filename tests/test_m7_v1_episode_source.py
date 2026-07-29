import json
import tempfile
import unittest
from pathlib import Path

from scripts.m6a_manifest_authority import load_and_validate_m6a_manifest
from scripts.m6a_trusted_artifacts import digest
from scripts.m7_v1_episode_source import (
    LOCK_PATH, MANIFEST_PATH, PREREGISTRATION_PATH, SCENE_IDS,
    V2_LOCK_SHA256, V2_MANIFEST_SHA256, V3_LOCK_SHA256, V3_MANIFEST_SHA256,
    _bytes, identities, load_and_validate_m7_v1_manifest,
    load_evaluator_only_geometry, manifest_payload, persist_evaluator_only_geometry,
)
from scripts.m7_v1_corpus import audit_historical_disjointness, load_preregistration
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package, load_prepared_launch_package_for_audit
from scripts.run_m6a_one_identity import build_one_identity_runtime_config, load_v2_runtime_config
from simulator.m7_scenarios import generate_m7_scenario, geometric_event_evidence


class M7V1EpisodeSourceTests(unittest.TestCase):
    def test_exact_balanced_development_matrix(self):
        value = load_and_validate_m7_v1_manifest()
        self.assertEqual(value, json.loads(_bytes(manifest_payload())))
        self.assertEqual(len(value["records"]), 16)
        self.assertEqual(value["scene_counts"], {scene: 2 for scene in SCENE_IDS})
        self.assertEqual(
            [item["identity"]["seed"] for item in value["records"]],
            [710000 + scene * 100 + offset for scene in range(1, 9) for offset in range(2)],
        )
        self.assertTrue(all(item["identity"]["split"] == "development" for item in value["records"]))
        self.assertEqual(value["parent_authorities"], {
            "m6_v2_manifest_sha256": V2_MANIFEST_SHA256, "m6_v2_lock_sha256": V2_LOCK_SHA256,
            "m6_v3_manifest_sha256": V3_MANIFEST_SHA256, "m6_v3_lock_sha256": V3_LOCK_SHA256,
        })

    def test_critical_and_generalization_geometry_is_predeclared(self):
        for item in identities():
            evidence = geometric_event_evidence(generate_m7_scenario(item["scenario_id"], item["seed"]))
            self.assertTrue(evidence["passed"])
            self.assertFalse(evidence["uses_rgb_or_codec_outcomes"])
            declared = [row for row in evidence["observations"] if row["obstacle_id"] in evidence["declared_event_obstacle_ids"] and row["snapshot_id"] in evidence["declared_event_snapshot_ids"]]
            if item["scenario_id"].startswith("M7C"):
                self.assertTrue(declared)
                self.assertTrue(all(row["trajectory_critical"] and row["clipped_projected_pixels"] >= 64 for row in declared))
            else:
                self.assertFalse(any(row["trajectory_critical"] for row in evidence["observations"]))

    def test_information_boundary_excludes_evaluator_fields_from_runtime(self):
        config = build_one_identity_runtime_config(
            MANIFEST_PATH, LOCK_PATH, output_root="Z:/m7-uncreated",
            episode_id="m7_v1_development_m7c1_seed710100",
        )
        self.assertEqual((config["protocol_version"], config["manifest_authority_version"], config["split"]), ("m7-development-corpus-v1", "m7v1", "development"))
        self.assertIs(load_v2_runtime_config(config), config)
        forbidden = {"evaluator_only_obstacle_geometry", "critical_event_labels", "tcobr_annotations", "future_ground_truth"}
        self.assertFalse(forbidden & set(config))
        tampered = dict(config); tampered["evaluator_only_obstacle_geometry"] = {}
        tampered["config_sha256"] = digest({k:v for k,v in tampered.items() if k != "config_sha256"})
        with self.assertRaises(ValueError): load_v2_runtime_config(tampered)

    def test_manifest_router_and_split_tamper(self):
        self.assertEqual(load_and_validate_m6a_manifest(MANIFEST_PATH, LOCK_PATH)[0], "m7v1")
        config = build_one_identity_runtime_config(MANIFEST_PATH, LOCK_PATH, output_root="Z:/m7-uncreated-2", episode_id="m7_v1_development_m7g2_seed710801")
        config["split"] = "formal"; config["config_sha256"] = digest({k:v for k,v in config.items() if k != "config_sha256"})
        with self.assertRaises(ValueError): load_v2_runtime_config(config)

    def test_manifest_and_lock_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"; lock = Path(directory) / "lock.json"
            value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")); value["records"][0]["identity"]["seed"] += 1
            manifest.write_bytes(_bytes(value)); lock.write_bytes(LOCK_PATH.read_bytes())
            with self.assertRaises(ValueError): load_and_validate_m7_v1_manifest(manifest, lock)
            manifest.write_bytes(MANIFEST_PATH.read_bytes()); changed = json.loads(LOCK_PATH.read_text(encoding="utf-8")); changed["total_records"] = 15; lock.write_bytes(_bytes(changed))
            with self.assertRaises(ValueError): load_and_validate_m7_v1_manifest(manifest, lock)

    def test_evaluator_geometry_is_post_runtime_canonical_and_tamper_checked(self):
        config = build_one_identity_runtime_config(MANIFEST_PATH, LOCK_PATH, output_root="Z:/m7-uncreated-3", episode_id="m7_v1_development_m7c2_seed710200")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = persist_evaluator_only_geometry(config, root)
            self.assertFalse(value["allocator_access_allowed"]); self.assertTrue(value["persisted_after_runtime"])
            self.assertEqual(load_evaluator_only_geometry(root / "evaluator_only_geometry.json", config, root), value)
            changed = json.loads((root / "evaluator_only_geometry.json").read_text(encoding="utf-8")); changed["allocator_access_allowed"] = True; changed["canonical_digest"] = digest({k:v for k,v in changed.items() if k != "canonical_digest"}); (root / "evaluator_only_geometry.json").write_bytes(_bytes(changed))
            with self.assertRaises(ValueError): load_evaluator_only_geometry(root / "evaluator_only_geometry.json", config, root)

    def test_preregistration_and_repository_disjointness(self):
        value = load_preregistration(PREREGISTRATION_PATH)
        self.assertEqual(len(value["matrix"]), 16)
        self.assertEqual(value["expected"], {"episodes":16,"scenes":8,"snapshots":64,"codec_cases":512})
        audit = audit_historical_disjointness(); self.assertTrue(audit["passed"])
        self.assertEqual((audit["identity_overlap_count"], audit["seed_overlap_count"]), (0, 0))

    def test_prepared_package_binds_exact_m7_authority_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            path, package = build_prepared_launch_package(
                head="a" * 40, branch="main", attempt_id="m7v1-test-package",
                episode_id="m7_v1_development_m7c1_seed710100", package_root=Path(directory),
                manifest_path=MANIFEST_PATH, lock_path=LOCK_PATH,
            )
            self.assertEqual(load_prepared_launch_package_for_audit(path), package)
            self.assertEqual(package["manifest_authority_version"], "m7v1")
            self.assertEqual((package["scene_id"],package["seed"]),("M7C1",710100))
            runtime=json.loads(Path(package["launch_spec"]["runtime_config"]["path"]).read_text(encoding="utf-8"))
            self.assertEqual(runtime["split"],"development");self.assertIs(load_v2_runtime_config(runtime),runtime)
