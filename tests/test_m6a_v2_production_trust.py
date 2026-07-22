import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from scripts.m6a_common import PROJECT_ROOT
from scripts.m6a_trusted_artifacts import digest
from scripts.m6a_v2_execution_authorization import ED25519_DOMAIN, authorization_canonical_payload_bytes
from scripts.m6a_v2_fresh_preflight import run_fresh_preflight_for_prepared_launch
from scripts.m6a_v2_prepared_launch import build_prepared_launch_package
from scripts.m6a_v2_production_trust import *


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())


def make_trust(root, public_key):
    public_path = Path(root) / "config" / "trust" / "public.pem"
    public_path.parent.mkdir(parents=True)
    public_path.write_bytes(public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    value = {"schema_version": TRUST_SCHEMA, "verifier_type": "ed25519", "public_key_path": "config/trust/public.pem", "expected_public_key_fingerprint": __import__("hashlib").sha256(raw).hexdigest(), "expected_key_id": "ephemeral-key", "expected_issuer": "ephemeral-issuer", "accepted_authorization_policy_version": "ephemeral-policy", "verifier_identity": "ephemeral-verifier", "trust_domain": "ephemeral-domain", "signing_domain_hex": ED25519_DOMAIN.hex()}
    value["config_digest"] = digest(value)
    config = Path(root) / "config" / "trust.json"
    write_json(config, value)
    return config, value


class ProductionTrustTests(unittest.TestCase):
    def test_repository_pinned_public_trust(self):
        config = PROJECT_ROOT / "config" / "m6a_v2" / "production_authorization_trust.json"
        value = load_production_authorization_trust_config(config)
        verifier = build_production_authorization_verifier_from_config(config)
        self.assertEqual(value["expected_public_key_fingerprint"], "327b50d78e9f965ce7e8a10ed12bb14483ca7120325add9dbfd6d86c22f50ef4")
        self.assertEqual(verifier.public_key_fingerprint, value["expected_public_key_fingerprint"])

    def test_unsigned_request_roundtrip_readiness_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = Ed25519PrivateKey.generate()
            config, _ = make_trust(root, private.public_key())
            with patch("scripts.m6a_v2_execution_safety.PILOT_ROOT", root / "pilot"):
                package_path, package = build_prepared_launch_package(head="h", branch="main", attempt_id="request1", package_root=root / "control")
                run_fresh_preflight_for_prepared_launch(package_path)
                now = datetime.now(timezone.utc).replace(microsecond=0)
                request_path = authoritative_signing_request_path(package_path)
                request = export_execution_authorization_signing_request(package_path, package["preflight_report_path"], config, request_path, repository_root=root, issued_at_utc=now.isoformat(), expires_at_utc=(now + timedelta(minutes=2)).isoformat(), nonce="fixed-test-nonce")
                payload_bytes = authorization_canonical_payload_bytes(request["authorization_payload"])
                self.assertEqual(__import__("base64").b64decode(request["signed_message_base64"]), ED25519_DOMAIN + payload_bytes)
                loaded=load_execution_authorization_signing_request(request_path, package_path=package_path, preflight_path=package["preflight_report_path"], trust_config_path=config, repository_root=root);self.assertTrue(loaded["signature_absent"]);self.assertFalse(loaded["signature_present"]);self.assertFalse(loaded["authorization_verified"])
                request_path.unlink()
                readiness = run_production_authorization_readiness(package_path, package["preflight_report_path"], config, repository_root=root)
                self.assertEqual({key: readiness[key] for key in ("signature_present", "authorization_verified", "execution_authorized", "attempt_materialized", "process_launched")}, {key: False for key in ("signature_present", "authorization_verified", "execution_authorized", "attempt_materialized", "process_launched")})
                repeated=run_production_authorization_readiness(package_path,package["preflight_report_path"],config,repository_root=root);self.assertEqual(repeated["signing_request_digest"],readiness["signing_request_digest"])
                with self.assertRaises(ValueError):run_production_authorization_readiness(package_path,package["preflight_report_path"],config,root/'wrong.json',repository_root=root)
                with self.assertRaises(ValueError): load_execution_authorization_signing_request(request_path, package_path=package_path, preflight_path=package["preflight_report_path"], trust_config_path=config, repository_root=root, now=now + timedelta(minutes=20))
                valid_request = json.loads(request_path.read_text()); tampered = dict(valid_request); tampered["nonce"] = "tampered"; write_json(request_path, tampered)
                with self.assertRaises(ValueError): load_execution_authorization_signing_request(request_path, package_path=package_path, preflight_path=package["preflight_report_path"], trust_config_path=config, repository_root=root)
                write_json(request_path, valid_request)
                Path(package["prospective_attempt_root"]).mkdir(parents=True)
                with self.assertRaises(ValueError): load_execution_authorization_signing_request(request_path, package_path=package_path, preflight_path=package["preflight_report_path"], trust_config_path=config, repository_root=root)

    def test_trust_config_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); config, original = make_trust(root, Ed25519PrivateKey.generate().public_key())
            cases = []
            missing = dict(original); missing["public_key_path"] = "config/trust/missing.pem"; cases.append(("missing", missing))
            absolute = dict(original); absolute["public_key_path"] = str((root / "config" / "trust" / "public.pem").resolve()); cases.append(("absolute", absolute))
            traversal = dict(original); traversal["public_key_path"] = "../outside.pem"; cases.append(("traversal", traversal))
            fingerprint = dict(original); fingerprint["expected_public_key_fingerprint"] = "0" * 64; cases.append(("fingerprint", fingerprint))
            key_id = dict(original); key_id["expected_key_id"] = "PLACEHOLDER"; cases.append(("key_id", key_id))
            placeholder = dict(original); placeholder["expected_issuer"] = "PLACEHOLDER"; cases.append(("placeholder", placeholder))
            private_field = dict(original); private_field["private_key_path"] = "forbidden"; cases.append(("private", private_field))
            for name, value in cases:
                with self.subTest(name=name):
                    value.pop("config_digest", None); value["config_digest"] = digest(value); write_json(config, value)
                    with self.assertRaises(ValueError): load_production_authorization_trust_config(config, repository_root=root)
            malformed = root / "config" / "trust" / "public.pem"; malformed.write_text("not a key")
            write_json(config, original)
            with self.assertRaises(ValueError): build_production_authorization_verifier_from_config(config, repository_root=root)
            rsa = generate_private_key(public_exponent=65537, key_size=2048).public_key(); malformed.write_bytes(rsa.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
            with self.assertRaises(ValueError): build_production_authorization_verifier_from_config(config, repository_root=root)
