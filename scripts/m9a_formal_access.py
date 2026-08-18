"""One-shot formal access gate. This module never reads formal logs itself."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

AUTH_RE = re.compile(r"^M9A-[A-Z0-9]{8,64}$")

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()

def read_state(ledger: Path) -> str:
    if not ledger.exists(): return "sealed"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    return json.loads(lines[-1])["new_state"] if lines else "sealed"

def authorize_once(*, formal_unlock: bool, authorization_id: str, actor: str, ledger: Path, expected_digests: dict[str, str], artifact_paths: dict[str, Path]) -> None:
    if not formal_unlock: raise PermissionError("formal access requires --formal-unlock")
    if not AUTH_RE.fullmatch(authorization_id): raise PermissionError("invalid authorization ID")
    if read_state(ledger) != "sealed": raise PermissionError("formal authorization is one-shot")
    actual = {name: sha256_file(path) for name, path in artifact_paths.items()}
    if actual != expected_digests: raise PermissionError("formal digest mismatch")
    entry = {"authorization_id": authorization_id, "actor": actor, "command": "authorize", "prior_state": "sealed", "new_state": "authorized_once", "utc": datetime.now(timezone.utc).isoformat(), "digests": actual}
    ledger.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n"); handle.flush(); os.fsync(handle.fileno())

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-unlock", action="store_true")
    parser.add_argument("--authorization-id", required=True)
    parser.parse_args()
    raise SystemExit("Library-only I1 guard: caller must supply frozen artifact paths/digests")

if __name__ == "__main__": main()

