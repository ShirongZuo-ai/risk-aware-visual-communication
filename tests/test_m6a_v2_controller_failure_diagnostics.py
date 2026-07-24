import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_episode_source import load_and_validate_m6a_v2_manifest
from scripts.m6a_v2_runtime_summary import (
    FailureStage,
    Lifecycle,
    LifecycleState,
    SceneInitializationEvidence,
    load_runtime_failure_status,
    run_v2_controller_lifecycle,
)
from scripts.m6a_webots_adapter import run_configured_m6a_controller
from scripts.run_m6a_one_identity import (
    RUNTIME_PATH_NAMES,
    build_one_identity_runtime_config,
)


class _Supervisor:
    def __init__(self, *, shutdown_error=None):
        self.shutdown_error = shutdown_error
        self.quit_codes = []

    def simulationQuit(self, code):
        self.quit_codes.append(code)
        if self.shutdown_error is not None:
            raise self.shutdown_error


class ControllerFailureDiagnosticTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        attempt = root / "attempt"
        config = build_one_identity_runtime_config(output_root=attempt)
        attempt.mkdir()
        config["attempt_paths"] = {
            key: str((attempt / name).resolve()) for key, name in RUNTIME_PATH_NAMES.items()
        }
        config["config_sha256"] = digest(
            {key: value for key, value in config.items() if key != "config_sha256"}
        )
        config_path = root / "runtime.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        record = next(
            item
            for item in load_and_validate_m6a_v2_manifest()["records"]
            if item["source_record_sha256"] == config["source_record_sha256"]
        )
        scene = SceneInitializationEvidence(
            config["source_record_sha256"],
            config["seed"],
            record["scene_config_sha256"],
            record["scene_config_sha256"],
            "obstacle",
            "pose",
            True,
        )
        return temporary, attempt, config, config_path, scene

    def run_lifecycle(self, config, config_path, scene, *, summary_path=None, devices=None, episode=None):
        paths = config["attempt_paths"]
        stderr = io.StringIO()
        with patch(
            "scripts.m6a_v2_runtime_summary.initialize_v2_scene_before_motion",
            scene if callable(scene) else lambda *_: scene,
        ), redirect_stderr(stderr):
            code, lifecycle = run_v2_controller_lifecycle(
                config_path,
                supervisor_factory=object,
                devices_initializer=devices or (lambda *_: None),
                episode_runner=episode or (lambda *_: []),
                summary_path=summary_path or paths["runtime_summary"],
                status_path=paths["runtime_status"],
                diagnostic_path=paths["runtime_diagnostic"],
                runtime_manifest_path=paths["runtime_manifest"],
            )
        return code, lifecycle, stderr.getvalue()

    def test_scene_failure_is_canonical_actionable_and_redacted(self):
        temporary, attempt, config, path, _ = self.fixture(); self.addCleanup(temporary.cleanup)

        def fail_scene(*_):
            raise ValueError(f"scene read-back mismatch at {attempt}")

        code, _, stderr = self.run_lifecycle(config, path, fail_scene)
        self.assertEqual(code, 1)
        value = load_runtime_failure_status(config["attempt_paths"]["runtime_status"])
        self.assertEqual(value["failure_stage"], FailureStage.SCENE_INITIALIZATION.value)
        self.assertEqual(value["last_completed_state"], LifecycleState.CONFIG_VALIDATED.value)
        self.assertEqual(value["exception"]["type"], "ValueError")
        self.assertIn("<ATTEMPT_ROOT>", value["exception"]["message"])
        self.assertNotIn(str(attempt), json.dumps(value))
        self.assertIn("M6A_CONTROLLER_FAILURE", stderr)
        self.assertTrue(any(frame["function"] == "fail_scene" for frame in value["exception"]["frames"]))

    def test_device_failure_records_state_reader_setup_stage(self):
        temporary, _, config, path, scene = self.fixture(); self.addCleanup(temporary.cleanup)

        def fail_devices(*_):
            raise ValueError("robot pose device unavailable")

        code, _, _ = self.run_lifecycle(config, path, scene, devices=fail_devices)
        self.assertEqual(code, 1)
        value = load_runtime_failure_status(config["attempt_paths"]["runtime_status"])
        self.assertEqual(value["failure_stage"], FailureStage.STATE_READER_SETUP.value)
        self.assertEqual(value["exception"]["message"], "robot pose device unavailable")

    def test_actuator_schedule_setup_preserves_original_value_error(self):
        temporary, _, config, path, scene = self.fixture(); self.addCleanup(temporary.cleanup)
        supervisor = _Supervisor()
        stderr = io.StringIO()
        with (
            patch("scripts.m6a_v2_runtime_summary.initialize_v2_scene_before_motion", return_value=scene),
            patch("scripts.m6a_webots_adapter.WebotsCurrentStateReader", return_value=object()),
            patch("scripts.m6a_webots_adapter.WebotsScheduleActuator", side_effect=ValueError("frozen schedule motor unavailable")),
            redirect_stderr(stderr),
        ):
            code = run_configured_m6a_controller(path, supervisor_factory=lambda: supervisor)
        self.assertEqual(code, 1)
        self.assertEqual(supervisor.quit_codes, [1])
        value = load_runtime_failure_status(config["attempt_paths"]["runtime_status"])
        self.assertEqual(value["failure_stage"], FailureStage.ACTUATOR_SCHEDULE_SETUP.value)
        self.assertEqual(value["exception"]["type"], "ValueError")
        self.assertEqual(value["exception"]["message"], "frozen schedule motor unavailable")

    def test_output_path_mismatch_records_pre_scene_stage(self):
        temporary, attempt, config, path, scene = self.fixture(); self.addCleanup(temporary.cleanup)
        code, _, _ = self.run_lifecycle(
            config,
            path,
            scene,
            summary_path=str((attempt / "not-authoritative.json").resolve()),
        )
        self.assertEqual(code, 1)
        value = load_runtime_failure_status(config["attempt_paths"]["runtime_status"])
        self.assertEqual(value["failure_stage"], FailureStage.RUNTIME_OUTPUT_PATH_VALIDATION.value)
        self.assertIsNone(value["last_completed_state"])

    def test_episode_failure_records_running_stage_and_location(self):
        temporary, _, config, path, scene = self.fixture(); self.addCleanup(temporary.cleanup)

        def fail_episode(*_):
            raise ValueError("camera frame timestamp misalignment")

        code, _, _ = self.run_lifecycle(config, path, scene, episode=fail_episode)
        self.assertEqual(code, 1)
        value = load_runtime_failure_status(config["attempt_paths"]["runtime_status"])
        self.assertEqual(value["failure_stage"], FailureStage.EPISODE_EXECUTION.value)
        self.assertEqual(value["last_completed_state"], LifecycleState.EPISODE_RUNNING.value)
        self.assertTrue(any(frame["function"] == "fail_episode" for frame in value["exception"]["frames"]))

    def test_failure_status_tamper_is_rejected(self):
        temporary, _, config, path, _ = self.fixture(); self.addCleanup(temporary.cleanup)

        def fail_scene(*_):
            raise ValueError("scene failure")

        self.run_lifecycle(config, path, fail_scene)
        status = Path(config["attempt_paths"]["runtime_status"])
        value = json.loads(status.read_text(encoding="utf-8"))
        value["exception"]["message"] = "tampered"
        status.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_runtime_failure_status(status)

    def test_controlled_shutdown_failure_is_structured_and_returns_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "output_root": str((root / "attempt").resolve()),
                "snapshots": [{"snapshot_id": "0", "timestamp_s": 0.512}],
                "schedule": {"schedule_id": "frozen", "available_time_s": 0.0, "segments": [{"start_s": 0.0, "end_s": 6.0, "left_rad_s": 2.0, "right_rad_s": 2.0}]},
                "attempt_paths": {key: str((root / "attempt" / name).resolve()) for key, name in RUNTIME_PATH_NAMES.items()},
            }
            path = root / "runtime.json"; path.write_text(json.dumps(config), encoding="utf-8")
            lifecycle = Lifecycle()
            for state in (
                LifecycleState.CONFIG_VALIDATED, LifecycleState.SCENE_INITIALIZED,
                LifecycleState.DEVICES_READY, LifecycleState.EPISODE_RUNNING,
                LifecycleState.EPISODE_COMPLETED, LifecycleState.SUMMARY_COMMITTED,
            ):
                lifecycle.transition(state)
            supervisor = _Supervisor(shutdown_error=ValueError("simulation quit rejected"))
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = run_configured_m6a_controller(
                    path,
                    supervisor_factory=lambda: supervisor,
                    lifecycle_runner=lambda *_args, **_kwargs: (0, lifecycle),
                )
            self.assertEqual(code, 1)
            self.assertEqual(supervisor.quit_codes, [0])
            self.assertIn('"failure_stage":"CONTROLLED_SHUTDOWN"', stderr.getvalue())
            self.assertIn('"message":"simulation quit rejected"', stderr.getvalue())

    def test_successful_controlled_shutdown_remains_zero_and_silent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "output_root": str((root / "attempt").resolve()),
                "snapshots": [{"snapshot_id": "0", "timestamp_s": 0.512}],
                "schedule": {"schedule_id": "frozen", "available_time_s": 0.0, "segments": [{"start_s": 0.0, "end_s": 6.0, "left_rad_s": 2.0, "right_rad_s": 2.0}]},
                "attempt_paths": {key: str((root / "attempt" / name).resolve()) for key, name in RUNTIME_PATH_NAMES.items()},
            }
            path = root / "runtime.json"; path.write_text(json.dumps(config), encoding="utf-8")
            lifecycle = Lifecycle()
            for state in (
                LifecycleState.CONFIG_VALIDATED, LifecycleState.SCENE_INITIALIZED,
                LifecycleState.DEVICES_READY, LifecycleState.EPISODE_RUNNING,
                LifecycleState.EPISODE_COMPLETED, LifecycleState.SUMMARY_COMMITTED,
            ):
                lifecycle.transition(state)
            supervisor = _Supervisor(); stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = run_configured_m6a_controller(
                    path,
                    supervisor_factory=lambda: supervisor,
                    lifecycle_runner=lambda *_args, **_kwargs: (0, lifecycle),
                )
            self.assertEqual(code, 0)
            self.assertEqual(supervisor.quit_codes, [0])
            self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
