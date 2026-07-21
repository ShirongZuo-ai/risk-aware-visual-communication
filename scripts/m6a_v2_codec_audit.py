"""Offline-only, fail-closed M6-A v2 byte-fair 32-case codec audit.

Synthetic fixtures are permitted for tests; this module neither reads nor writes
pilot data and never invokes Webots.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib, math, tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from compression.tiled_jpeg import DEFAULT_M5_GRID, decode_tiles_to_rgb, encode_rgb_frame_to_tiles
from compression.tile_container import serialize_tiled_frame
from evaluation.image_quality import compute_error_metrics, compute_ssim
from scripts.m6a_dual_roi import CurrentState, ScheduleEvidence
from scripts.m6a_mask_generation import generate_command_conditioned_risk_mask, generate_state_only_risk_mask
from scripts.m6a_trusted_artifacts import M6AProjectionConfig, digest
from scripts.run_m6a_one_identity import load_v2_runtime_config


CODEC_VERSION = "m6a-v2-tiled-jpeg-byte-fair-v1"
METHODS = ("state_only_risk_roi", "command_conditioned_risk_roi")
BUDGET_ORDER = ("severe", "low", "medium", "high")


def _sha(payload: bytes) -> str: return hashlib.sha256(payload).hexdigest()

@dataclass(frozen=True)
class SnapshotCodecInput:
    snapshot_id: str; timestamp_s: float; image: np.ndarray; state: CurrentState; schedule: ScheduleEvidence; raw_image_sha256: str; source_digest: str; synthetic_fixture: bool = False

    @classmethod
    def create(cls, *, runtime_config: dict, snapshot_id: str, timestamp_s: float, image: np.ndarray, state: CurrentState, schedule: ScheduleEvidence, synthetic_fixture: bool = False, **forbidden):
        if forbidden: raise ValueError("unknown or prohibited SnapshotCodecInput field")
        load_v2_runtime_config(runtime_config)
        expected = next((item for item in runtime_config["snapshots"] if item["snapshot_id"] == snapshot_id), None)
        if expected is None or timestamp_s != expected["timestamp_s"] or not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.shape != (120, 160, 3) or not np.isfinite(image).all() or not isinstance(state, CurrentState) or not isinstance(schedule, ScheduleEvidence): raise ValueError("invalid frozen snapshot input")
        if schedule.available_time_s > timestamp_s or not schedule.segments: raise ValueError("unavailable predefined schedule")
        raw = image.tobytes(); source = digest({"snapshot_id": snapshot_id, "timestamp_s": timestamp_s, "state": asdict(state), "schedule": asdict(schedule), "raw_image_sha256": _sha(raw)})
        return cls(snapshot_id, timestamp_s, image.copy(), state, schedule, _sha(raw), source, synthetic_fixture)


@dataclass(frozen=True)
class MethodMaskEvidence:
    method: str; input_digest: str; projection_digest: str; mask_sha256: str; selected_pixel_count: int; selected_area_ratio: float; actual_future_usage: int; combined_usage: int; oracle_usage: int; fallback: int


def build_method_mask(runtime_config: dict, snapshot: SnapshotCodecInput, method: str) -> tuple[MethodMaskEvidence, tuple[float, ...]]:
    load_v2_runtime_config(runtime_config)
    if method not in tuple(runtime_config["methods"]) or tuple(runtime_config["methods"]) != METHODS: raise ValueError("unknown or unfrozen method")
    config = M6AProjectionConfig(**runtime_config["projection_config"]); config.validate()
    artifact = generate_state_only_risk_mask(snapshot.state, config) if method == METHODS[0] else generate_command_conditioned_risk_mask(snapshot.state, snapshot.schedule, config, timestamp_s=snapshot.timestamp_s)
    if artifact.method != method or artifact.predictor_config_digest != config.sha256() or any((artifact.actual_future_usage, artifact.combined_usage, artifact.raw_external_mask_usage, artifact.fallback, artifact.replacement)) or artifact.empty: raise ValueError("unsafe or unusable method mask")
    evidence = MethodMaskEvidence(method, artifact.predictor_input_digest, config.sha256(), artifact.mask_hash, artifact.roi_pixel_count, artifact.roi_area_ratio, 0, 0, 0, 0)
    return evidence, artifact.mask_payload


@dataclass(frozen=True)
class CodecCaseResult:
    snapshot_id: str; timestamp_s: float; method: str; budget_label: str; budget_bytes: int; raw_image_sha256: str; mask_sha256: str; payload: bytes; payload_bytes: int; mask_signal_bytes: int; metadata_bytes: int; charged_bytes: int; reconstruction: np.ndarray; reconstruction_sha256: str; fallback: int; replacement: int; case_sha256: str


def _mask_signal(mask: tuple[float, ...]) -> bytes:
    indices = [index for index, value in enumerate(mask) if value > 0]
    if len(indices) > 65535: raise ValueError("mask signaling count overflow")
    return len(indices).to_bytes(2, "big") + b"".join(index.to_bytes(2, "big") for index in indices)


def encode_reconstruct_case(runtime_config: dict, snapshot: SnapshotCodecInput, mask: MethodMaskEvidence, mask_payload: tuple[float, ...], budget_label: str) -> CodecCaseResult:
    load_v2_runtime_config(runtime_config)
    if budget_label not in BUDGET_ORDER or budget_label not in runtime_config["budgets"] or mask.method not in runtime_config["methods"]: raise ValueError("method or budget override")
    if mask.mask_sha256 != digest(mask_payload) or mask.actual_future_usage or mask.combined_usage or mask.oracle_usage or mask.fallback: raise ValueError("untrusted mask evidence")
    image = Image.fromarray(snapshot.image, "RGB"); signal = _mask_signal(mask_payload); metadata = (CODEC_VERSION + "|mask-index-v1|" + mask.method).encode("ascii")
    # Both methods share this fixed descending candidate family and choose the first feasible byte-fair allocation.
    tile_roi = []
    array = np.asarray(mask_payload, dtype=np.uint8).reshape(120, 160)
    for _, _, _, bounds in DEFAULT_M5_GRID.iter_tiles(): tile_roi.append(bool(array[bounds[1]:bounds[3], bounds[0]:bounds[2]].any()))
    budget = int(runtime_config["budgets"][budget_label]); selected_result = None
    for enhanced in (95, 75, 55, 35, 15, 1):
        qualities = tuple(enhanced if selected else max(1, enhanced - 30) for selected in tile_roi)
        candidate_tiles = encode_rgb_frame_to_tiles(image, DEFAULT_M5_GRID, qualities); candidate_payload = serialize_tiled_frame(DEFAULT_M5_GRID, candidate_tiles); candidate_charged = len(candidate_payload) + len(signal) + len(metadata)
        if candidate_charged <= budget:
            selected_result = (candidate_tiles, candidate_payload, candidate_charged); break
    if selected_result is None: raise ValueError("no deterministic under-budget codec allocation")
    tiles, payload, charged = selected_result; reconstructed = np.asarray(decode_tiles_to_rgb(tiles, DEFAULT_M5_GRID), dtype=np.uint8)
    base = {"snapshot_id": snapshot.snapshot_id,"timestamp_s":snapshot.timestamp_s,"method":mask.method,"budget_label":budget_label,"budget_bytes":budget,"raw_image_sha256":snapshot.raw_image_sha256,"mask_sha256":mask.mask_sha256,"payload_sha256":_sha(payload),"payload_bytes":len(payload),"mask_signal_bytes":len(signal),"metadata_bytes":len(metadata),"charged_bytes":charged,"reconstruction_sha256":_sha(reconstructed.tobytes()),"fallback":0,"replacement":0}
    return CodecCaseResult(snapshot.snapshot_id,snapshot.timestamp_s,mask.method,budget_label,budget,snapshot.raw_image_sha256,mask.mask_sha256,payload,len(payload),len(signal),len(metadata),charged,reconstructed,base["reconstruction_sha256"],0,0,digest(base))


@dataclass(frozen=True)
class CaseEvaluation:
    case_sha256: str; reconstruction_sha256: str; full_mse: float; full_psnr_db: float; full_ssim: float; evaluation_sha256: str


def evaluate_codec_case(runtime_config: dict, snapshot: SnapshotCodecInput, case: CodecCaseResult) -> CaseEvaluation:
    load_v2_runtime_config(runtime_config)
    if case.snapshot_id != snapshot.snapshot_id or case.timestamp_s != snapshot.timestamp_s or case.raw_image_sha256 != snapshot.raw_image_sha256 or case.reconstruction_sha256 != _sha(case.reconstruction.tobytes()) or case.charged_bytes > case.budget_bytes: raise ValueError("invalid frozen codec output")
    metrics = compute_error_metrics(snapshot.image, case.reconstruction); ssim = compute_ssim(snapshot.image, case.reconstruction)
    base = {"case_sha256":case.case_sha256,"reconstruction_sha256":case.reconstruction_sha256,"full_mse":metrics.mse,"full_psnr_db":metrics.psnr_db,"full_ssim":ssim,"metric_version":"m5-image-quality-v1"}
    return CaseEvaluation(case.case_sha256,case.reconstruction_sha256,metrics.mse,metrics.psnr_db,ssim,digest(base))


def audit_codec_case(runtime_config: dict, snapshot: SnapshotCodecInput, mask: MethodMaskEvidence, mask_payload: tuple[float, ...], case: CodecCaseResult, evaluation: CaseEvaluation) -> dict:
    load_v2_runtime_config(runtime_config)
    if case.method != mask.method or case.mask_sha256 != mask.mask_sha256 or case.raw_image_sha256 != snapshot.raw_image_sha256 or case.reconstruction_sha256 != _sha(case.reconstruction.tobytes()) or case.charged_bytes != case.payload_bytes + case.mask_signal_bytes + case.metadata_bytes or case.charged_bytes > case.budget_bytes or any((mask.actual_future_usage,mask.combined_usage,mask.oracle_usage,mask.fallback,case.fallback,case.replacement)) or evaluation.case_sha256 != case.case_sha256 or evaluation.reconstruction_sha256 != case.reconstruction_sha256: raise ValueError("case audit failed")
    expected = encode_reconstruct_case(runtime_config,snapshot,mask,mask_payload,case.budget_label)
    if expected.case_sha256 != case.case_sha256: raise ValueError("codec evidence is not deterministic")
    return {"case_sha256":case.case_sha256,"evaluation_sha256":evaluation.evaluation_sha256,"audit_sha256":digest({"case":case.case_sha256,"evaluation":evaluation.evaluation_sha256}),"passed":True}


def build_and_audit_one_identity_cases(runtime_config: dict, snapshots: list[SnapshotCodecInput], *, safe_output_root: str | Path) -> dict:
    load_v2_runtime_config(runtime_config); root=Path(safe_output_root).resolve(); temp=Path(tempfile.gettempdir()).resolve()
    if temp not in root.parents or root.exists() or {"m5","data","pilot","formal","calibration"}&{x.lower() for x in root.parts}: raise ValueError("unsafe synthetic output root")
    expected=runtime_config["snapshots"]
    if [(x.snapshot_id,x.timestamp_s) for x in snapshots] != [(x["snapshot_id"],x["timestamp_s"]) for x in expected]: raise ValueError("snapshot coverage mismatch")
    records=[]
    for snapshot in snapshots:
        for method in METHODS:
            evidence,payload=build_method_mask(runtime_config,snapshot,method)
            for budget in BUDGET_ORDER:
                case=encode_reconstruct_case(runtime_config,snapshot,evidence,payload,budget); evaluation=evaluate_codec_case(runtime_config,snapshot,case); records.append(audit_codec_case(runtime_config,snapshot,evidence,payload,case,evaluation)|{"snapshot_id":snapshot.snapshot_id,"method":method,"budget_label":budget,"charged_bytes":case.charged_bytes})
    if len(records)!=32 or len({(x['snapshot_id'],x['method'],x['budget_label']) for x in records})!=32: raise ValueError("incomplete or duplicate case matrix")
    aggregate={"schema_version":"m6a-v2-synthetic-codec-audit-v1","identity":runtime_config["episode_id"],"case_count":32,"cases":records,"execution_authorized":False,"webots_started":False,"synthetic_fixture":all(x.synthetic_fixture for x in snapshots),"scientific_result":False,"prohibited_usage":0,"fallback":0,"replacement":0}
    aggregate["aggregate_sha256"]=digest(aggregate);return aggregate
