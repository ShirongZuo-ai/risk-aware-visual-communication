# M6-A v2 execution authorization signature protocol

The repository can verify an externally signed Ed25519 authorization, but it does not generate, store, or possess the production private key.

The authorization signer signs the fixed domain `RAVC-M6A-V2-EXECUTION-AUTHORIZATION` (including its terminating zero byte) followed by canonical UTF-8 JSON for the authorization payload. Canonical JSON uses sorted keys, compact separators, and a trailing newline. The authenticator envelope, `payload_digest`, and `canonical_artifact_digest` are derived packaging fields and are excluded from the signed bytes; all launch identity, binding digests, root, issuer, validity interval, policy, and nonce fields are included.

The detached authenticator envelope uses `scheme=ed25519`, an externally agreed `key_id`, and a standard Base64 64-byte signature. An optional claimed fingerprint is checked for consistency but is not trusted. The verifier loads an explicitly supplied raw, PEM, or DER Ed25519 public key, converts it to the canonical raw 32-byte form, and requires an exact match to the configured lowercase SHA-256 fingerprint.

Production provisioning is an external manual operation: manage the private key offline, provision the public key and pinned fingerprint through the caller's trusted configuration channel, and supply the expected key ID, issuer, policy version, verifier identity, and trust domain. With any value absent or marked as a placeholder, verification fails closed. Verification alone does not create an execution context, materialize an attempt, consume authorization, launch a process, or write a final marker.

The production public trust root is now pinned by `config/m6a_v2/production_authorization_trust.json`. It references only the repository-relative public file `config/m6a_v2/trust/m6a_authority_public.pem`; the canonical raw-key SHA-256 fingerprint is `327b50d78e9f965ce7e8a10ed12bb14483ca7120325add9dbfd6d86c22f50ef4`. No private signing key is present in or accessible through this configuration.

The repository may export an immutable unsigned signing request after reloading the prepared package, fresh preflight, and pinned trust configuration. The request contains the canonical authorization payload and Base64-encoded exact signed-message bytes, but explicitly records `signature_absent=true`, `execution_authorized=false`, and `materialization_allowed=false`. It is not an authorization artifact or receipt. A repository-external offline signing program must sign the exported exact-message bytes; only a separately imported signed artifact may later enter verification-only processing.

Package-bound preflight renewal preserves immutable history: a still-current report is reused, while an expired report is first validated at its original checked time and moved unchanged into the package workspace's `fresh_preflight_history` before the canonical current path is recreated. Tampered or conflicting evidence fails closed. The authoritative unsigned-request path is deterministically `<preflight_workspace_root>/unsigned_authorization_signing_request.json`; callers cannot redirect the production readiness entrypoint. The request additionally records `signature_present=false` and `authorization_verified=false`, while readiness records that no attempt or process exists.

## Offline detached-signature return contract

The operator input is the current package-bound `unsigned_authorization_signing_request.json`. Before signing, the operator must confirm that both its `expires_at_utc` and the bound fresh-preflight `valid_until_utc` are still in the future. An expired request is historical evidence and must never be signed or relabeled as current.

The only bytes to sign are the raw bytes obtained by standard Base64-decoding `signed_message_base64`. The approved offline signer produces a 64-byte Ed25519 detached signature over those exact bytes. It must not reserialize `authorization_payload`, sign `payload_digest` or `signed_message_sha256` as text, or sign the Base64 string itself. Every request has a distinct nonce and must be signed separately.

The operator returns one canonical JSON file named `detached_authorization_signature.json` to the prepared package workspace. Its exact schema is:

```json
{
  "authorization_id": "<copy from unsigned request>",
  "canonical_bundle_digest": "<SHA-256 of canonical JSON for all other fields>",
  "execution_authorized": false,
  "key_id": "<copy from unsigned request>",
  "materialization_allowed": false,
  "schema_version": "m6a-v2-detached-authorization-signature-v1",
  "signature_base64": "<standard Base64 encoding of the 64-byte detached signature>",
  "signature_present": true,
  "signature_scheme": "ed25519",
  "signed_at_utc": "<timezone-aware ISO 8601 time within the request interval>",
  "signed_message_sha256": "<copy from unsigned request>",
  "trust_verified": false,
  "unsigned_request_digest": "<copy canonical_request_digest from unsigned request>"
}
```

Canonical JSON uses sorted keys, compact `,` and `:` separators, ASCII escaping, and one trailing newline. `canonical_bundle_digest` is lower-case SHA-256 over the same canonical object before that digest field is added, without a trailing newline in the digest input. The private key and any key password must remain outside the repository, Codex, logs, and chat. The production repository provides no signing operation and treats bundle metadata as untrusted until the pinned public key verifies the signature.

The authoritative follow-on paths are all derived from the prepared package workspace, never from caller string concatenation:

- `detached_authorization_signature.json`
- `execution_authorization_artifact.json`
- `verified_authorization_receipt.json`

`run_detached_authorization_verification_only(...)` reloads the current request, detached bundle, package, fresh preflight, and pinned public trust. It then imports the signature into the existing authenticator envelope, persists and reloads the existing unverified authorization-artifact schema, calls `verify_execution_authorization(...)`, and persists and reloads the verified receipt. A successful result means only `trust_verified=true`, `authorization_verified=true`, and `receipt_valid=true`. It deliberately returns `execution_context_created=false`, `materialization_allowed=false`, `attempt_materialized=false`, `ownership_acquired=false`, `process_launched=false`, `authorization_consumed=false`, and `final_marker_written=false`.

## Short-validity operating sequence

The effective signing/import deadline is the earlier of the fresh-preflight `valid_until_utc` (normally about five minutes after refresh) and request `expires_at_utc`. The intended sequence is: refresh package-bound preflight, export the current unsigned request, stop repository-side work, sign the decoded exact message offline, place the bundle at its authoritative workspace path, and immediately run verification-only processing. Do not run the full test suite between request export and signature import. Verification does not relax the independent requirement for another current fresh preflight before any future materialization step.

The exact production commands, repository-external signing handoff, and fail-closed time-window procedure are recorded in [the operator runbook](m6a_v2_production_authorization_operator_runbook.md). Repository CLI commands expose only `refresh-export` and `verify-only`; they have no private-key, output-root, materialization, or process-launch options.
