"""Canonical identity and evidence helpers for M8 proxy qualification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from scripts.m6a_trusted_artifacts import digest


IDENTITY_SCHEMA = "m8-proxy-identity-v1"
IMAGE_SHAPE = (120, 160, 3)
FIELD_SHAPE = IMAGE_SHAPE[:2]
QUALIFICATION_STATUS = "unvalidated_candidate"


@dataclass(frozen=True)
class ProxyIdentity:
    schema_version: str
    identity_id: str
    split: str
    scene: str
    episode_id: str
    seed: int
    snapshot_id: str
    reconstruction_id: str

    @classmethod
    def create(
        cls,
        *,
        identity_id: str,
        split: str,
        scene: str,
        episode_id: str,
        seed: int,
        snapshot_id: str,
        reconstruction_id: str,
    ) -> "ProxyIdentity":
        value = cls(
            IDENTITY_SCHEMA,
            identity_id,
            split,
            scene,
            episode_id,
            seed,
            snapshot_id,
            reconstruction_id,
        )
        value.validate()
        return value

    def validate(self) -> None:
        if self.schema_version != IDENTITY_SCHEMA:
            raise ValueError("invalid M8 proxy identity schema")
        strings = (
            self.identity_id,
            self.split,
            self.scene,
            self.episode_id,
            self.snapshot_id,
            self.reconstruction_id,
        )
        if any(not isinstance(value, str) or not value.strip() for value in strings):
            raise ValueError("M8 proxy identity fields must be non-empty strings")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("M8 proxy seed must be a non-negative integer")

    def canonical(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @property
    def canonical_digest(self) -> str:
        return digest(self.canonical())


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize one canonical JSON object as UTF-8 with a single LF."""

    return (
        json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def require_rgb(image: np.ndarray, *, name: str) -> np.ndarray:
    if not isinstance(image, np.ndarray) or image.shape != IMAGE_SHAPE:
        raise ValueError(f"{name} must have shape {IMAGE_SHAPE}")
    if image.dtype != np.uint8:
        raise ValueError(f"{name} must have dtype uint8")
    return image


def require_field(
    field: np.ndarray,
    *,
    name: str,
    boolean: bool = False,
) -> np.ndarray:
    if not isinstance(field, np.ndarray) or field.shape != FIELD_SHAPE:
        raise ValueError(f"{name} must have shape {FIELD_SHAPE}")
    if boolean:
        if field.dtype != np.bool_:
            raise ValueError(f"{name} must have dtype bool")
        return field
    if not np.issubdtype(field.dtype, np.number):
        raise ValueError(f"{name} must be numeric")
    value = field.astype(np.float64, copy=False)
    if not np.all(np.isfinite(value)) or np.any(value < 0.0) or np.any(value > 1.0):
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return value


def array_digest(value: np.ndarray) -> str:
    if not isinstance(value, np.ndarray):
        raise ValueError("array digest requires ndarray input")
    payload = {
        "dtype": str(value.dtype),
        "shape": list(value.shape),
        "bytes_sha256": hashlib.sha256(value.tobytes(order="C")).hexdigest(),
    }
    return digest(payload)


def validate_identity_binding(
    observed: Mapping[str, Any],
    expected: ProxyIdentity | None,
) -> ProxyIdentity:
    try:
        identity = ProxyIdentity(**dict(observed))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid M8 proxy evidence identity") from exc
    identity.validate()
    if expected is not None:
        expected.validate()
        if identity != expected:
            raise ValueError("M8 proxy evidence identity mismatch")
    return identity


def validate_canonical_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_schema: str,
    expected_identity: ProxyIdentity | None = None,
    expected_evaluator_input_usage: int = 0,
) -> dict[str, Any]:
    value = dict(evidence)
    supplied = value.pop("canonical_digest", None)
    if value.get("schema_version") != expected_schema:
        raise ValueError("unexpected M8 proxy evidence schema")
    if not isinstance(supplied, str) or supplied != digest(value):
        raise ValueError("invalid M8 proxy canonical digest")
    identity = validate_identity_binding(value.get("identity", {}), expected_identity)
    if value.get("identity_digest") != identity.canonical_digest:
        raise ValueError("invalid M8 proxy identity digest")
    if value.get("actual_future_usage") != 0:
        raise ValueError("unsafe M8 future-data usage")
    if value.get("evaluator_input_usage") != expected_evaluator_input_usage:
        raise ValueError("invalid M8 evaluator-input usage")
    for field in ("fallback", "replacement"):
        if value.get(field) is not False:
            raise ValueError("unsafe M8 proxy evidence")
    value["canonical_digest"] = supplied
    return value


def persist_canonical_evidence(
    path: Path,
    evidence: Mapping[str, Any],
    *,
    validator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> None:
    validated = dict(validator(evidence))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite M8 evidence: {path}")
    path.write_bytes(canonical_json_bytes(validated))


def load_canonical_evidence(
    path: Path,
    *,
    validator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    path = Path(path)
    raw = path.read_bytes()
    if b"\r\n" in raw or not raw.endswith(b"\n"):
        raise ValueError("M8 evidence is not canonical LF JSON")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid M8 evidence JSON") from exc
    validated = dict(validator(value))
    if raw != canonical_json_bytes(validated):
        raise ValueError("non-canonical M8 evidence serialization")
    return validated


def sequence_diagnostics(scores: Sequence[float]) -> dict[str, float | int | bool]:
    """Synthetic-only range and monotonicity diagnostics; not calibration gates."""

    values = np.asarray(tuple(scores), dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("diagnostic scores must contain at least two finite values")
    if np.any(values < 0.0) or np.any(values > 1.0):
        raise ValueError("diagnostic scores must be in [0, 1]")
    ranks = np.empty(values.size, dtype=np.float64)
    order = np.argsort(values, kind="mergesort")
    index = 0
    while index < values.size:
        end = index + 1
        while end < values.size and values[order[end]] == values[order[index]]:
            end += 1
        ranks[order[index:end]] = (index + end - 1) / 2.0
        index = end
    expected = np.arange(values.size, dtype=np.float64)
    if np.all(ranks == ranks[0]):
        spearman = 0.0
    else:
        spearman = float(np.corrcoef(expected, ranks)[0, 1])
    return {
        "count": int(values.size),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "range": float(values.max() - values.min()),
        "endpoint_fraction": float(np.mean((values == 0.0) | (values == 1.0))),
        "nondecreasing": bool(np.all(np.diff(values) >= -1e-12)),
        "spearman_with_quality_order": spearman,
    }


def require_unit_interval(value: Any, *, name: str, allow_none: bool = False) -> float | None:
    if allow_none and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return result
