import base64
import hashlib
import importlib.util
import json
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, Encoding, PrivateFormat

import scripts.m6a_v2_authorization_operator as operator
from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_authorization_operator import (
    AUTHORIZATION_GENERATION_HISTORY_DIRECTORY,
    archive_existing_unsigned_request,
    archive_existing_verified_authorization_generation,
    refresh_and_export_current_request,
    verify_current_detached_signature,
)
from scripts.m6a_v2_detached_authorization import authoritative_detached_authorization_paths
from scripts.m6a_v2_fresh_preflight import (
    refresh_fresh_preflight_for_prepared_launch,
    run_fresh_preflight_for_prepared_launch,
)
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_production_trust import (
    export_execution_authorization_signing_request,
    run_production_authorization_readiness,
)
from tests.test_m6a_v2_production_trust import make_trust


def _canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _offline_template():
    path = PROJECT_ROOT / "docs" / "templates" / "m6a_v2_offline_sign_detached.py"
    spec = importlib.util.spec_from_file_location("m6a_v2_generation_archive_signer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def _isolated_execution_roots(root):
    with patch("scripts.m6a_v2_execution_safety.PILOT_ROOT", root / "pilot"), patch(
        "scripts.m6a_v2_execution_safety.CONTROL_ROOT", root / "execution-control"
    ):
        yield


class AuthorizationGenerationArchiveTests(unittest.TestCase):
    def prepare_verified(self, root, *, attempt_id):
        private = Ed25519PrivateKey.generate()
        trust, _ = make_trust(root, private.public_key())
        package_path, package = build_prepared_launch_package(
            head="generation-archive-head",
            branch="main",
            attempt_id=attempt_id,
            package_root=root / "control",
        )
        issued = datetime.now(timezone.utc).replace(microsecond=0)
        run_fresh_preflight_for_prepared_launch(package_path, now=issued)
        paths = authoritative_detached_authorization_paths(package_path)
        request = export_execution_authorization_signing_request(
            package_path,
            package["preflight_report_path"],
            trust,
            paths["unsigned_request"],
            repository_root=root,
            issued_at_utc=issued.isoformat(),
            expires_at_utc=(issued + timedelta(minutes=5)).isoformat(),
            nonce=f"generation-{attempt_id}",
            now=issued,
        )
        private_path = root / "ephemeral-signer" / "private.pem"
        private_path.parent.mkdir()
        private_path.write_bytes(
            private.private_bytes(
                Encoding.PEM,
                PrivateFormat.PKCS8,
                BestAvailableEncryption(b"temporary-test-password"),
            )
        )
        _offline_template().sign_request(
            repository_root=PROJECT_ROOT,
            request_path=paths["unsigned_request"],
            private_key_path=private_path,
            output_path=paths["detached_signature_bundle"],
            password_provider=lambda _: "temporary-test-password",
        )
        result = verify_current_detached_signature(package_path, trust, repository_root=root)
        self.assertTrue(result["receipt_valid"])
        source_bytes = {
            key: paths[key].read_bytes()
            for key in ("detached_signature_bundle", "authorization_artifact", "verified_receipt")
        }
        return trust, package_path, package, paths, request, source_bytes, issued

    def test_valid_generation_archives_exact_bytes_then_refreshes_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _isolated_execution_roots(root):
                trust, package_path, package, paths, old_request, source_bytes, issued = self.prepare_verified(
                    root, attempt_id="archive-valid"
                )
                with patch(
                    "scripts.m6a_v2_authorization_operator.build_externally_validated_execution_context"
                ) as context, patch(
                    "scripts.m6a_v2_authorization_operator.materialize_authorized_attempt"
                ) as materialize, patch(
                    "scripts.m6a_v2_execution_safety.acquire_ownership"
                ) as ownership, patch(
                    "scripts.m6a_v2_execution_safety.consume_authorization"
                ) as consume, patch(
                    "scripts.m6a_v2_execution_safety.write_final_marker"
                ) as final_marker, patch("subprocess.Popen") as process:
                    result = refresh_and_export_current_request(
                        package_path,
                        trust,
                        repository_root=root,
                        now=issued + timedelta(minutes=10),
                    )
                    for prohibited in (context, materialize, ownership, consume, final_marker, process):
                        prohibited.assert_not_called()
                archived = result["archived_verification_generation"]
                archive_root = Path(archived["archive_directory"])
                self.assertLess(max(len(str(path)) for path in archive_root.iterdir()), 260)
                for key, filename in {
                    "detached_signature_bundle": "bundle.json",
                    "authorization_artifact": "artifact.json",
                    "verified_receipt": "receipt.json",
                }.items():
                    archived_bytes = (archive_root / filename).read_bytes()
                    self.assertEqual(archived_bytes, source_bytes[key])
                    self.assertEqual(
                        hashlib.sha256(archived_bytes).hexdigest(),
                        hashlib.sha256(source_bytes[key]).hexdigest(),
                    )
                    self.assertFalse(paths[key].exists())
                self.assertNotEqual(result["authorization_id"], old_request["authorization_id"])
                self.assertNotEqual(result["unsigned_request_digest"], old_request["canonical_request_digest"])
                self.assertFalse(Path(package["prospective_attempt_root"]).exists())

    def test_partial_archive_recovers_with_all_sources_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _isolated_execution_roots(root):
                trust, package_path, _, paths, request, source_bytes, _ = self.prepare_verified(
                    root, attempt_id="partial-archive"
                )
                original = operator._persist_exact_bytes
                calls = 0

                def interrupt_after_first(path, raw, description):
                    nonlocal calls
                    original(path, raw, description)
                    calls += 1
                    if calls == 1:
                        raise RuntimeError("simulated archive interruption")

                with patch(
                    "scripts.m6a_v2_authorization_operator._persist_exact_bytes",
                    side_effect=interrupt_after_first,
                ):
                    with self.assertRaisesRegex(RuntimeError, "simulated archive interruption"):
                        archive_existing_verified_authorization_generation(
                            package_path, trust, repository_root=root
                        )
                self.assertTrue(all(paths[key].exists() for key in source_bytes))
                recovered = archive_existing_verified_authorization_generation(
                    package_path, trust, repository_root=root
                )
                self.assertEqual(recovered["unsigned_request_digest"], request["canonical_request_digest"])
                self.assertTrue(Path(recovered["manifest_path"]).is_file())
                self.assertTrue(all(not paths[key].exists() for key in source_bytes))

    def test_completed_archive_is_idempotent_and_releases_identical_recovered_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _isolated_execution_roots(root):
                trust, package_path, _, paths, request, source_bytes, _ = self.prepare_verified(
                    root, attempt_id="archive-idempotent"
                )
                first = archive_existing_verified_authorization_generation(
                    package_path, trust, repository_root=root
                )
                second = archive_existing_verified_authorization_generation(
                    package_path,
                    trust,
                    repository_root=root,
                    expected_request_digest=request["canonical_request_digest"],
                )
                self.assertEqual(first, second)
                for key, raw in source_bytes.items():
                    paths[key].write_bytes(raw)
                third = archive_existing_verified_authorization_generation(
                    package_path, trust, repository_root=root
                )
                self.assertEqual(first, third)
                self.assertTrue(all(not paths[key].exists() for key in source_bytes))

    def test_conflicting_partial_archive_fails_without_releasing_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _isolated_execution_roots(root):
                trust, package_path, _, paths, request, source_bytes, _ = self.prepare_verified(
                    root, attempt_id="archive-conflict"
                )
                archive = operator._generation_archive_directory(
                    package_path.parent, request["canonical_request_digest"]
                )
                (archive / "bundle.json").write_bytes(b"conflict\n")
                with self.assertRaises(FileExistsError):
                    archive_existing_verified_authorization_generation(
                        package_path, trust, repository_root=root
                    )
                self.assertTrue(all(paths[key].read_bytes() == raw for key, raw in source_bytes.items()))

    def test_incomplete_source_without_completed_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _isolated_execution_roots(root):
                trust, package_path, _, paths, _, source_bytes, _ = self.prepare_verified(
                    root, attempt_id="incomplete-source"
                )
                paths["verified_receipt"].unlink()
                with self.assertRaisesRegex(ValueError, "incomplete current verification generation"):
                    archive_existing_verified_authorization_generation(
                        package_path, trust, repository_root=root
                    )
                self.assertEqual(paths["detached_signature_bundle"].read_bytes(), source_bytes["detached_signature_bundle"])
                self.assertEqual(paths["authorization_artifact"].read_bytes(), source_bytes["authorization_artifact"])

    def _assert_tamper_fails(self, attempt_id, target, mutate):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _isolated_execution_roots(root):
                trust, package_path, _, paths, _, _, _ = self.prepare_verified(root, attempt_id=attempt_id)
                path = paths[target]
                value = json.loads(path.read_bytes())
                mutate(value)
                if target == "detached_signature_bundle":
                    value.pop("canonical_bundle_digest", None)
                    value["canonical_bundle_digest"] = digest(value)
                elif target == "authorization_artifact":
                    value.pop("payload_digest", None)
                    value.pop("canonical_artifact_digest", None)
                    value["payload_digest"] = digest(value)
                    value["canonical_artifact_digest"] = digest(value)
                else:
                    value.pop("canonical_receipt_digest", None)
                    value["canonical_receipt_digest"] = digest(value)
                path.write_bytes(_canonical_bytes(value))
                with self.assertRaises((ValueError, PermissionError)):
                    archive_existing_verified_authorization_generation(
                        package_path, trust, repository_root=root
                    )

    def test_wrong_authorization_id_fails_closed(self):
        self._assert_tamper_fails(
            "wrong-authorization-id",
            "authorization_artifact",
            lambda value: value.__setitem__("authorization_id", "0" * 64),
        )

    def test_wrong_request_digest_fails_closed(self):
        self._assert_tamper_fails(
            "wrong-request-digest",
            "detached_signature_bundle",
            lambda value: value.__setitem__("unsigned_request_digest", "0" * 64),
        )

    def test_receipt_tamper_fails_closed(self):
        self._assert_tamper_fails(
            "receipt-tamper",
            "verified_receipt",
            lambda value: value.__setitem__("nonce", "tampered-receipt"),
        )

    def test_artifact_tamper_fails_closed(self):
        self._assert_tamper_fails(
            "artifact-tamper",
            "authorization_artifact",
            lambda value: value.__setitem__("nonce", "tampered-artifact"),
        )

    def test_bundle_tamper_fails_closed(self):
        self._assert_tamper_fails(
            "bundle-tamper",
            "detached_signature_bundle",
            lambda value: value.__setitem__("signature_base64", base64.b64encode(b"\x00" * 64).decode()),
        )

    def test_new_current_request_does_not_capture_old_verified_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _isolated_execution_roots(root):
                trust, package_path, package, _, old_request, _, issued = self.prepare_verified(
                    root, attempt_id="new-request-old-generation"
                )
                archive_existing_unsigned_request(package_path, trust, repository_root=root)
                refreshed_at = issued + timedelta(seconds=1)
                refresh_fresh_preflight_for_prepared_launch(package_path, now=refreshed_at)
                readiness = run_production_authorization_readiness(
                    package_path,
                    package["preflight_report_path"],
                    trust,
                    repository_root=root,
                    now=refreshed_at,
                )
                current_digest = readiness["signing_request_digest"]
                result = refresh_and_export_current_request(
                    package_path, trust, repository_root=root, now=refreshed_at
                )
                self.assertEqual(result["unsigned_request_digest"], current_digest)
                self.assertNotEqual(result["authorization_id"], old_request["authorization_id"])
                self.assertEqual(
                    result["archived_verification_generation"]["authorization_id"],
                    old_request["authorization_id"],
                )
                paths = authoritative_detached_authorization_paths(package_path)
                self.assertFalse(paths["detached_signature_bundle"].exists())
                self.assertFalse(paths["authorization_artifact"].exists())
                self.assertFalse(paths["verified_receipt"].exists())

    def test_generation_history_path_escape_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _isolated_execution_roots(root):
                trust, package_path, _, paths, _, source_bytes, _ = self.prepare_verified(
                    root, attempt_id="history-escape"
                )
                outside = package_path.parent.parent / "escape"
                with patch(
                    "scripts.m6a_v2_authorization_operator.AUTHORIZATION_GENERATION_HISTORY_DIRECTORY",
                    "../escape",
                ):
                    with self.assertRaises(ValueError):
                        archive_existing_verified_authorization_generation(
                            package_path, trust, repository_root=root
                        )
                self.assertFalse(outside.exists())
                self.assertTrue(all(paths[key].read_bytes() == raw for key, raw in source_bytes.items()))

    def test_generation_history_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with _isolated_execution_roots(root):
                trust, package_path, _, _, _, _, _ = self.prepare_verified(
                    root, attempt_id="history-symlink"
                )
                outside = root / "outside-history"
                outside.mkdir()
                history = package_path.parent / AUTHORIZATION_GENERATION_HISTORY_DIRECTORY
                try:
                    history.symlink_to(outside, target_is_directory=True)
                except OSError as exc:
                    self.skipTest(f"directory symlinks unavailable: {exc}")
                with self.assertRaises(ValueError):
                    archive_existing_verified_authorization_generation(
                        package_path, trust, repository_root=root
                    )


if __name__ == "__main__":
    unittest.main()
