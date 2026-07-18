from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_m5e_dataset_smoke import (
    WORLD,
    _argument_parser,
    _wait_for_process,
    build_webots_command,
    controller_environment,
    gui_world_path,
    prepare_gui_world,
    validate_cli_arguments,
    validate_completed_episode,
)
from simulator.m5e_gui_acceptance import (
    GUI_ACCEPTANCE_ENVIRONMENT_VARIABLE,
    gui_acceptance_message,
    gui_acceptance_requested,
    pause_for_gui_acceptance,
)


class _FakeProcess:
    def __init__(self, poll_results: list[int | None]) -> None:
        self._poll_results = iter(poll_results)
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self) -> int | None:
        return next(self._poll_results)

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1


class _FakeSupervisor:
    def __init__(self) -> None:
        self.modes: list[int] = []

    def simulationSetMode(self, mode: int) -> None:
        self.modes.append(mode)


class M5EGuiAcceptanceTests(unittest.TestCase):
    def test_default_command_remains_batch_fast(self) -> None:
        command = build_webots_command(Path("webots.exe"), gui=False)
        self.assertEqual(command, ["webots.exe", "--batch", "--mode=fast", str(WORLD)])

    def test_gui_command_uses_realtime_without_batch_or_fast(self) -> None:
        review_world = gui_world_path("S2")
        command = build_webots_command(Path("webots.exe"), gui=True, world=review_world)
        self.assertEqual(command, ["webots.exe", "--mode=realtime", str(review_world)])
        self.assertNotIn("--batch", command)
        self.assertNotIn("--mode=fast", command)

    def test_gui_world_is_an_isolated_copy(self) -> None:
        review_world = prepare_gui_world("S2")
        try:
            self.assertNotEqual(review_world, WORLD)
            self.assertEqual(review_world.read_bytes(), WORLD.read_bytes())
            review_world.write_text("GUI runtime state", encoding="utf-8")
            self.assertNotEqual(review_world.read_bytes(), WORLD.read_bytes())
        finally:
            review_world.unlink(missing_ok=True)

    def test_gui_environment_passes_explicit_controller_marker(self) -> None:
        environment = controller_environment(Path("job.json"), gui=True, parent_environment={"KEEP": "yes"})
        self.assertEqual(environment[GUI_ACCEPTANCE_ENVIRONMENT_VARIABLE], "1")
        self.assertEqual(environment["M5E_CONFIG_PATH"], "job.json")
        self.assertTrue(gui_acceptance_requested(environment))

    def test_default_environment_removes_inherited_gui_marker(self) -> None:
        environment = controller_environment(
            Path("job.json"),
            gui=False,
            parent_environment={GUI_ACCEPTANCE_ENVIRONMENT_VARIABLE: "1"},
        )
        self.assertNotIn(GUI_ACCEPTANCE_ENVIRONMENT_VARIABLE, environment)
        self.assertFalse(gui_acceptance_requested(environment))

    def test_gui_requires_exactly_one_scenario(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            validate_cli_arguments(argparse.Namespace(gui=True, scenario=None, resume=False))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            validate_cli_arguments(argparse.Namespace(gui=True, scenario=["S1", "S2"], resume=False))

    def test_gui_rejects_resume_without_launching_a_window(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            validate_cli_arguments(argparse.Namespace(gui=True, scenario=["S2"], resume=True))

    def test_help_documents_gui_switch(self) -> None:
        help_text = _argument_parser().format_help()
        self.assertIn("--gui", help_text)
        self.assertIn("Launch Webots interactively", help_text)

    def test_gui_completion_pauses_and_emits_manual_checklist(self) -> None:
        supervisor = _FakeSupervisor()
        emitted: list[str] = []
        pause_for_gui_acceptance(supervisor, "S2", 4, 0, emit=emitted.append)
        self.assertEqual(supervisor.modes, [0])
        self.assertEqual(emitted, [gui_acceptance_message("S2", 4)])
        self.assertIn("M5E GUI ACCEPTANCE READY", emitted[0])
        self.assertIn("Close Webots manually", emitted[0])

    def test_gui_wait_has_no_automatic_timeout_or_termination(self) -> None:
        process = _FakeProcess([None, 0])
        _wait_for_process(process, Path("does-not-matter"), 0.0, gui=True, sleep=lambda _: None)
        self.assertEqual(process.terminate_calls, 0)
        self.assertEqual(process.kill_calls, 0)

    def test_default_wait_keeps_summary_timeout_behavior(self) -> None:
        process = _FakeProcess([None])
        monotonic_values = iter([0.0, 2.0])
        with self.assertRaises(TimeoutError):
            _wait_for_process(
                process,
                Path("does-not-exist"),
                1.0,
                gui=False,
                monotonic=lambda: next(monotonic_values),
                sleep=lambda _: None,
            )
        self.assertEqual(process.kill_calls, 1)

    def test_default_wait_terminates_after_summary_is_written(self) -> None:
        process = _FakeProcess([None])
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "episode_summary.json"
            summary.write_text("{}", encoding="utf-8")
            _wait_for_process(process, summary, 1.0, gui=False, sleep=lambda _: None)
        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.kill_calls, 0)

    def test_completed_episode_requires_four_snapshots(self) -> None:
        with patch("scripts.run_m5e_dataset_smoke.validate_episode", return_value={"completed_snapshot_count": 4}) as validator:
            self.assertEqual(validate_completed_episode(Path("summary.json"))["completed_snapshot_count"], 4)
            validator.assert_called_once_with(Path("summary.json"))
        with patch("scripts.run_m5e_dataset_smoke.validate_episode", return_value={"completed_snapshot_count": 3}):
            with self.assertRaisesRegex(ValueError, "four snapshots"):
                validate_completed_episode(Path("summary.json"))


if __name__ == "__main__":
    unittest.main()
