# M6-A v2 production authorization operator runbook

Commands A through C perform public-evidence preparation and signature verification only. Command D creates one durable owned attempt and stops before launch. Command E is the separately approved one-shot production launch/recovery boundary. Command F retires only a superseded, evidence-free pre-spawn legacy attempt. Never run E or F without explicit approval for the named package.

## Fixed production inputs

- Repository: `C:\Users\ROG\Documents\risk-aware-visual-communication`
- Prepared package: `results\m6a_v2_control\prepared\m6a-prod-pilot-001\package.json`
- Production public trust: `config\m6a_v2\production_authorization_trust.json`
- Expected identity: `m6a-prod-pilot-001` / `m6ac31cb4657ae813d7e35387acc28583fd` / `m6a_pilot_s1_seed600100`
- Expected public-key fingerprint: `327b50d78e9f965ce7e8a10ed12bb14483ca7120325add9dbfd6d86c22f50ef4`

The repository commands accept no private-key options. `--package` may select only an existing `results\m6a_v2_control\prepared\<attempt-id>\package.json`; attempt roots and evidence paths are always derived from that package.

## T0 — Command A: refresh and export

From the repository root, run exactly:

```powershell
Set-Location 'C:\Users\ROG\Documents\risk-aware-visual-communication'
.\.venv\Scripts\python.exe -m scripts.m6a_v2_authorization_operator refresh-export
```

Before renewing a request, the command treats any authoritative detached bundle, authorization artifact, and verified receipt as one verification generation. It reloads the generation's retained request and preflight, repeats pinned-public-key verification at the receipt's recorded verification time, archives the three exact files plus a canonical manifest, and releases the three authoritative paths only after the complete archive reloads successfully. It then validates and immutably archives an expired request, renews package-bound preflight evidence, exports/reloads the current unsigned request, and prints:

- `unsigned_request_path`
- `authorization_id`
- `fresh_preflight_valid_until_utc`
- `request_expires_at_utc`
- `effective_deadline_utc`
- `archived_verification_generation`

It stops with `signature_present=false`, `execution_authorized=false`, and `stop_after_export=true`. Copy these printed values into the operator record. Do not run tests, Git commands, or further Codex analysis before Command C.

Expired requests are archived under `unsigned_authorization_request_history/request.<canonical_request_digest>.json`. The short digest-only filename avoids Windows legacy path-length failures while remaining deterministic and content-addressed. Archival validates the original canonical bytes and package/preflight/trust binding at the request's issue time; it never relaxes freshness checks for a current request. Repeated calls recover safely if an identical archive already exists, reject conflicting archive bytes, and can resume after either the request move or preflight renewal completed before a crash.

Verified generations are archived under `authorization_generation_history/g.<first-16-hex-of-request-digest>/`. Each directory contains exact-byte `bundle.json`, `artifact.json`, and `receipt.json` files plus `manifest.json`, which records the full request digest, authorization ID, signed-message digest, trust identity, per-file SHA-256, and canonical digests. The short directory is only a locator: the full digest in the validated manifest resolves collisions fail closed. Archive files are copied and revalidated before the manifest is written; source paths are released only after the complete manifest and all archived evidence reload successfully. An interrupted copy can resume with intact sources, and an interrupted source release can resume from an already-complete identical archive. Partial sources without a complete archive, changed bytes, symlinks, path escape, or conflicting history are terminal and do not produce a new request.

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

## Command D: materialize-only

Run this command only after Command C succeeds and while the preflight, request, authorization artifact, and receipt remain current:

```powershell
Set-Location 'C:\Users\ROG\Documents\risk-aware-visual-communication'
.\.venv\Scripts\python.exe -m scripts.m6a_v2_authorization_operator materialize-only
```

The command derives every path from the prepared package and reloads the package, current preflight, unsigned request, detached bundle, authorization artifact, and persisted receipt. It repeats pinned-public-key verification and requires the persisted receipt to match that fresh verification before constructing `ExternallyValidatedExecutionContext`. It then calls the existing `materialize_authorized_attempt(..., mode="production")`, atomically creates the attempt root and ownership marker once, persists `.m6a_v2_owned_context.json`, reloads and rebinds that artifact to the package/receipt/ownership, and stops.

