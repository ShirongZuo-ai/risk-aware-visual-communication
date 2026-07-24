import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_execution_safety import attempt_path_plan
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_research_pilot import (
    RESEARCH_BRIDGE_ALLOWED_PATHS,
    RESEARCH_CLAIM,
    RESEARCH_CONTEXT,
    build_research_head_binding,
    run_research_pilot,
)
from tests.test_m6a_v2_materialization_operator import canonical_write, isolated_execution_roots


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rewrite_for_child(package_path, package, code, *, timeout_s=5.0):
    executable = Path(sys.executable).resolve()
    spec = package["launch_spec"]
    spec["webots"] = {
        "path": str(executable),
        "source": "temporary-harmless-child",
        "version": sys.version.split()[0],
        "executable_sha256": _sha(executable),
    }
    spec["argv"] = [str(executable), "-c", code]
    spec["working_directory"] = str(Path(package_path).parent)
    spec["timeout_s"] = timeout_s
    spec["graceful_termination_s"] = 0.1
    spec["launch_spec_sha256"] = digest(
        {key: value for key, value in spec.items() if key != "launch_spec_sha256"}
    )
    package["launch_spec"] = spec
    package["launch_spec_sha256"] = spec["launch_spec_sha256"]
    package["executable"] = spec["webots"]
    package["argv_sha256"] = digest(spec["argv"])
    package["package_sha256"] = digest(
        {key: value for key, value in package.items() if key != "package_sha256"}
    )
    canonical_write(package_path, package)
    return package


def _binding(head="research-head"):
    value = {
        "schema_version": "m6a-v2-research-head-binding-v1",
        "package_head": head,
        "execution_head": head,
        "branch": "main",
        "binding_mode": "exact",
        "changed_paths": [],
        "allowed_paths": sorted(RESEARCH_BRIDGE_ALLOWED_PATHS),
    }
    value["binding_digest"] = digest(value)
    return value


def _completion(spec, process, *, owned_output_root):
    return {
        "integration_valid": True,
        "final_evidence": {
            "runtime_sha256": "runtime",
            "snapshot_validation_sha256": "snapshots",
            "b5_sha256": "aggregate-validation",
            "aggregate_sha256": "aggregate",
            "joint_validator_sha256": "joint",
            "manifest_sha256": "manifest",
            "lock_sha256": "lock",
        },
    }


class CountingRunner:
    def __init__(self, *, raises=False):
        self.calls = 0
        self.raises = raises

    def run(self, **kwargs):
        self.calls += 1
        if self.raises:
            raise RuntimeError("simulated start uncertainty")
        raise AssertionError("runner should not have been invoked")


