import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, Encoding, PrivateFormat
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_v2_authorization_operator import refresh_and_export_current_request, verify_current_detached_signature
from scripts.m6a_v2_detached_authorization import authoritative_detached_authorization_paths
from scripts.m6a_v2_fresh_preflight import run_fresh_preflight_for_prepared_launch
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
    def test_full_short_window_rehearsal_archives_refreshes_signs_and_verifies_only(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            root = Path(directory)
            private = Ed25519PrivateKey.generate()
            trust, _ = make_trust(root, private.public_key())
            package_path, package = build_prepared_launch_package(
                head="rehearsal-head", branch="main", attempt_id="operator-rehearsal", package_root=root / "control"
            )
            current = datetime.now(timezone.utc).replace(microsecond=0)
            old_time = current - timedelta(minutes=10)
            run_fresh_preflight_for_prepared_launch(package_path, now=old_time)
            old_request_path = authoritative_detached_authorization_paths(package_path)["unsigned_request"]
            export_execution_authorization_signing_request(
                package_path,
                package["preflight_report_path"],
                trust,
                old_request_path,
                repository_root=root,
                issued_at_utc=old_time.isoformat(),
                expires_at_utc=(old_time + timedelta(minutes=2)).isoformat(),
                nonce="expired-rehearsal-request",
                now=old_time,
            )
            old_request_bytes = old_request_path.read_bytes()

            command_a = refresh_and_export_current_request(
                package_path, trust, repository_root=root, now=current
            )
            archive = Path(command_a["archived_unsigned_request_path"])
            self.assertEqual(archive.read_bytes(), old_request_bytes)
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


if __name__ == "__main__":
    unittest.main()
