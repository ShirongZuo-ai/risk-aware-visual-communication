# M6-A v2 local research-pilot runbook

Status: attempt-002 and disposable smoke-001 are permanently `failed_process`
and must not be reused. Smoke-001 verified v4 controller discovery and normal
non-timeout process termination, then failed before snapshot 0. Failure status
v2 and the offline state-reader correction require a new package plus separate
smoke-002 launch approval.

## Purpose and boundary

The research runner changes only the local execution-authority mechanism. It
reloads the existing frozen prepared package and reuses its world, controller,
runtime configuration, argv, manifest, lock, expected outputs, process capture,
runtime validation, 32-case aggregate, joint validation, and final marker.

Research mode does not read or require a production private key, signing
request, detached signature, authorization artifact, verified receipt, or
production consumption record. It does not alter the production-audited path.
A zero process exit is only a process success; the command reports final success
only after the existing scientific completion and joint validators pass.

## Separately approved disposable diagnostic smoke

After preparing `m6a-research-lifecycle-smoke-002` from the exact executing HEAD,
the one permitted diagnostic command from the repository root is:

```powershell
.\.venv\Scripts\python.exe -m scripts.m6a_v2_research_pilot run `
  --package results\m6a_v2_control\prepared\m6a-research-lifecycle-smoke-002\package.json `
  --confirm-attempt m6a-research-lifecycle-smoke-002
```

Do not run this command without explicit approval to create that disposable
attempt and start Webots exactly once. Never point it at attempt-001 or
attempt-002. A new package must be produced by the authoritative package
producer; the JSON must not be copied or edited.

## Fail-closed lifecycle

1. Reload and validate the canonical prepared package and every bound input.
2. Require a clean tracked tree and bind the package HEAD to the executing HEAD.
   Exact equality is accepted. For the already-prepared attempt-002 only, one
   direct descendant commit is accepted when every changed path is in the fixed
   research-runner/tests/documentation allowlist. This bridge is persisted in
   the research context and does not rewrite the frozen package.
3. Require the exact attempt confirmation and authoritative prepared path.
4. Exclusively create ownership and persist the canonical research context.
5. Persist an immutable launch claim before process start. Once claimed, no
   automatic retry is permitted, including when start outcome is uncertain.
6. Run the package-declared shell-free process once, capture stdout/stderr and
   canonical timing, timeout, termination, and return-code evidence.
7. Preserve nonzero or timed-out execution as an immutable failed terminal.
8. After a clean exit, run the existing runtime, aggregate, joint, and final
   validators. Recovery from complete process evidence never launches again.

Any arbitrary existing root, path escape, identity/head drift, tampering,
partial/conflicting evidence, production consumption, or unsupported terminal
state fails closed. There is no cleanup/retry command: an indeterminate claimed
attempt must be investigated and replaced by a newly prepared, separately
approved attempt identity.
