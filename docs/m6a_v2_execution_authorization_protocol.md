# M6-A v2 execution authorization signature protocol

The repository can verify an externally signed Ed25519 authorization, but it does not generate, store, or possess the production private key.

The authorization signer signs the fixed domain `RAVC-M6A-V2-EXECUTION-AUTHORIZATION` (including its terminating zero byte) followed by canonical UTF-8 JSON for the authorization payload. Canonical JSON uses sorted keys, compact separators, and a trailing newline. The authenticator envelope, `payload_digest`, and `canonical_artifact_digest` are derived packaging fields and are excluded from the signed bytes; all launch identity, binding digests, root, issuer, validity interval, policy, and nonce fields are included.

The detached authenticator envelope uses `scheme=ed25519`, an externally agreed `key_id`, and a standard Base64 64-byte signature. An optional claimed fingerprint is checked for consistency but is not trusted. The verifier loads an explicitly supplied raw, PEM, or DER Ed25519 public key, converts it to the canonical raw 32-byte form, and requires an exact match to the configured lowercase SHA-256 fingerprint.

Production provisioning is an external manual operation: manage the private key offline, provision the public key and pinned fingerprint through the caller's trusted configuration channel, and supply the expected key ID, issuer, policy version, verifier identity, and trust domain. With any value absent or marked as a placeholder, verification fails closed. Verification alone does not create an execution context, materialize an attempt, consume authorization, launch a process, or write a final marker.
