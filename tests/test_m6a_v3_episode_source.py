import json
import tempfile
import unittest
from pathlib import Path

from scripts.m6a_manifest_authority import load_and_validate_m6a_manifest
from scripts.m6a_v2_episode_source import LOCK_PATH as V2_LOCK, MANIFEST_PATH as V2_MANIFEST
from scripts.m6a_v3_episode_source import (
    LOCK_PATH, MANIFEST_PATH, V2_LOCK_SHA256, V2_MANIFEST_SHA256,
    load_and_validate_m6a_v3_manifest, manifest_payload,
)
from scripts.run_m6a_one_identity import build_one_identity_runtime_config, load_v2_runtime_config
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package, load_prepared_launch_package_for_audit


class M6AV3EpisodeSourceTests(unittest.TestCase):
    def test_exact_balanced_new_formal_matrix_and_parent_binding(self):
        value = load_and_validate_m6a_v3_manifest()
        self.assertEqual(value, json.loads(json.dumps(manifest_payload())))
        self.assertEqual(len(value["records"]), 32)
        self.assertEqual([item["identity"]["seed"] for item in value["records"]], [630000 + scene * 100 + offset for scene in range(1, 9) for offset in range(4)])
        self.assertTrue(all(item["identity"]["split"] == "formal" for item in value["records"]))
        self.assertEqual(value["parent_manifest_sha256"], V2_MANIFEST_SHA256)
        self.assertEqual(value["parent_lock_sha256"], V2_LOCK_SHA256)

    def test_v2_and_v3_authorities_route_strictly(self):
        self.assertEqual(load_and_validate_m6a_manifest(V2_MANIFEST, V2_LOCK)[0], "v2")
        self.assertEqual(load_and_validate_m6a_manifest(MANIFEST_PATH, LOCK_PATH)[0], "v3")

    def test_v3_manifest_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"; lock = Path(directory) / "lock.json"
            value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")); value["records"][0]["identity"]["seed"] += 1
            manifest.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
            lock.write_bytes(LOCK_PATH.read_bytes())
            with self.assertRaises(ValueError):
                load_and_validate_m6a_v3_manifest(manifest, lock)

    def test_runtime_config_binds_exact_v3_record(self):
        config = build_one_identity_runtime_config(MANIFEST_PATH, LOCK_PATH, output_root="Z:/v3-uncreated", episode_id="m6a_v3_formal_s8_seed630803")
        self.assertEqual((config["protocol_version"], config["manifest_authority_version"]), ("m6a-byte-fair-v3", "v3"))
        self.assertEqual((config["split"], config["scene"], config["seed"]), ("formal", "S8", 630803))
        self.assertIs(load_v2_runtime_config(config), config)

    def test_runtime_authority_tamper_is_rejected(self):
        config = build_one_identity_runtime_config(MANIFEST_PATH, LOCK_PATH, output_root="Z:/v3-uncreated", episode_id="m6a_v3_formal_s1_seed630100")
        config["manifest_authority_version"] = "v2"
        from scripts.m6a_trusted_artifacts import digest
        config["config_sha256"] = digest({key: value for key, value in config.items() if key != "config_sha256"})
        with self.assertRaises(ValueError):
            load_v2_runtime_config(config)

    def test_prepared_package_binds_v3_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            path, package = build_prepared_launch_package(
                head="a" * 40, branch="main", attempt_id="m6v3-test-package",
                episode_id="m6a_v3_formal_s1_seed630100", package_root=Path(directory),
                manifest_path=MANIFEST_PATH, lock_path=LOCK_PATH,
            )
            self.assertEqual(load_prepared_launch_package_for_audit(path), package)
            self.assertEqual(package["manifest_authority_version"], "v3")
            runtime = json.loads(Path(package["launch_spec"]["runtime_config"]["path"]).read_text(encoding="utf-8"))
            self.assertEqual(runtime["manifest_authority_version"], "v3")
            self.assertIs(load_v2_runtime_config(runtime), runtime)