class ResearchPilotTests(unittest.TestCase):
    def prepare(self, root, attempt, code="print('research-child-ok')", timeout_s=5.0):
        package_path, package = build_prepared_launch_package(
            head="research-head", branch="main", attempt_id=attempt, package_root=root / "prepared"
        )
        package = _rewrite_for_child(package_path, package, code, timeout_s=timeout_s)
        return package_path, package

    def run_pilot(self, package_path, **kwargs):
        with patch("scripts.m6a_v2_research_pilot.build_research_head_binding", return_value=_binding()):
            return run_research_pilot(
                package_path,
                confirm_attempt=Path(package_path).parent.name,
                require_authoritative_path=False,
                **kwargs,
            )

    def test_harmless_child_success_is_finalized_without_consumption(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = self.prepare(root, "research-success")
            result = self.run_pilot(package_path, completion_runner=_completion)
            self.assertEqual(result["state"], "finalized")
            self.assertTrue(result["runner_invoked"])
            self.assertEqual(result["process"]["return_code"], 0)
            self.assertFalse(result["process"]["timed_out"])
            self.assertEqual(result["process"]["termination_state"], "exited")
            self.assertEqual(result["terminal"]["state"], "completed")
            self.assertIn("research-child-ok", Path(result["process"]["stdout"]["path"]).read_text())
            paths = attempt_path_plan(
                package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
            )["artifacts"]
            self.assertFalse(Path(paths["consumption_record"]).exists())
            self.assertEqual(result["final_marker"]["execution_mode"], "research")
            self.assertNotIn("consumption_sha256", result["final_marker"])

    def test_nonzero_exit_is_terminal_and_never_retried(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, _ = self.prepare(root, "research-nonzero", "import sys; sys.exit(7)")
            first = self.run_pilot(package_path, completion_runner=_completion)
            forbidden = CountingRunner()
            second = self.run_pilot(package_path, process_runner=forbidden, completion_runner=_completion)
            self.assertEqual(first["state"], "process_failed")
            self.assertEqual(first["process"]["return_code"], 7)
            self.assertTrue(second["idempotent"])
            self.assertEqual(forbidden.calls, 0)

    def test_timeout_is_preserved_as_explicit_failure(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, _ = self.prepare(root, "research-timeout", "import time; time.sleep(2)", timeout_s=0.05)
            result = self.run_pilot(package_path, completion_runner=_completion)
            self.assertEqual(result["state"], "process_failed")
            self.assertTrue(result["process"]["timed_out"])
            self.assertIn(result["process"]["termination_state"], {"terminated_after_timeout", "killed_after_timeout"})

    def test_arbitrary_existing_root_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = self.prepare(root, "research-existing")
            attempt = Path(package["prospective_attempt_root"])
            attempt.mkdir(parents=True)
            sentinel = attempt / "user.txt"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not a research-owned attempt"):
                self.run_pilot(package_path, completion_runner=_completion)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_claim_before_start_error_forbids_retry(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = self.prepare(root, "research-uncertain")
            uncertain = CountingRunner(raises=True)
            with self.assertRaisesRegex(RuntimeError, "simulated start uncertainty"):
                self.run_pilot(package_path, process_runner=uncertain, completion_runner=_completion)
            self.assertTrue((Path(package["prospective_attempt_root"]) / RESEARCH_CLAIM).is_file())
            forbidden = CountingRunner()
            with self.assertRaisesRegex(RuntimeError, "retry forbidden"):
                self.run_pilot(package_path, process_runner=forbidden, completion_runner=_completion)
            self.assertEqual(uncertain.calls, 1)
            self.assertEqual(forbidden.calls, 0)

    def test_recovery_after_process_evidence_does_not_relaunch(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, _ = self.prepare(root, "research-recover")
            calls = {"completion": 0}

            def interrupted(*args, **kwargs):
                calls["completion"] += 1
                raise RuntimeError("completion interrupted")

            with self.assertRaisesRegex(RuntimeError, "completion interrupted"):
                self.run_pilot(package_path, completion_runner=interrupted)
            forbidden = CountingRunner()
            result = self.run_pilot(package_path, process_runner=forbidden, completion_runner=_completion)
            self.assertEqual(result["state"], "finalized")
            self.assertFalse(result["runner_invoked"])
            self.assertEqual(forbidden.calls, 0)
            self.assertEqual(calls["completion"], 1)

    def test_context_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = self.prepare(root, "research-context-tamper")
            uncertain = CountingRunner(raises=True)
            with self.assertRaises(RuntimeError):
                self.run_pilot(package_path, process_runner=uncertain)
            path = Path(package["prospective_attempt_root"]) / RESEARCH_CONTEXT
            value = json.loads(path.read_text(encoding="utf-8"))
            value["identity_id"] = "wrong"
            canonical_write(path, value)
            with self.assertRaises(ValueError):
                self.run_pilot(package_path)

    def test_claim_tamper_is_rejected_without_relaunch(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = self.prepare(root, "research-claim-tamper")
            with self.assertRaises(RuntimeError):
                self.run_pilot(package_path, process_runner=CountingRunner(raises=True))
            path = Path(package["prospective_attempt_root"]) / RESEARCH_CLAIM
            value = json.loads(path.read_text(encoding="utf-8"))
            value["package_sha256"] = "0" * 64
            canonical_write(path, value)
            forbidden = CountingRunner()
            with self.assertRaises(ValueError):
                self.run_pilot(package_path, process_runner=forbidden)
            self.assertEqual(forbidden.calls, 0)

    def test_process_evidence_without_claim_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = self.prepare(root, "research-partial")
            with self.assertRaises(RuntimeError):
                self.run_pilot(package_path, process_runner=CountingRunner(raises=True))
            attempt = Path(package["prospective_attempt_root"])
            (attempt / RESEARCH_CLAIM).unlink()
            (attempt / "host_process_result.json").write_text("partial", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "without an at-most-once"):
                self.run_pilot(package_path)

    def test_resealed_conflicting_final_marker_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = self.prepare(root, "research-final-tamper")
            result = self.run_pilot(package_path, completion_runner=_completion)
            path = Path(package["prospective_attempt_root"]) / "m6a_v2_final_success.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["research_launch_claim_sha256"] = "0" * 64
            value["sha256"] = digest({key: item for key, item in value.items() if key != "sha256"})
            canonical_write(path, value)
            with self.assertRaisesRegex(ValueError, "final marker binding"):
                self.run_pilot(package_path, completion_runner=_completion)
            self.assertEqual(result["state"], "finalized")

    def test_attempt_confirmation_mismatch_rejected_before_root(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = self.prepare(root, "research-confirm")
            with patch("scripts.m6a_v2_research_pilot.build_research_head_binding", return_value=_binding()):
                with self.assertRaisesRegex(ValueError, "confirmation mismatch"):
                    run_research_pilot(package_path, confirm_attempt="wrong", require_authoritative_path=False)
            self.assertFalse(Path(package["prospective_attempt_root"]).exists())


class ResearchHeadBindingTests(unittest.TestCase):
    def git(self, root, *args):
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, shell=False)

    def repository(self, root):
        self.git(root, "init", "-b", "main")
        self.git(root, "config", "user.email", "research@example.invalid")
        self.git(root, "config", "user.name", "Research Test")
        path = root / "scripts" / "m6a_v2_research_pilot.py"
        path.parent.mkdir()
        path.write_text("one\n", encoding="utf-8")
        self.git(root, "add", ".")
        self.git(root, "commit", "-m", "base")
        return self.git(root, "rev-parse", "HEAD").stdout.strip()

    def test_exact_head_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            head = self.repository(root)
            binding = build_research_head_binding(head, "main", repository_root=root)
            self.assertEqual(binding["binding_mode"], "exact")

    def test_single_allowed_commit_bridge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            head = self.repository(root)
            path = root / "scripts" / "m6a_v2_research_pilot.py"
            path.write_text("two\n", encoding="utf-8")
            self.git(root, "add", ".")
            self.git(root, "commit", "-m", "runner")
            binding = build_research_head_binding(head, "main", repository_root=root)
            self.assertEqual(binding["binding_mode"], "single_research_runner_commit")

    def test_non_research_or_multiple_commit_bridge_is_rejected(self):
        for kind in ("unexpected", "multiple"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                head = self.repository(root)
                path = root / ("scientific.json" if kind == "unexpected" else "scripts/m6a_v2_research_pilot.py")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("two\n", encoding="utf-8")
                self.git(root, "add", ".")
                self.git(root, "commit", "-m", "change")
                if kind == "multiple":
                    path.write_text("three\n", encoding="utf-8")
                    self.git(root, "add", ".")
                    self.git(root, "commit", "-m", "second")
                with self.assertRaises(ValueError):
                    build_research_head_binding(head, "main", repository_root=root)

    def test_dirty_tracked_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            head = self.repository(root)
            (root / "scripts" / "m6a_v2_research_pilot.py").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be clean"):
                build_research_head_binding(head, "main", repository_root=root)


if __name__ == "__main__":
    unittest.main()
