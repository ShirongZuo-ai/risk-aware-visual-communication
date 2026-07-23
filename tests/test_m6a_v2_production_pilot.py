import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_authorization_operator import materialize_current_verified_authorization
from scripts.m6a_v2_execution_safety import (
    FINAL,
    OWNER,
    OWNED_CONTEXT,
    acquire_ownership,
    attempt_path_plan,
    launch_owned_attempt,
    load_owned_attempt_context,
    retire_pre_spawn_attempt,
)
from scripts.m6a_v2_host_wrapper import ProductionOwnedProcessRunner
from scripts.m6a_v2_pilot_operator import run_production_pilot
from scripts.m6a_v2_prepared_launch import (
    build_prepared_launch_package,
    load_owned_prepared_launch_package,
    load_prepared_launch_package,
)
from tests.test_m6a_v2_materialization_operator import (
    MaterializationOperatorTests,
    canonical_write,
    isolated_execution_roots,
)


REAL_ATTEMPT = (
    PROJECT_ROOT
    / "data"
    / "m6a"
    / "pilot"
    / "m6ac31cb4657ae813d7e35387acc28583fd"
    / "m6a-prod-pilot-001"
)
REAL_ATTEMPT_SNAPSHOT = (
    {str(path.relative_to(REAL_ATTEMPT)): path.read_bytes() for path in REAL_ATTEMPT.rglob("*") if path.is_file()}
    if REAL_ATTEMPT.is_dir()
    else {}
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _prepare_verified(root, *, attempt_id):
    helper = MaterializationOperatorTests(methodName="test_materialize_only_creates_reloaded_ownership_and_nothing_later")
    return helper.prepare_verified(root, attempt_id=attempt_id)


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


class FakeRunner:
    def __init__(self, *, code=0):
        self.calls = 0
        self.code = code

    def run(self, *, root, path_plan, owned_attempt_context):
        self.calls += 1
        Path(path_plan["stdout"]).write_bytes(b"safe fake stdout\n")
        Path(path_plan["stderr"]).write_bytes(b"safe fake stderr\n")
        return {
            "launch_performed": True,
            "started_at_utc": "2026-07-23T00:00:00+00:00",
            "ended_at_utc": "2026-07-23T00:00:01+00:00",
            "return_code": self.code,
            "timed_out": False,
            "termination_state": "exited",
            "stdout_path": path_plan["stdout"],
            "stderr_path": path_plan["stderr"],
            "process_identity": "temporary-fake-runner",
        }


def _materialize(root, *, attempt_id):
    trust, package_path, package, _, _, _ = _prepare_verified(root, attempt_id=attempt_id)
    result = materialize_current_verified_authorization(
        package_path,
        trust,
        repository_root=root,
        current_head=package["head"],
    )
    return package_path, package, result


def _rewrite_for_child(package_path, package, *, code, timeout_s=5, grace_s=1):
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
    spec["graceful_termination_s"] = grace_s
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


class ProductionPilotTests(unittest.TestCase):
    def test_phase_specific_loaders_accept_only_pre_or_owned_state(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = build_prepared_launch_package(
                head="phase-head", branch="main", attempt_id="phase1", package_root=root / "prepared"
            )
            self.assertEqual(load_prepared_launch_package(package_path)["package_sha256"], package["package_sha256"])
            attempt = Path(package["prospective_attempt_root"])
            attempt.mkdir(parents=True)
            with self.assertRaises(ValueError):
                load_prepared_launch_package(package_path)
            with self.assertRaises(ValueError):
                load_owned_prepared_launch_package(package_path, {}, expected_head="phase-head")

    def test_durable_owned_context_persists_reloads_and_rejects_direct_dict(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            _, package, result = _materialize(root, attempt_id="durable1")
            artifact = Path(result["owned_context_path"])
            owned = load_owned_attempt_context(artifact, expected_head=package["head"])
            self.assertEqual(owned["package_digest"], package["package_sha256"])
            self.assertEqual(owned["ownership_digest"], result["ownership_digest"])
            with self.assertRaises(TypeError):
                load_owned_attempt_context(owned.data, expected_head=package["head"])

    def test_durable_context_tamper_and_head_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            _, package, result = _materialize(root, attempt_id="tamper1")
            artifact = Path(result["owned_context_path"])
            value = json.loads(artifact.read_text(encoding="utf-8"))
            value["identity_id"] = "wrong"
            value["canonical_digest"] = digest(
                {key: item for key, item in value.items() if key != "canonical_digest"}
            )
            canonical_write(artifact, value)
            with self.assertRaises(ValueError):
                load_owned_attempt_context(artifact, expected_head=package["head"])
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            _, package, result = _materialize(root, attempt_id="head-mismatch")
            with self.assertRaises(ValueError):
                load_owned_attempt_context(result["owned_context_path"], expected_head="different-head")
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            _, package, result = _materialize(root, attempt_id="wrong-root")
            artifact = Path(result["owned_context_path"])
            value = json.loads(artifact.read_text(encoding="utf-8"))
            value["attempt_root"] = str(root / "pilot" / "escaped")
            value["canonical_digest"] = digest(
                {key: item for key, item in value.items() if key != "canonical_digest"}
            )
            canonical_write(artifact, value)
            with self.assertRaises(ValueError):
                load_owned_attempt_context(artifact, expected_head=package["head"])
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            _, package, result = _materialize(root, attempt_id="wrong-package")
            wrong_path, _ = build_prepared_launch_package(
                head=package["head"], branch="main", attempt_id="other-package", package_root=root / "other-prepared"
            )
            artifact = Path(result["owned_context_path"])
            value = json.loads(artifact.read_text(encoding="utf-8"))
            value["package_path"] = str(wrong_path.resolve())
            value["canonical_digest"] = digest(
                {key: item for key, item in value.items() if key != "canonical_digest"}
            )
            canonical_write(artifact, value)
            with self.assertRaises(ValueError):
                load_owned_attempt_context(artifact, expected_head=package["head"])

    def test_durable_context_rejects_wrong_ownership_and_receipt(self):
        for target in ("ownership", "receipt"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
                root = Path(directory)
                _, package, result = _materialize(root, attempt_id=f"wrong-{target}")
                context = json.loads(Path(result["owned_context_path"]).read_text(encoding="utf-8"))
                path = Path(context["ownership_path"] if target == "ownership" else context["receipt_path"])
                value = json.loads(path.read_text(encoding="utf-8"))
                value["nonce" if target == "receipt" else "identity_id"] = "wrong"
                digest_field = "canonical_receipt_digest" if target == "receipt" else "sha256"
                value[digest_field] = digest(
                    {key: item for key, item in value.items() if key != digest_field}
                )
                canonical_write(path, value)
                with self.assertRaises(ValueError):
                    load_owned_attempt_context(result["owned_context_path"], expected_head=package["head"])

    def test_materialization_rejects_package_head_mismatch_before_root(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            trust, package_path, package, _, _, _ = _prepare_verified(root, attempt_id="wrong-head-materialize")
            with self.assertRaises(ValueError):
                materialize_current_verified_authorization(
                    package_path, trust, repository_root=root, current_head="not-the-package-head"
                )
            self.assertFalse(Path(package["prospective_attempt_root"]).exists())

    def test_production_runner_harmless_child_success_nonzero_and_timeout(self):
        cases = (
            ("success", "print('child-ok')", 0, 5, False, "exited"),
            ("nonzero", "import sys; print('child-fail'); sys.exit(7)", 7, 5, False, "exited"),
            ("timeout", "import time; print('child-wait'); time.sleep(5)", None, 0.1, True, None),
        )
        for label, code, expected_code, timeout_s, expected_timeout, expected_state in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
                root = Path(directory)
                package_path, package = build_prepared_launch_package(
                    head=f"child-{label}", branch="main", attempt_id=f"child-{label}", package_root=root / "prepared"
                )
                package = _rewrite_for_child(
                    package_path, package, code=code, timeout_s=timeout_s, grace_s=0.1
                )
                attempt = Path(package["prospective_attempt_root"])
                attempt.mkdir(parents=True)
                runner = ProductionOwnedProcessRunner(package_path, repository_head=package["head"])
                context = {
                    "launch_id": package["launch_id"],
                    "attempt_id": package["attempt_id"],
                    "identity_id": package["identity_id"],
                }
                result = runner.run(
                    root=attempt,
                    path_plan=package["path_plan"]["artifacts"],
                    owned_attempt_context=context,
                )
                self.assertEqual(runner.start_count, 1)
                self.assertTrue(result["launch_performed"])
                self.assertEqual(result["timed_out"], expected_timeout)
                if expected_code is not None:
                    self.assertEqual(result["return_code"], expected_code)
                if expected_state is not None:
                    self.assertEqual(result["termination_state"], expected_state)
                else:
                    self.assertIn(result["termination_state"], {"terminated_after_timeout", "killed_after_timeout"})
                self.assertTrue(Path(result["stdout_path"]).is_file())
                self.assertTrue(Path(result["stderr_path"]).is_file())

    def test_run_pilot_launches_once_finalizes_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package, _ = _materialize(root, attempt_id="pilot-once")
            runner = FakeRunner()
            first = run_production_pilot(
                package_path,
                repository_head=package["head"],
                process_runner=runner,
                completion_runner=_completion,
                prepared_root=package_path.parent.parent,
            )
            self.assertEqual(first["state"], "finalized")
            self.assertEqual(runner.calls, 1)
            second = run_production_pilot(
                package_path,
                repository_head=package["head"],
                process_runner=runner,
                completion_runner=_completion,
                prepared_root=package_path.parent.parent,
            )
            self.assertEqual(second["state"], "already_finalized")
            self.assertEqual(runner.calls, 1)

    def test_final_marker_without_terminal_recovers_without_launch_or_completion(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package, _ = _materialize(root, attempt_id="final-recovery")
            runner = FakeRunner()
            run_production_pilot(
                package_path,
                repository_head=package["head"],
                process_runner=runner,
                completion_runner=_completion,
                prepared_root=package_path.parent.parent,
            )
            paths = attempt_path_plan(
                package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
            )["artifacts"]
            Path(paths["ownership_terminal"]).unlink()

            def forbidden_completion(*args, **kwargs):
                raise AssertionError("completion must not rerun after a validated final marker")

            recovered = run_production_pilot(
                package_path,
                repository_head=package["head"],
                process_runner=FakeRunner(),
                completion_runner=forbidden_completion,
                prepared_root=package_path.parent.parent,
            )
            self.assertEqual(recovered["state"], "finalized")
            self.assertTrue(Path(paths["ownership_terminal"]).is_file())

    def test_run_pilot_recovers_complete_launch_evidence_without_relaunch(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package, result = _materialize(root, attempt_id="recover1")
            owned = load_owned_attempt_context(result["owned_context_path"], expected_head=package["head"])
            first_runner = FakeRunner()
            launch_owned_attempt(
                owned, first_runner, mode="production", repository_head=package["head"]
            )
            forbidden_runner = FakeRunner()
            recovered = run_production_pilot(
                package_path,
                repository_head=package["head"],
                process_runner=forbidden_runner,
                completion_runner=_completion,
                prepared_root=package_path.parent.parent,
            )
            self.assertEqual(recovered["state"], "finalized")
            self.assertFalse(recovered["runner_invoked"])
            self.assertEqual(first_runner.calls, 1)
            self.assertEqual(forbidden_runner.calls, 0)

    def test_failed_process_is_consumed_once_and_never_retried(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package, _ = _materialize(root, attempt_id="failed-once")
            first_runner = FakeRunner(code=9)
            first = run_production_pilot(
                package_path,
                repository_head=package["head"],
                process_runner=first_runner,
                completion_runner=_completion,
                prepared_root=package_path.parent.parent,
            )
            self.assertEqual(first["state"], "process_failed")
            recovery_runner = FakeRunner()
            second = run_production_pilot(
                package_path,
                repository_head=package["head"],
                process_runner=recovery_runner,
                completion_runner=_completion,
                prepared_root=package_path.parent.parent,
            )
            self.assertEqual(second["state"], "process_failed")
            self.assertEqual(first_runner.calls, 1)
            self.assertEqual(recovery_runner.calls, 0)

    def test_run_pilot_partial_evidence_and_head_mismatch_fail_without_launch(self):
        for mode in ("partial", "head"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
                root = Path(directory)
                package_path, package, _ = _materialize(root, attempt_id=f"fail-{mode}")
                paths = attempt_path_plan(
                    package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
                )["artifacts"]
                if mode == "partial":
                    path = Path(paths["consumption_record"])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("partial", encoding="utf-8")
                runner = FakeRunner()
                with self.assertRaises(ValueError):
                    run_production_pilot(
                        package_path,
                        repository_head="wrong-head" if mode == "head" else package["head"],
                        process_runner=runner,
                        completion_runner=_completion,
                        prepared_root=package_path.parent.parent,
                    )
                self.assertEqual(runner.calls, 0)

    def test_pre_spawn_retirement_is_terminal_without_launch_evidence(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            package_path, package = build_prepared_launch_package(
                head="superseded-head", branch="main", attempt_id="retire1", package_root=root / "prepared"
            )
            authorization = {
                "authorization_id": "retirement-auth",
                "authorization_sha256": "a" * 64,
                "launch_id": package["launch_id"],
                "attempt_id": package["attempt_id"],
                "identity_id": package["identity_id"],
                "scene_id": package["scene_id"],
                "seed": package["seed"],
                "launch_spec_sha256": package["launch_spec_sha256"],
            }
            ownership = acquire_ownership(package["prospective_attempt_root"], authorization)
            ownership_bytes = Path(package["prospective_attempt_root"], OWNER).read_bytes()
            terminal = retire_pre_spawn_attempt(package_path, current_head="new-head")
            self.assertEqual(terminal["state"], "retired_pre_spawn")
            self.assertEqual(Path(package["prospective_attempt_root"], OWNER).read_bytes(), ownership_bytes)
            paths = attempt_path_plan(
                package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
            )["artifacts"]
            for key in ("owned_context", "consumption_record", "process_evidence", "final_marker"):
                self.assertFalse(Path(paths[key]).exists())
            owned = {
                "schema_version": "m6a-v2-owned-attempt-context-v1",
                "attempt_root": package["prospective_attempt_root"],
                "ownership": ownership,
                "launch_id": package["launch_id"],
                "attempt_id": package["attempt_id"],
                "identity_id": package["identity_id"],
                "authorization_id": ownership["authorization_id"],
                "nonce": "test-nonce",
                "execution_mode": "test",
                "test_fixture": True,
            }
            owned["canonical_digest"] = digest(owned)
            runner = FakeRunner()
            with self.assertRaises(ValueError):
                launch_owned_attempt(owned, runner, mode="test")
            self.assertEqual(runner.calls, 0)

    def test_zz_current_real_attempt_was_not_modified(self):
        current = (
            {str(path.relative_to(REAL_ATTEMPT)): path.read_bytes() for path in REAL_ATTEMPT.rglob("*") if path.is_file()}
            if REAL_ATTEMPT.is_dir()
            else {}
        )
        self.assertEqual(current, REAL_ATTEMPT_SNAPSHOT)


if __name__ == "__main__":
    unittest.main()