Success must report:

```text
trust_verified=true
receipt_valid=true
execution_context_created=true
materialization_allowed=true
attempt_materialized=true
ownership_acquired=true
process_launched=false
authorization_consumed=false
final_marker_written=false
stop_before_launch=true
```

The command rejects a reused root, second materialization, arbitrary context, test receipt, stale or tampered evidence, identity/path drift, or any pre-existing ownership, consumption, process, or final-marker evidence. It accepts only the authoritative prepared-package selector; it never accepts an attempt root or private-key parameter.

## Command E: run-pilot

Run only after Command D succeeds for a package whose recorded HEAD equals the current `git rev-parse HEAD`:

```powershell
.\.venv\Scripts\python.exe -m scripts.m6a_v2_authorization_operator run-pilot `
  --package results\m6a_v2_control\prepared\m6a-prod-pilot-002\package.json
```

The operator reloads the durable owned context, package, receipt, and ownership. With no consumption or process evidence it invokes `ProductionOwnedProcessRunner` exactly once. The runner revalidates launch-spec v3 and input hashes, uses `OwnedPopenBackend.start(...)`, waits once, and persists the declared stdout/stderr. The existing launch boundary then writes single-use consumption and process evidence. A zero-exit, non-timeout process enters the existing B5 completion and finalization path.

Recovery rules are fail closed: a complete consumption/process pair skips the runner and resumes completion/finalization; a completed terminal returns idempotently; exactly one of consumption/process rejects retry; retired or failed terminal evidence rejects launch. A nonzero exit or timeout remains consumed process evidence and is never retried automatically.

## Command F: retire-pre-spawn

For the superseded attempt-001, run only after separately checking and approving the unchanged old package and ownership evidence:

```powershell
.\.venv\Scripts\python.exe -m scripts.m6a_v2_authorization_operator retire-pre-spawn `
  --package results\m6a_v2_control\prepared\m6a-prod-pilot-001\package.json
```

The command requires the package HEAD to differ from the current HEAD, ownership state `owned_pre_spawn`, and absence of durable context, consumption, process/runtime/completion evidence, final marker, and unknown attempt-root content. It writes only immutable `.m6a_v2_ownership_terminal.json` with state `retired_pre_spawn` and reason `package_head_superseded_before_launch`. It never modifies the original ownership marker, consumes authorization, creates a success marker, or reports a scientific result.

## Preparing the replacement attempt-002

After attempt-001 retirement is separately approved and completed, create the new package from the then-current committed HEAD:

```powershell
$head = (& 'C:\Program Files\Git\cmd\git.exe' rev-parse HEAD).Trim()
.\.venv\Scripts\python.exe -c "from scripts.m6a_v2_prepared_launch import build_prepared_launch_package; print(build_prepared_launch_package(head='$head', branch='main', attempt_id='m6a-prod-pilot-002')[0])"
```

Run Commands A, B, C, and D for the `m6a-prod-pilot-002` package, passing the same `--package` path to repository commands. Only after all four gates succeed and a separate launch approval is recorded should Command E be run. Never copy authorization, receipt, owned context, or ownership from attempt-001.

## Time-window rule

| Time | Required action |
|---|---|
| T0 | Run Command A. |
| Immediately after T0 | Record both deadlines and use `effective_deadline_utc`. |
| As quickly as possible | Run Command B outside the repository. |
| Immediately after signing | Return only the bundle and run Command C. |
| Immediately after verified receipt | If explicitly authorized, run Command D once and stop before launch. |

The hard deadline is:

```text
min(fresh_preflight.valid_until_utc, unsigned_request.expires_at_utc)
```

If the deadline passes, do not import or verify the old signature. Keep old evidence immutable, rerun Command A, and sign the newly issued request. A signature must never be replayed onto a new request.

## Failure handling

- Any canonical digest, identity, trust, key ID, signature length, signature, request, preflight, expiry, path, or existing-attempt failure is terminal for that request.
- Do not edit request, bundle, authorization artifact, or receipt JSON.
- Do not delete or overwrite prepared-workspace evidence to force a retry.
- Do not proceed beyond Command D to Webots, consumption, completion, or finalization from this runbook.
