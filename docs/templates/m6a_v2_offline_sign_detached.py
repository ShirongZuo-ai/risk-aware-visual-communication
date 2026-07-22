"""Operator-only template: copy outside the repository before use.

This file is never called by repository runtime code.  It reads an encrypted
Ed25519 private key only when the operator explicitly runs the copied file.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def sign_request(*, repository_root, request_path, private_key_path, output_path, password_provider=getpass.getpass):
    repository_root = Path(repository_root).resolve()
    sys.path.insert(0, str(repository_root))
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from scripts.m6a_trusted_artifacts import digest
    from scripts.m6a_v2_detached_authorization import (
        build_detached_signature_bundle,
        persist_detached_signature_bundle,
    )

    request_path = Path(request_path).resolve()
    raw = request_path.read_bytes()
    request = json.loads(raw)
    canonical = (json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
    if raw != canonical:
        raise ValueError("noncanonical unsigned request")
    if request.get("canonical_request_digest") != digest(
        {key: item for key, item in request.items() if key != "canonical_request_digest"}
    ):
        raise ValueError("unsigned request digest")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if datetime.fromisoformat(request["expires_at_utc"]) <= now:
        raise ValueError("refusing to sign expired request")
    exact_message = base64.b64decode(request["signed_message_base64"], validate=True)
    if __import__("hashlib").sha256(exact_message).hexdigest() != request["signed_message_sha256"]:
        raise ValueError("signed-message digest")

    password_text = password_provider("Production Ed25519 private-key password: ")
    password = password_text.encode("utf-8") if password_text else None
    private_key = load_pem_private_key(Path(private_key_path).read_bytes(), password=password)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("private key is not Ed25519")
    signature = private_key.sign(exact_message)
    bundle = build_detached_signature_bundle(
        request,
        signature_base64=base64.b64encode(signature).decode("ascii"),
        signed_at_utc=now.isoformat(),
        now=now,
    )
    persisted = persist_detached_signature_bundle(
        output_path, bundle, request=request, now=now
    )
    return {
        "output_path": str(Path(output_path).resolve()),
        "authorization_id": persisted["authorization_id"],
        "unsigned_request_digest": persisted["unsigned_request_digest"],
        "signed_message_sha256": persisted["signed_message_sha256"],
        "canonical_bundle_digest": persisted["canonical_bundle_digest"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = sign_request(
        repository_root=args.repository_root,
        request_path=args.request,
        private_key_path=args.private_key,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
