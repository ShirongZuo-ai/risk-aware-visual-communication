import base64
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_detached_authorization import (
    AUTHORIZATION_FILENAME,
    BUNDLE_FILENAME,
    RECEIPT_FILENAME,
    authoritative_detached_authorization_paths,
    build_detached_signature_bundle,
    load_detached_signature_bundle,
    load_verified_authorization_receipt,
    persist_detached_signature_bundle,
    run_detached_authorization_verification_only,
    validate_detached_signature_bundle,
)
from scripts.m6a_v2_execution_authorization import (
    ED25519_DOMAIN,
    build_expected_authorization_binding,
    load_execution_authorization_artifact,
    verify_execution_authorization,
)
from scripts.m6a_v2_fresh_preflight import run_fresh_preflight_for_prepared_launch
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_production_trust import (
    REQUEST_SCHEMA,
    TRUST_SCHEMA,
    authoritative_signing_request_path,
    build_production_authorization_verifier_from_config,
    export_execution_authorization_signing_request,
    load_execution_authorization_signing_request,
)


def canonical_write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))


def make_trust(root, private_key):
    public_path = Path(root) / "config" / "trust" / "public.pem"
    public_path.parent.mkdir(parents=True)
    public = private_key.public_key()
    public_path.write_bytes(public.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    raw = public.public_bytes(Encoding.Raw, PublicFormat.Raw)
    value = {
        "schema_version": TRUST_SCHEMA,
        "verifier_type": "ed25519",
        "public_key_path": "config/trust/public.pem",
        "expected_public_key_fingerprint": __import__("hashlib").sha256(raw).hexdigest(),
        "expected_key_id": "ephemeral-key",
        "expected_issuer": "ephemeral-issuer",
        "accepted_authorization_policy_version": "ephemeral-policy",
        "verifier_identity": "ephemeral-verifier",
        "trust_domain": "ephemeral-domain",
        "signing_domain_hex": ED25519_DOMAIN.hex(),
    }
    value["config_digest"] = digest(value)
    config = Path(root) / "config" / "trust.json"
    canonical_write(config, value)
    return config


def reseal_bundle(bundle):
    bundle["canonical_bundle_digest"] = digest(
        {key: item for key, item in bundle.items() if key != "canonical_bundle_digest"}
    )
    return bundle


def reseal_artifact(artifact):
    artifact["payload_digest"] = digest(
        {key: item for key, item in artifact.items() if key not in {"payload_digest", "canonical_artifact_digest"}}
    )
    artifact["canonical_artifact_digest"] = digest(
        {key: item for key, item in artifact.items() if key != "canonical_artifact_digest"}
    )
    return artifact


class DetachedAuthorizationTests(unittest.TestCase):
    def prepare(self, root, *, attempt_id="offline1", request_minutes=2, private=None, trust=None):
        private = private or Ed25519PrivateKey.generate()
        trust = trust or make_trust(root, private)
        package_path, package = build_prepared_launch_package(
            head="test-head", branch="main", attempt_id=attempt_id, package_root=Path(root) / "control"
        )
        now = datetime.now(timezone.utc).replace(microsecond=0)
        run_fresh_preflight_for_prepared_launch(package_path, now=now)
        request_path = authoritative_signing_request_path(package_path)
        request = export_execution_authorization_signing_request(
            package_path,
            package["preflight_report_path"],
            trust,
            request_path,
            repository_root=root,
            issued_at_utc=now.isoformat(),
            expires_at_utc=(now + timedelta(minutes=request_minutes)).isoformat(),
            nonce=f"nonce-{attempt_id}",
        )
        return private, trust, package_path, package, request, now

    def make_bundle(self, private, request, now):
        exact_message = base64.b64decode(request["signed_message_base64"], validate=True)
        signature = private.sign(exact_message)
        return build_detached_signature_bundle(
            request,
            signature_base64=base64.b64encode(signature).decode("ascii"),
            signed_at_utc=now.isoformat(),
            now=now,
        )

    def test_valid_import_verification_receipt_and_verification_only_state(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            private, trust, package_path, package, request, now = self.prepare(directory)
            paths = authoritative_detached_authorization_paths(package_path)
            self.assertEqual(paths["detached_signature_bundle"].name, BUNDLE_FILENAME)
            self.assertEqual(paths["authorization_artifact"].name, AUTHORIZATION_FILENAME)
            self.assertEqual(paths["verified_receipt"].name, RECEIPT_FILENAME)
            bundle = self.make_bundle(private, request, now)
            persisted = persist_detached_signature_bundle(
                paths["detached_signature_bundle"], bundle, request=request, now=now
            )
            self.assertEqual(
                load_detached_signature_bundle(paths["detached_signature_bundle"], request=request)["canonical_bundle_digest"],
                persisted["canonical_bundle_digest"],
            )
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
                result = run_detached_authorization_verification_only(
                    package_path,
                    package["preflight_report_path"],
                    trust,
                    repository_root=directory,
                )
                for prohibited in (context_factory, materialize, ownership, consume, final_marker, process_spawn):
                    prohibited.assert_not_called()
            binding = build_expected_authorization_binding(package_path, package["preflight_report_path"])
            artifact = load_execution_authorization_artifact(paths["authorization_artifact"])
            receipt = load_verified_authorization_receipt(paths["verified_receipt"], binding)
            self.assertEqual(artifact["authorization_id"], request["authorization_id"])
            self.assertEqual(receipt.data["authorization_id"], request["authorization_id"])
            expected_true = {"trust_root_loaded", "signature_present", "authorization_verified", "trust_verified", "receipt_valid"}
            expected_false = {
                "execution_context_created", "execution_authorized_for_materialization", "materialization_allowed",
                "attempt_materialized", "ownership_acquired", "process_launched", "authorization_consumed",
                "final_marker_written",
            }
            self.assertTrue(all(result[key] is True for key in expected_true))
            self.assertTrue(all(result[key] is False for key in expected_false))
            self.assertFalse(Path(package["prospective_attempt_root"]).exists())

    def test_bundle_binding_encoding_timing_and_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            private, _, _, _, request, now = self.prepare(directory)
            original = self.make_bundle(private, request, now)
            mutations = {
                "authorization": lambda value: value.__setitem__("authorization_id", "wrong"),
                "request_digest": lambda value: value.__setitem__("unsigned_request_digest", "0" * 64),
                "message_digest": lambda value: value.__setitem__("signed_message_sha256", "0" * 64),
                "key_id": lambda value: value.__setitem__("key_id", "wrong"),
                "scheme": lambda value: value.__setitem__("signature_scheme", "rsa"),
                "malformed": lambda value: value.__setitem__("signature_base64", "%%%"),
                "truncated": lambda value: value.__setitem__("signature_base64", base64.b64encode(b"short").decode()),
                "future": lambda value: value.__setitem__("signed_at_utc", (now + timedelta(seconds=1)).isoformat()),
            }
            for name, mutation in mutations.items():
                with self.subTest(name=name):
                    candidate = json.loads(json.dumps(original))
                    mutation(candidate)
                    reseal_bundle(candidate)
                    with self.assertRaises(ValueError):
                        validate_detached_signature_bundle(candidate, request=request, now=now)
            tampered = json.loads(json.dumps(original))
            tampered["signature_base64"] = base64.b64encode(b"x" * 64).decode()
            with self.assertRaises(ValueError):
                validate_detached_signature_bundle(tampered, request=request, now=now)

    def test_wrong_signature_replay_and_claimed_key_cannot_change_trust_root(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            private, trust, package_path, package, request, now = self.prepare(directory, attempt_id="wrong-signature")
            paths = authoritative_detached_authorization_paths(package_path)
            wrong = Ed25519PrivateKey.generate()
            wrong_signature = wrong.sign(base64.b64decode(request["signed_message_base64"]))
            bundle = build_detached_signature_bundle(
                request,
                signature_base64=base64.b64encode(wrong_signature).decode(),
                signed_at_utc=now.isoformat(),
                now=now,
            )
            persist_detached_signature_bundle(paths["detached_signature_bundle"], bundle, request=request, now=now)
            with self.assertRaises(PermissionError):
                run_detached_authorization_verification_only(
                    package_path, package["preflight_report_path"], trust, repository_root=directory
                )

        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            private, trust, first_package, first, first_request, now = self.prepare(directory, attempt_id="replay-source")
            _, _, second_package, second, second_request, second_now = self.prepare(
                directory, attempt_id="replay-target", private=private, trust=trust
            )
            copied_signature = private.sign(base64.b64decode(first_request["signed_message_base64"]))
            replay = build_detached_signature_bundle(
                second_request,
                signature_base64=base64.b64encode(copied_signature).decode(),
                signed_at_utc=second_now.isoformat(),
                now=second_now,
            )
            replay_paths = authoritative_detached_authorization_paths(second_package)
            persist_detached_signature_bundle(
                replay_paths["detached_signature_bundle"], replay, request=second_request, now=second_now
            )
            with self.assertRaises(PermissionError):
                run_detached_authorization_verification_only(
                    second_package, second["preflight_report_path"], trust, repository_root=directory
                )

            valid_paths = authoritative_detached_authorization_paths(first_package)
            valid_bundle = self.make_bundle(private, first_request, now)
            persist_detached_signature_bundle(
                valid_paths["detached_signature_bundle"], valid_bundle, request=first_request, now=now
            )
            binding = build_expected_authorization_binding(first_package, first["preflight_report_path"])
            from scripts.m6a_v2_detached_authorization import import_execution_authorization_artifact

            artifact = import_execution_authorization_artifact(
                valid_paths["authorization_artifact"], request=first_request,
                signature_bundle=valid_bundle, binding=binding, now=now,
            )
            artifact["authenticator_envelope"]["claimed_public_key_fingerprint"] = "0" * 64
            reseal_artifact(artifact)
            canonical_write(valid_paths["authorization_artifact"], artifact)
            verifier = build_production_authorization_verifier_from_config(trust, repository_root=directory)
            with self.assertRaises(PermissionError):
                verify_execution_authorization(
                    first_package, first["preflight_report_path"], valid_paths["authorization_artifact"], verifier
                )

    def test_request_bundle_and_receipt_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            private, trust, package_path, package, request, now = self.prepare(directory, attempt_id="tamper")
            paths = authoritative_detached_authorization_paths(package_path)
            bundle = self.make_bundle(private, request, now)
            persist_detached_signature_bundle(paths["detached_signature_bundle"], bundle, request=request, now=now)
            request_path = paths["unsigned_request"]
            request_value = json.loads(request_path.read_text(encoding="utf-8"))
            request_value["nonce"] = "tampered"
            canonical_write(request_path, request_value)
            with self.assertRaises(ValueError):
                run_detached_authorization_verification_only(
                    package_path, package["preflight_report_path"], trust, repository_root=directory
                )

    def test_expired_request_and_stale_preflight_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            _, trust, package_path, package, _, now = self.prepare(directory, attempt_id="expired", request_minutes=2)
            with self.assertRaises(ValueError):
                load_execution_authorization_signing_request(
                    authoritative_signing_request_path(package_path), package_path=package_path,
                    preflight_path=package["preflight_report_path"], trust_config_path=trust,
                    repository_root=directory, now=now + timedelta(minutes=3),
                )

        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.m6a_v2_execution_safety.PILOT_ROOT", Path(directory) / "pilot"
        ):
            _, trust, package_path, package, _, now = self.prepare(directory, attempt_id="stale", request_minutes=15)
            with self.assertRaises(ValueError):
                load_execution_authorization_signing_request(
                    authoritative_signing_request_path(package_path), package_path=package_path,
                    preflight_path=package["preflight_report_path"], trust_config_path=trust,
                    repository_root=directory, now=now + timedelta(minutes=6),
                )


if __name__ == "__main__":
    unittest.main()
