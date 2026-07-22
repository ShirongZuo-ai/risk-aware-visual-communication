import importlib.util
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, Encoding, PrivateFormat
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_v2_authorization_operator import (
    REQUEST_HISTORY_DIRECTORY,
    archive_existing_unsigned_request,
    refresh_and_export_current_request,
    verify_current_detached_signature,
)
from scripts.m6a_v2_detached_authorization import authoritative_detached_authorization_paths
from scripts.m6a_v2_fresh_preflight import (
    refresh_fresh_preflight_for_prepared_launch,
    run_fresh_preflight_for_prepared_launch,
)
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_production_trust import export_execution_authorization_signing_request
from tests.test_m6a_v2_production_trust import make_trust


def load_offline_template():
    path = PROJECT_ROOT / "docs" / "templates" / "m6a_v2_offline_sign_detached.py"
    spec = importlib.util.spec_from_file_location("m6a_v2_offline_sign_detached_template", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuthorizationOperatorTests(unittest.TestCase):
    def prepare_expired(self, root, *, attempt_id):
        private = Ed25519PrivateKey.generate()
        trust, _ = make_trust(root, private.public_key())
        package_path, package = build_prepared_launch_package(
            head="rehearsal-head", branch="main", attempt_id=attempt_id, package_root=root / "control"
        )
        current = datetime.now(timezone.utc).replace(microsecond=0)
        old_time = current - timedelta(minutes=10)
        run_fresh_preflight_for_prepared_launch(package_path, now=old_time)
        request_path = authoritative_detached_authorization_paths(package_path)["unsigned_request"]
        request = export_execution_authorization_signing_request(
            package_path,
            package["preflight_report_path"],
            trust,
            request_path,
            repository_root=root,
            issued_at_utc=old_time.isoformat(),
            expires_at_utc=(old_time + timedelta(minutes=2)).isoformat(),
            nonce=f"expired-{attempt_id}",
            now=old_time,
        )
        return private, trust, package_path, package, request_path, request, current

    def test_full_short_window_rehearsal_archives_refreshes_signs_and_verifies_only(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            root = Path(directory)
            private, trust, package_path, package, old_request_path, _, current = self.prepare_expired(
                root, attempt_id="operator-rehearsal"
            )
            old_request_bytes = old_request_path.read_bytes()
            history = package_path.parent / REQUEST_HISTORY_DIRECTORY
            self.assertFalse(history.exists())

            command_a = refresh_and_export_current_request(
                package_path, trust, repository_root=root, now=current
            )
            archive = Path(command_a["archived_unsigned_request_path"])
            self.assertEqual(archive.read_bytes(), old_request_bytes)
            self.assertEqual(hashlib.sha256(archive.read_bytes()).digest(), hashlib.sha256(old_request_bytes).digest())
            self.assertEqual(archive.name, f"request.{json.loads(old_request_bytes)['canonical_request_digest']}.json")
            self.assertLess(len(str(archive)), 260)
            self.assertNotEqual(old_request_path.read_bytes(), old_request_bytes)
            self.assertGreater(
                datetime.fromisoformat(command_a["effective_deadline_utc"]), current
            )
            self.assertTrue(list((package_path.parent / "fresh_preflight_history").glob("*.json")))

            private_path = root / "external-signer" / "ephemeral-private.pem"
            private_path.parent.mkdir()
            private_path.write_bytes(
                private.private_bytes(
                    Encoding.PEM,
                    PrivateFormat.PKCS8,
                    BestAvailableEncryption(b"ephemeral-password"),
                )
            )
            paths = authoritative_detached_authorization_paths(package_path)
            template = load_offline_template()
            signed = template.sign_request(
                repository_root=PROJECT_ROOT,
                request_path=paths["unsigned_request"],
                private_key_path=private_path,
                output_path=paths["detached_signature_bundle"],
                password_provider=lambda _: "ephemeral-password",
            )
            self.assertEqual(signed["authorization_id"], command_a["authorization_id"])

            with patch(
                "scripts.m6a_v2_execution_authorization.build_externally_validated_execution_context"
            ) as context_factory, patch(
                "scripts.m6a_v2_execution_safety.materialize_authorized_attempt"
            ) as materialize, patch(
                "scripts.m6a_v2_execution_safety.acquire_ownership"
            ) as ownership, patch(
                "scripts.m6a_v2_execution_safety.consume_authorization"
            ) as consume, patch(
                "scripts.m6a_v2_execution_safety.write_final_marker"
            ) as final_marker, patch("subprocess.Popen") as process_spawn:
                command_c = verify_current_detached_signature(
                    package_path, trust, repository_root=root
                )
                for prohibited in (context_factory, materialize, ownership, consume, final_marker, process_spawn):
                    prohibited.assert_not_called()
            self.assertTrue(command_c["trust_verified"])
            self.assertTrue(command_c["authorization_verified"])
            self.assertTrue(command_c["receipt_valid"])
            for key in (
                "execution_context_created", "materialization_allowed", "attempt_materialized",
                "ownership_acquired", "process_launched", "authorization_consumed", "final_marker_written",
            ):
                self.assertFalse(command_c[key])
            self.assertFalse(Path(package["prospective_attempt_root"]).exists())

    def test_existing_history_and_repeated_refresh_export_are_safe(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            root = Path(directory)
            _, trust, package_path, _, request_path, _, current = self.prepare_expired(
                root, attempt_id="history-repeat"
            )
            (package_path.parent / REQUEST_HISTORY_DIRECTORY).mkdir()
            first = refresh_and_export_current_request(package_path, trust, repository_root=root, now=current)
            second = refresh_and_export_current_request(package_path, trust, repository_root=root, now=current)
            self.assertEqual(first["unsigned_request_digest"], second["unsigned_request_digest"])
            self.assertEqual(first["authorization_id"], second["authorization_id"])
            self.assertTrue(request_path.is_file())

    def test_archive_conflict_and_identical_duplicate_recovery(self):
        for conflict in (False, True):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as directory, patch(
                "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
            ):
                root = Path(directory)
                _, trust, package_path, _, request_path, request, _ = self.prepare_expired(
                    root, attempt_id=f"archive-{'conflict' if conflict else 'same'}"
                )
                history = package_path.parent / REQUEST_HISTORY_DIRECTORY
                history.mkdir()
                archive = history / f"request.{request['canonical_request_digest']}.json"
                archive.write_bytes(b"conflict\n" if conflict else request_path.read_bytes())
                if conflict:
                    with self.assertRaises(FileExistsError):
                        archive_existing_unsigned_request(package_path, trust, repository_root=root)
                    self.assertTrue(request_path.is_file())
                else:
                    recovered = archive_existing_unsigned_request(package_path, trust, repository_root=root)
                    self.assertEqual(recovered, archive)
                    self.assertFalse(request_path.exists())

    def test_recover_after_request_archive_before_preflight_refresh(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            root = Path(directory)
            _, trust, package_path, _, request_path, old_request, current = self.prepare_expired(
                root, attempt_id="crash-before-preflight"
            )
            archive = archive_existing_unsigned_request(package_path, trust, repository_root=root)
            self.assertFalse(request_path.exists())
            result = refresh_and_export_current_request(package_path, trust, repository_root=root, now=current)
            self.assertTrue(archive.is_file())
            self.assertNotEqual(result["unsigned_request_digest"], old_request["canonical_request_digest"])
            self.assertTrue(request_path.is_file())

    def test_recover_after_preflight_refresh_before_request_export(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            root = Path(directory)
            _, trust, package_path, _, request_path, _, current = self.prepare_expired(
                root, attempt_id="crash-after-preflight"
            )
            archive_existing_unsigned_request(package_path, trust, repository_root=root)
            refresh_fresh_preflight_for_prepared_launch(package_path, now=current)
            self.assertFalse(request_path.exists())
            result = refresh_and_export_current_request(package_path, trust, repository_root=root, now=current)
            self.assertTrue(request_path.is_file())
            self.assertGreater(datetime.fromisoformat(result["effective_deadline_utc"]), current)

    def test_source_absent_archive_recovery_and_both_absent_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            root = Path(directory)
            _, trust, package_path, _, _, request, _ = self.prepare_expired(
                root, attempt_id="source-absent"
            )
            archive = archive_existing_unsigned_request(package_path, trust, repository_root=root)
            recovered = archive_existing_unsigned_request(
                package_path,
                trust,
                repository_root=root,
                expected_request_digest=request["canonical_request_digest"],
            )
            self.assertEqual(recovered, archive)
            archive.unlink()
            with self.assertRaises(FileNotFoundError):
                archive_existing_unsigned_request(
                    package_path,
                    trust,
                    repository_root=root,
                    expected_request_digest=request["canonical_request_digest"],
                )

    def test_history_path_escape_and_wrong_type_fail_closed(self):
        for mode in ("escape", "file"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory, patch(
                "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
            ):
                root = Path(directory)
                _, trust, package_path, _, request_path, _, _ = self.prepare_expired(
                    root, attempt_id=f"unsafe-history-{mode}"
                )
                if mode == "escape":
                    outside = package_path.parent.parent / "escape"
                    with patch("scripts.m6a_v2_authorization_operator.REQUEST_HISTORY_DIRECTORY", "../escape"):
                        with self.assertRaises(ValueError):
                            archive_existing_unsigned_request(package_path, trust, repository_root=root)
                    self.assertFalse(outside.exists())
                else:
                    (package_path.parent / REQUEST_HISTORY_DIRECTORY).write_text("not a directory", encoding="utf-8")
                    with self.assertRaises(ValueError):
                        archive_existing_unsigned_request(package_path, trust, repository_root=root)
                self.assertTrue(request_path.is_file())


if __name__ == "__main__":
    unittest.main()
