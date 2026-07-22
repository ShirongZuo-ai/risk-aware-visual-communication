import base64
import json
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_authorization_operator import materialize_current_verified_authorization
from scripts.m6a_v2_detached_authorization import (
    authoritative_detached_authorization_paths,
    build_detached_signature_bundle,
    persist_detached_signature_bundle,
    run_detached_authorization_verification_only,
)
from scripts.m6a_v2_execution_safety import OWNER, attempt_path_plan, materialize_authorized_attempt
from scripts.m6a_v2_fresh_preflight import run_fresh_preflight_for_prepared_launch
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_production_trust import export_execution_authorization_signing_request
from tests.test_m6a_v2_production_trust import make_trust


def canonical_write(path, value):
    Path(path).write_bytes((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))


@contextmanager
def isolated_execution_roots(directory):
    root = Path(directory)
    with patch("scripts.m6a_v2_execution_safety.PILOT_ROOT", root / "pilot"), patch(
        "scripts.m6a_v2_execution_safety.CONTROL_ROOT", root / "control-evidence"
    ):
        yield


class MaterializationOperatorTests(unittest.TestCase):
    def prepare_verified(self, root, *, attempt_id="materialize1", request_minutes=15):
        private = Ed25519PrivateKey.generate()
        trust, _ = make_trust(root, private.public_key())
        package_path, package = build_prepared_launch_package(
            head="materialize-head", branch="main", attempt_id=attempt_id, package_root=Path(root) / "control"
        )
        now = datetime.now(timezone.utc).replace(microsecond=0)
        run_fresh_preflight_for_prepared_launch(package_path, now=now)
        paths = authoritative_detached_authorization_paths(package_path)
        request = export_execution_authorization_signing_request(
            package_path,
            package["preflight_report_path"],
            trust,
            paths["unsigned_request"],
            repository_root=root,
            issued_at_utc=now.isoformat(),
            expires_at_utc=(now + timedelta(minutes=request_minutes)).isoformat(),
            nonce=f"nonce-{attempt_id}",
            now=now,
        )
        signature = private.sign(base64.b64decode(request["signed_message_base64"], validate=True))
        bundle = build_detached_signature_bundle(
            request,
            signature_base64=base64.b64encode(signature).decode("ascii"),
            signed_at_utc=now.isoformat(),
            now=now,
        )
        persist_detached_signature_bundle(paths["detached_signature_bundle"], bundle, request=request, now=now)
        run_detached_authorization_verification_only(
            package_path, package["preflight_report_path"], trust, repository_root=root, now=now
        )
        return trust, package_path, package, paths, request, now

    def test_materialize_only_creates_reloaded_ownership_and_nothing_later(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            trust, package_path, package, _, _, _ = self.prepare_verified(root)
            with patch("scripts.m6a_v2_execution_safety.launch_owned_attempt") as runner, patch(
                "scripts.m6a_v2_execution_safety.consume_authorization"
            ) as consume, patch("scripts.m6a_v2_execution_safety.write_final_marker") as final_marker, patch(
                "subprocess.Popen"
            ) as process_spawn:
                result = materialize_current_verified_authorization(
                    package_path, trust, repository_root=root
                )
                for prohibited in (runner, consume, final_marker, process_spawn):
                    prohibited.assert_not_called()
            attempt_root = Path(result["attempt_root"])
            ownership_path = Path(result["ownership_path"])
            self.assertTrue(attempt_root.is_dir())
            self.assertEqual(list(attempt_root.iterdir()), [ownership_path])
            ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
            self.assertEqual(ownership["sha256"], result["ownership_digest"])
            self.assertEqual(ownership["state"], "owned_pre_spawn")
            self.assertFalse(ownership["launch_performed"])
            for key in ("trust_verified", "receipt_valid", "execution_context_created", "materialization_allowed", "attempt_materialized", "ownership_acquired"):
                self.assertTrue(result[key])
            for key in ("process_launched", "authorization_consumed", "final_marker_written"):
                self.assertFalse(result[key])
            plan = attempt_path_plan(
                package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
            )["artifacts"]
            self.assertFalse(Path(plan["consumption_record"]).exists())
            self.assertFalse(Path(plan["process_evidence"]).exists())
            self.assertFalse(Path(plan["final_marker"]).exists())
            with self.assertRaises(ValueError):
                materialize_current_verified_authorization(package_path, trust, repository_root=root)

    def test_expired_preflight_and_request_fail_before_root_creation(self):
        for label, request_minutes, delta in (("request", 1, 2), ("preflight", 15, 6)):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
                root = Path(directory)
                trust, package_path, package, _, _, now = self.prepare_verified(
                    root, attempt_id=f"expired-{label}", request_minutes=request_minutes
                )
                with self.assertRaises(ValueError):
                    materialize_current_verified_authorization(
                        package_path, trust, repository_root=root, now=now + timedelta(minutes=delta)
                    )
                self.assertFalse(Path(package["prospective_attempt_root"]).exists())

    def test_expired_authorization_receipt_tamper_and_test_receipt_fail(self):
        for mode in ("authorization", "receipt-expired", "receipt-tamper", "test-receipt"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
                root = Path(directory)
                trust, package_path, package, paths, _, now = self.prepare_verified(
                    root, attempt_id=f"invalid-{mode}"
                )
                if mode == "authorization":
                    artifact = json.loads(paths["authorization_artifact"].read_text(encoding="utf-8"))
                    artifact["expires_at_utc"] = (now - timedelta(seconds=1)).isoformat()
                    artifact["payload_digest"] = digest(
                        {key: item for key, item in artifact.items() if key not in {"payload_digest", "canonical_artifact_digest"}}
                    )
                    artifact["canonical_artifact_digest"] = digest(
                        {key: item for key, item in artifact.items() if key != "canonical_artifact_digest"}
                    )
                    canonical_write(paths["authorization_artifact"], artifact)
                else:
                    receipt = json.loads(paths["verified_receipt"].read_text(encoding="utf-8"))
                    if mode == "receipt-expired":
                        receipt["expires_at_utc"] = (now - timedelta(seconds=1)).isoformat()
                        receipt["canonical_receipt_digest"] = digest(
                            {key: item for key, item in receipt.items() if key != "canonical_receipt_digest"}
                        )
                    elif mode == "receipt-tamper":
                        receipt["nonce"] = "tampered"
                    else:
                        receipt["verification_class"] = "test"
                        receipt["trust_domain"] = "test-only"
                        receipt["canonical_receipt_digest"] = digest(
                            {key: item for key, item in receipt.items() if key != "canonical_receipt_digest"}
                        )
                    canonical_write(paths["verified_receipt"], receipt)
                with self.assertRaises((ValueError, PermissionError)):
                    materialize_current_verified_authorization(package_path, trust, repository_root=root)
                self.assertFalse(Path(package["prospective_attempt_root"]).exists())

    def test_wrong_package_arbitrary_context_and_root_escape_fail(self):
        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            trust, package_path, package, _, _, _ = self.prepare_verified(root, attempt_id="wrong-boundary")
            with self.assertRaises(TypeError):
                materialize_authorized_attempt(package, {}, mode="production", prepared_package_path=package_path)
            wrong_package_path, _ = build_prepared_launch_package(
                head="other", branch="main", attempt_id="other-package", package_root=root / "other-control"
            )
            with self.assertRaises((ValueError, FileNotFoundError)):
                materialize_current_verified_authorization(wrong_package_path, trust, repository_root=root)
            with patch("scripts.m6a_v2_execution_safety.PILOT_ROOT", root / "other-pilot"):
                with self.assertRaises(ValueError):
                    materialize_current_verified_authorization(package_path, trust, repository_root=root)
            self.assertFalse(Path(package["prospective_attempt_root"]).exists())

    def test_existing_execution_evidence_and_ownership_write_failure_fail_closed(self):
        for evidence in ("ownership_marker", "consumption_record", "process_evidence", "final_marker"):
            with self.subTest(evidence=evidence), tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
                root = Path(directory)
                trust, package_path, package, _, _, _ = self.prepare_verified(
                    root, attempt_id=f"existing-{evidence.replace('_', '-')}"
                )
                plan = attempt_path_plan(
                    package["launch_id"], package["attempt_id"], package["identity_id"], package["scene_id"], package["seed"]
                )["artifacts"]
                path = Path(plan[evidence])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("preexisting", encoding="utf-8")
                with self.assertRaises((ValueError, FileNotFoundError, json.JSONDecodeError)):
                    materialize_current_verified_authorization(package_path, trust, repository_root=root)

        with tempfile.TemporaryDirectory() as directory, isolated_execution_roots(directory):
            root = Path(directory)
            trust, package_path, package, _, _, _ = self.prepare_verified(root, attempt_id="ownership-write-fail")
            with patch("scripts.m6a_v2_execution_safety._new", side_effect=OSError("simulated ownership write failure")):
                with self.assertRaises(OSError):
                    materialize_current_verified_authorization(package_path, trust, repository_root=root)
            self.assertFalse(Path(package["prospective_attempt_root"]).exists())


if __name__ == "__main__":
    unittest.main()
