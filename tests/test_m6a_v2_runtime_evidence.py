import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from navigation.trajectory_prediction import CommandSegment
from scripts.m6a_dual_roi import CurrentState, ScheduleEvidence
from scripts.m6a_trusted_artifacts import M6AProjectionConfig
from scripts.m6a_v2_episode_source import load_and_validate_m6a_v2_manifest
from scripts.m6a_v2_runtime_evidence import (load_runtime_manifest, persist_runtime_diagnostic,
    persist_runtime_manifest)
from scripts.m6a_v2_runtime_summary import (Lifecycle, LifecycleState,
    SceneInitializationEvidence, build_episode_runtime_summary,
    persist_episode_runtime_summary, run_v2_controller_lifecycle)
from scripts.m6a_webots_adapter import (CameraFrame, M6ARuntimeConfig, StateSample,
    run_m6a_webots_episode)
from scripts.run_m6a_one_identity import build_one_identity_runtime_config


class _Facade:
    def __init__(self, times): self.times = iter(times)
    def step(self): return next(self.times, None)


class RuntimeManifestTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(); root = Path(temporary.name)
        config = build_one_identity_runtime_config(output_root=root / "episode_output")
        source = next(item for item in load_and_validate_m6a_v2_manifest()["records"] if item["source_record_sha256"] == config["source_record_sha256"])
        evidence = SceneInitializationEvidence(config["source_record_sha256"], config["seed"], source["scene_config_sha256"], source["scene_config_sha256"], "obstacle", "pose", True)
        now = [0.0]; facade = _Facade([item["timestamp_s"] for item in config["snapshots"]] + [config["schedule"]["segments"][-1]["end_s"]]); original = facade.step
        def step(): now[0] = original(); return now[0]
        facade.step = step
        legacy = M6ARuntimeConfig(config["v2_manifest_sha256"], config["scene"], config["episode_id"], config["seed"], tuple((item["snapshot_id"], item["timestamp_s"]) for item in config["snapshots"]), root, M6AProjectionConfig())
        schedule = ScheduleEvidence(config["schedule"]["schedule_id"], config["schedule"]["available_time_s"], tuple(CommandSegment(item["start_s"], item["end_s"], item["left_rad_s"], item["right_rad_s"]) for item in config["schedule"]["segments"]))
        runtime = run_m6a_webots_episode(legacy, facade, state_reader=lambda: StateSample(CurrentState(0, 0, 0, .1, 0), now[0]), frame_reader=lambda: CameraFrame(bytes(160 * 120 * 3), now[0]), predefined_schedule=schedule)
        records = [{"snapshot_id": item["snapshot_id"], "timestamp_s": item["timestamp_s"], "path": record["serialized_snapshot_path"], "snapshot_record": record, "methods": list(runtime.method_set), "actual_future_usage": 0, "combined_usage": 0, "raw_mask_usage": 0, "fallback": 0, "replacement": 0} for item, record in zip(config["snapshots"], runtime.snapshot_records)]
        lifecycle = Lifecycle()
        for state in (LifecycleState.CONFIG_VALIDATED, LifecycleState.SCENE_INITIALIZED, LifecycleState.DEVICES_READY, LifecycleState.EPISODE_RUNNING, LifecycleState.EPISODE_COMPLETED): lifecycle.transition(state)
        summary = build_episode_runtime_summary(config, evidence, records, lifecycle); summary["lifecycle_final_state"] = LifecycleState.SUMMARY_COMMITTED.value
        from scripts.m6a_trusted_artifacts import digest
        summary["summary_sha256"] = digest({key: value for key, value in summary.items() if key != "summary_sha256"})
        persist_episode_runtime_summary(summary, root / "summary.json", root / "status.json", config)
        identity = {"launch_id": "test-launch", "attempt_id": "test-attempt", "identity_id": config["episode_id"], "scene_id": config["scene"], "seed": config["seed"]}
        persist_runtime_diagnostic(root / "diagnostic.json", identity, "success", [])
        return temporary, root, config, identity

    def persist(self, root, config, identity):
        return persist_runtime_manifest(root / "runtime_artifacts.json", identity, root, runtime_config=config, summary_path=root / "summary.json", status_path=root / "status.json", diagnostic_path=root / "diagnostic.json")

    def test_actual_four_snapshot_reload_and_tamper_fail(self):
        temporary, root, config, identity = self.fixture(); self.addCleanup(temporary.cleanup)
        manifest = self.persist(root, config, identity)
        self.assertEqual(load_runtime_manifest(root / "runtime_artifacts.json", identity, root, config)["sha256"], manifest["sha256"])
        raw = Path(manifest["snapshot_validation"]["snapshots"][0]["raw_rgb"]["path"]); raw.write_bytes(b"x" + raw.read_bytes()[1:])
        with self.assertRaises(ValueError): load_runtime_manifest(root / "runtime_artifacts.json", identity, root, config)

    def test_metadata_serialization_and_snapshot_set_fail_closed(self):
        temporary, root, config, identity = self.fixture(); self.addCleanup(temporary.cleanup)
        self.persist(root, config, identity)
        meta = root / "raw" / "0.json"; data = json.loads(meta.read_text()); data["scene"] = "wrong"; meta.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError): load_runtime_manifest(root / "runtime_artifacts.json", identity, root, config)
        temporary2, root2, config2, identity2 = self.fixture(); self.addCleanup(temporary2.cleanup)
        self.persist(root2, config2, identity2)
        (root2 / "snapshots" / "0" / "state_only_risk_roi" / "trajectory.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError): load_runtime_manifest(root2 / "runtime_artifacts.json", identity2, root2, config2)

    def test_success_lifecycle_persists_then_reloads_manifest(self):
        temporary, root, config, identity = self.fixture(); self.addCleanup(temporary.cleanup)
        summary = json.loads((root / "summary.json").read_text())
        records = [{"snapshot_id": item["snapshot_id"], "timestamp_s": config["snapshots"][item["snapshot_index"]]["timestamp_s"], "path": item["serialized_snapshot_path"], "snapshot_record": item, "methods": ["state_only_risk_roi", "command_conditioned_risk_roi"], "actual_future_usage": 0, "combined_usage": 0, "raw_mask_usage": 0, "fallback": 0, "replacement": 0} for item in summary["snapshots"]]
        for name in ("summary.json", "status.json", "diagnostic.json"):
            (root / name).unlink()
        config_path = root / "runtime.json"; config_path.write_text(json.dumps(config), encoding="utf-8")
        source = next(item for item in load_and_validate_m6a_v2_manifest()["records"] if item["source_record_sha256"] == config["source_record_sha256"])
        scene = SceneInitializationEvidence(config["source_record_sha256"], config["seed"], source["scene_config_sha256"], source["scene_config_sha256"], "obstacle", "pose", True)
        with patch("scripts.m6a_v2_runtime_summary.initialize_v2_scene_before_motion", lambda *_: scene):
            code, lifecycle = run_v2_controller_lifecycle(config_path, supervisor_factory=object, devices_initializer=lambda *_: None, episode_runner=lambda *_: records, summary_path=root / "summary.json", status_path=root / "status.json", diagnostic_path=root / "diagnostic.json", runtime_manifest_path=root / "runtime_artifacts.json", manifest_identity=identity)
        self.assertEqual(code, 0); self.assertEqual(lifecycle.state, LifecycleState.SUMMARY_COMMITTED)
        self.assertTrue(load_runtime_manifest(root / "runtime_artifacts.json", identity, root, config)["snapshot_validation"]["pass"])

    def test_summary_status_and_diagnostic_tamper_fail(self):
        for name, replacement in (("summary.json", b"{}\n"), ("status.json", b"{}\n"), ("diagnostic.json", b"{}\n")):
            temporary, root, config, identity = self.fixture(); self.addCleanup(temporary.cleanup)
            self.persist(root, config, identity); (root / name).write_bytes(replacement)
            with self.assertRaises(ValueError, msg=name): load_runtime_manifest(root / "runtime_artifacts.json", identity, root, config)

    def test_missing_serialization_and_manifest_tamper_fail(self):
        temporary, root, config, identity = self.fixture(); self.addCleanup(temporary.cleanup)
        self.persist(root, config, identity)
        (root / "snapshots" / "1" / "command_conditioned_risk_roi" / "mask.json").unlink()
        with self.assertRaises(ValueError): load_runtime_manifest(root / "runtime_artifacts.json", identity, root, config)
        temporary2, root2, config2, identity2 = self.fixture(); self.addCleanup(temporary2.cleanup)
        self.persist(root2, config2, identity2); manifest_path = root2 / "runtime_artifacts.json"; manifest_path.write_bytes(b"{}\n")
        with self.assertRaises(ValueError): load_runtime_manifest(manifest_path, identity2, root2, config2)
