# M6-A v2 production authorization operator runbook

This runbook performs public-evidence preparation and signature verification only. It does not create an execution context, materialize an attempt, acquire ownership, launch Webots or another process, consume authorization, or write a final marker.

## Fixed production inputs

- Repository: `C:\Users\ROG\Documents\risk-aware-visual-communication`
- Prepared package: `results\m6a_v2_control\prepared\m6a-prod-pilot-001\package.json`
- Production public trust: `config\m6a_v2\production_authorization_trust.json`
- Expected identity: `m6a-prod-pilot-001` / `m6ac31cb4657ae813d7e35387acc28583fd` / `m6a_pilot_s1_seed600100`
- Expected public-key fingerprint: `327b50d78e9f965ce7e8a10ed12bb14483ca7120325add9dbfd6d86c22f50ef4`

The repository commands accept no path or private-key options. Production paths are derived from the fixed prepared package and repository root.

## T0 — Command A: refresh and export

From the repository root, run exactly:

```powershell
Set-Location 'C:\Users\ROG\Documents\risk-aware-visual-communication'
.\.venv\Scripts\python.exe -m scripts.m6a_v2_authorization_operator refresh-export
```

The command reloads the prepared package, validates and immutably archives an expired request, renews package-bound preflight evidence, exports/reloads the current unsigned request, and prints:

- `unsigned_request_path`
- `authorization_id`
- `fresh_preflight_valid_until_utc`
- `request_expires_at_utc`
- `effective_deadline_utc`

It stops with `signature_present=false`, `execution_authorized=false`, and `stop_after_export=true`. Copy these printed values into the operator record. Do not run tests, Git commands, or further Codex analysis before Command C.

Expired requests are archived under `unsigned_authorization_request_history/request.<canonical_request_digest>.json`. The short digest-only filename avoids Windows legacy path-length failures while remaining deterministic and content-addressed. Archival validates the original canonical bytes and package/preflight/trust binding at the request's issue time; it never relaxes freshness checks for a current request. Repeated calls recover safely if an identical archive already exists, reject conflicting archive bytes, and can resume after either the request move or preflight renewal completed before a crash.

## Immediately after T0 — Command B: repository-external signing

This is the only command that reads the production private key. The operator, not repository automation or Codex, runs it. First copy the public template and current unsigned request into the secure directory:

```powershell
$repo = 'C:\Users\ROG\Documents\risk-aware-visual-communication'
$secure = 'C:\Users\ROG\Secure\ravc-m6a-authority'
$workspace = Join-Path $repo 'results\m6a_v2_control\prepared\m6a-prod-pilot-001'

Copy-Item -LiteralPath (Join-Path $repo 'docs\templates\m6a_v2_offline_sign_detached.py') -Destination (Join-Path $secure 'm6a_v2_offline_sign_detached.py')
Copy-Item -LiteralPath (Join-Path $workspace 'unsigned_authorization_signing_request.json') -Destination (Join-Path $secure 'unsigned_authorization_signing_request.json')
Set-Location $secure
```

Then sign. This command interactively prompts for the encrypted PEM password; no password argument or environment variable is supported:

```powershell
& (Join-Path $repo '.venv\Scripts\python.exe') .\m6a_v2_offline_sign_detached.py `
  --repository-root $repo `
  --request .\unsigned_authorization_signing_request.json `
  --private-key .\m6a_authority_private.pem `
  --output .\detached_authorization_signature.json
```

The external template signs exactly:

```text
Base64Decode(request["signed_message_base64"])
```

It does not sign the Base64 text, reserialized payload JSON, payload digest, signed-message SHA-256 text, or request digest. It calls the public `build_detached_signature_bundle(...)` and `persist_detached_signature_bundle(...)` helpers to produce the canonical bundle and digest.

Copy only the completed public bundle back to its authoritative prepared-workspace path. Fail if an old bundle is present; never overwrite it:

```powershell
$bundleTarget = Join-Path $workspace 'detached_authorization_signature.json'
if (Test-Path -LiteralPath $bundleTarget) { throw "Authoritative detached bundle already exists: $bundleTarget" }
Copy-Item -LiteralPath .\detached_authorization_signature.json -Destination $bundleTarget
```

The private key, password, and signer working files remain outside the repository. The only files copied into the secure directory are the public template and current unsigned request; the only file returned is `detached_authorization_signature.json`.

## Immediately after signing — Command C: verification-only

Return to the repository and run exactly:

```powershell
Set-Location 'C:\Users\ROG\Documents\risk-aware-visual-communication'
.\.venv\Scripts\python.exe -m scripts.m6a_v2_authorization_operator verify-only
```

The command reloads the request and bundle, revalidates the package, preflight, and pinned public trust, persists/reloads the unverified authorization artifact, verifies the exact signed bytes, and persists/reloads the receipt. Success must report:

```text
trust_verified=true
authorization_verified=true
receipt_valid=true
execution_context_created=false
materialization_allowed=false
attempt_materialized=false
ownership_acquired=false
process_launched=false
authorization_consumed=false
final_marker_written=false
```

Stop after this output. A verified receipt is not materialization permission.

## Time-window rule

| Time | Required action |
|---|---|
| T0 | Run Command A. |
| Immediately after T0 | Record both deadlines and use `effective_deadline_utc`. |
| As quickly as possible | Run Command B outside the repository. |
| Immediately after signing | Return only the bundle and run Command C. |

The hard deadline is:

```text
min(fresh_preflight.valid_until_utc, unsigned_request.expires_at_utc)
```

If the deadline passes, do not import or verify the old signature. Keep old evidence immutable, rerun Command A, and sign the newly issued request. A signature must never be replayed onto a new request.

## Failure handling

- Any canonical digest, identity, trust, key ID, signature length, signature, request, preflight, expiry, path, or existing-attempt failure is terminal for that request.
- Do not edit request, bundle, authorization artifact, or receipt JSON.
- Do not delete or overwrite prepared-workspace evidence to force a retry.
- Do not proceed to materialization, ownership, Webots, consumption, or finalization from this runbook.
