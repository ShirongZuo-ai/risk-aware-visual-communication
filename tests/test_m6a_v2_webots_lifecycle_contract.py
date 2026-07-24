import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from navigation.trajectory_prediction import CommandSegment
from scripts.m6a_dual_roi import ScheduleEvidence
from scripts.m6a_v2_prepared_launch import (
    build_prepared_launch_package,
    load_prepared_launch_package_for_audit,
)
from scripts.m6a_v2_runtime_summary import FailureStage, write_runtime_failure_status, Lifecycle
from scripts.m6a_webots_adapter import (
    WebotsScheduleActuator,
    run_configured_m6a_controller,
)
from scripts.run_m6a_one_identity import RUNTIME_PATH_NAMES
from tests.test_m6a_v2_materialization_operator import isolated_execution_roots


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class _Motor:
    def __init__(self):
        self.positions = []
        self.velocities = []

    def setPosition(self, value):
        self.positions.append(value)

    def setVelocity(self, value):
        self.velocities.append(value)


class _Supervisor:
    def __init__(self):
        self.left = _Motor()
        self.right = _Motor()
        self.quit_codes = []

    def getDevice(self, name):
        return {"left wheel motor": self.left, "right wheel motor": self.right}.get(name)

    def simulationQuit(self, code):
        self.quit_codes.append(code)


class WebotsLifecycleContractTests(unittest.TestCase):
    def test_prepared_package_is_a_discoverable_webots_project(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = build_prepared_launch_package(
                head="layout-head",
                branch="main",
                attempt_id="layout-attempt",
                package_root=root / "prepared",
            )
            loaded = load_prepared_launch_package_for_audit(package_path)
            spec = loaded["launch_spec"]
            project = Path(package_path).parent
            world = project / "worlds" / "prepared.wbt"
            controller = project / "controllers" / "m6a_trusted_runtime" / "m6a_trusted_runtime.py"
            self.assertEqual(spec["schema_version"], "m6a-v2-production-launch-spec-v4")
            self.assertEqual(Path(spec["temporary_world"]["path"]), world.resolve())
            self.assertEqual(Path(spec["controller"]["path"]), controller.resolve())
            self.assertEqual(_sha(controller), spec["controller"]["source_sha256"])
            self.assertEqual(spec["argv"][-1], str(world.resolve()))
            self.assertEqual(spec["argv"][1:5], ["--batch", "--mode=fast", "--stdout", "--stderr"])
            self.assertEqual(set(spec["environment"]), {"M6A_RUNTIME_CONFIG", "PYTHONPATH"})
            self.assertEqual(spec["timeout_s"], 75)
            self.assertFalse(Path(package["prospective_attempt_root"]).exists())

    def test_controller_propagates_authoritative_paths_and_quits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt_root = root / "attempt"
            paths = {key: str((attempt_root / name).resolve()) for key, name in RUNTIME_PATH_NAMES.items()}
            config = {
                "output_root": str(attempt_root.resolve()),
                "snapshots": [{"snapshot_id": "0", "timestamp_s": 0.512}],
                "schedule": {
                    "schedule_id": "frozen",
                    "available_time_s": 0.0,
                    "segments": [{"start_s": 0.0, "end_s": 6.0, "left_rad_s": 2.0, "right_rad_s": 2.0}],
                },
                "attempt_paths": paths,
            }
            config_path = root / "runtime.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            supervisor = _Supervisor()
            captured = {}

            def lifecycle(path, **kwargs):
                captured.update(kwargs)
                self.assertIs(kwargs["supervisor_factory"](), supervisor)
                return 0, object()

            code = run_configured_m6a_controller(
                config_path,
                supervisor_factory=lambda: supervisor,
                lifecycle_runner=lifecycle,
            )
            self.assertEqual(code, 0)
            self.assertEqual(supervisor.quit_codes, [0])
            self.assertEqual(captured["summary_path"], paths["runtime_summary"])
            self.assertEqual(captured["status_path"], paths["runtime_status"])
            self.assertEqual(captured["diagnostic_path"], paths["runtime_diagnostic"])
            self.assertEqual(captured["runtime_manifest_path"], paths["runtime_manifest"])

    def test_controller_failure_still_requests_process_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            supervisor = _Supervisor()
            diagnostics = io.StringIO()
            with redirect_stderr(diagnostics):
                code = run_configured_m6a_controller(path, supervisor_factory=lambda: supervisor)
            self.assertEqual(code, 1)
            self.assertEqual(supervisor.quit_codes, [1])
            self.assertIn("KeyError", diagnostics.getvalue())

    def test_frozen_schedule_is_applied_and_stopped(self):
        supervisor = _Supervisor()
        schedule = ScheduleEvidence(
            "frozen",
            0.0,
            (
                CommandSegment(0.0, 3.0, 2.0, 2.0),
                CommandSegment(3.0, 6.0, 1.0, 2.0),
            ),
        )
        actuator = WebotsScheduleActuator(
            supervisor,
            schedule,
            left_motor="left wheel motor",
            right_motor="right wheel motor",
            required_until_s=5.408,
        )
        actuator.apply(0.0)
        actuator.apply(4.0)
        actuator.stop()
        self.assertEqual(supervisor.left.velocities, [0.0, 2.0, 1.0, 0.0])
        self.assertEqual(supervisor.right.velocities, [0.0, 2.0, 2.0, 0.0])

    def test_incomplete_or_gapped_schedule_is_rejected(self):
        supervisor = _Supervisor()
        cases = (
            (CommandSegment(0.0, 5.0, 2.0, 2.0),),
            (CommandSegment(0.0, 2.0, 2.0, 2.0), CommandSegment(3.0, 6.0, 2.0, 2.0)),
        )
        for segments in cases:
            with self.subTest(segments=segments), self.assertRaises(ValueError):
                WebotsScheduleActuator(
                    supervisor,
                    ScheduleEvidence("bad", 0.0, segments),
                    left_motor="left wheel motor",
                    right_motor="right wheel motor",
                    required_until_s=5.408,
                )

    def test_authoritative_failure_status_cannot_escape_attempt_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "attempt"
            root.mkdir()
            status = root / "episode_runtime_status.json"
            lifecycle = Lifecycle(); lifecycle.fail()
            write_runtime_failure_status(status, lifecycle, RuntimeError("failure"), failure_stage=FailureStage.CONFIG_LOADING, last_completed_state=None, authoritative_root=root)
            self.assertTrue(status.is_file())
            with self.assertRaises(ValueError):
                write_runtime_failure_status(
                    Path(directory) / "escaped.json",
                    lifecycle,
                    RuntimeError("failure"),
                    failure_stage=FailureStage.CONFIG_LOADING,
                    last_completed_state=None,
                    authoritative_root=root,
                )


if __name__ == "__main__":
    unittest.main()
