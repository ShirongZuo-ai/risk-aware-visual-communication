"""Build deterministic publication figures from the frozen M6 v3 analysis.

The default command renders from the checked publication source tables.  The
``--refresh-source-data`` mode is a release-maintainer operation: it extracts
those tables from the immutable analysis and, for the qualitative panel,
reconstructs one predeclared sample and verifies its hashes against runtime
evidence.  It never runs Webots or writes experimental evidence.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
from pathlib import Path
import textwrap
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import FancyBboxPatch
import numpy as np

from navigation.trajectory_prediction import CommandSegment
from scripts.m6a_dual_roi import CurrentState, ScheduleEvidence
from scripts.m6a_v2_codec_audit import (
    SnapshotCodecInput,
    build_method_mask,
    encode_reconstruct_case,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ROOT = PROJECT_ROOT / "results/m6_multiscene_formal_v3"
PREREGISTRATION_PATH = PROJECT_ROOT / "docs/results/m6_multiscene_v3_preregistration.json"
V3_MANIFEST_PATH = PROJECT_ROOT / "docs/results/m6a_v3_episode_source_manifest.json"
M5_SNAPSHOT_PATH = PROJECT_ROOT / "docs/results/m5e_publication_figure_snapshot.json"
FIGURE_DIR = PROJECT_ROOT / "docs/figures"
SOURCE_DIR = FIGURE_DIR / "data"
BUDGETS = ("severe", "low", "medium", "high")
BUDGET_LABELS = {item: item.title() for item in BUDGETS}
BUDGET_COLORS = {
    "severe": "#D55E00",
    "low": "#E69F00",
    "medium": "#56B4E9",
    "high": "#0072B2",
}
METHODS = ("state_only_risk_roi", "command_conditioned_risk_roi")
METHOD_LABELS = {
    "state_only_risk_roi": "State-only",
    "command_conditioned_risk_roi": "Command-conditioned",
}
PIPELINE_ROWS = (
    ("webots", "Webots scene\ne-puck + camera", "Simulation"),
    ("capture", "RGB + state\ncommand schedule", "Evidence"),
    ("predict", "Independent\ntrajectory predictors", "Prediction"),
    ("project", "Corridor projection\nand ROI masks", "Allocation"),
    ("codec", "Byte-fair tiled JPEG\n4 budgets", "Communication"),
    ("metrics", "TCOBR + quality\nbytes + ROI area", "Evaluation"),
    ("analysis", "Episode pairing\nscene bootstrap", "Inference"),
)
CAPABILITY_ROWS = (
    ("M1", "Synchronized capture", "RGB, pose, and motion evidence", "docs/progress.md"),
    ("M2", "Trajectory prediction", "State-only and command-conditioned", "docs/results/m2_in_place_summary_metrics.csv"),
    ("M3", "Risk geometry", "Footprint and uncertainty corridors", "docs/m3_world_risk_validation_report.md"),
    ("M4", "Image projection", "World risk to camera-space ROI", "docs/m4_camera_projection_validation_report.md"),
    ("M5", "Byte-fair evaluation", "4 methods, 4 budgets, 64 episodes", "docs/m5e_f_independent_acceptance_report.md"),
    ("M6", "Closed-loop formal study", "Trusted evidence and paired inference", "docs/m6_final_report.md"),
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _validate_summary(summary: dict[str, Any]) -> None:
    if summary.get("schema_version") != "m6-multiscene-eligibility-conditional-analysis-v1":
        raise ValueError("unexpected M6 analysis schema")
    if summary.get("original_eight_scene_gate") != {
        "status": "NOT_EVALUATED",
        "reason": "empty_scene_strata_after_preregistered_eligibility_exclusions",
    }:
        raise ValueError("original support-gate status changed")
    conditional = summary.get("conditional_analysis", {})
    primary = conditional.get("primary", {})
    if conditional.get("support_gate_passed") is not False:
        raise ValueError("conditional support-gate status changed")
    if any(float(primary.get(key, float("nan"))) != 0.0 for key in ("estimate", "ci_low", "ci_high")):
        raise ValueError("frozen primary result changed")
    if len(summary.get("included", [])) != 17 or len(summary.get("exclusions", [])) != 15:
        raise ValueError("TCOBR eligibility coverage changed")
    if summary.get("secondary_episode_count") != 32 or len(summary.get("secondary_rows", [])) != 32:
        raise ValueError("secondary episode coverage changed")


def _export_pipeline_source(source_dir: Path) -> Path:
    path = source_dir / "m6_pipeline_nodes.csv"
    rows = [
        {"order": index + 1, "node_id": node, "label": label.replace("\n", " / "), "stage": stage}
        for index, (node, label, stage) in enumerate(PIPELINE_ROWS)
    ]
    _write_csv(path, rows, ("order", "node_id", "label", "stage"))
    return path


def _export_capability_source(source_dir: Path) -> Path:
    path = source_dir / "m6_capability_evolution.csv"
    rows = [
        {"order": index + 1, "milestone": milestone, "capability": capability,
         "verified_output": output, "source_path": source}
        for index, (milestone, capability, output, source) in enumerate(CAPABILITY_ROWS)
    ]
    for row in rows:
        if not (PROJECT_ROOT / row["source_path"]).is_file():
            raise ValueError(f"missing capability source: {row['source_path']}")
    _write_csv(path, rows, ("order", "milestone", "capability", "verified_output", "source_path"))
    return path


def _export_study_scale_source(summary: dict[str, Any], source_dir: Path) -> Path:
    preregistration = _read_json(PREREGISTRATION_PATH)
    matrix = preregistration["matrix"]
    if len(matrix) != 32 or len({item["attempt_id"] for item in matrix}) != 32:
        raise ValueError("formal registration is not 32 unique attempts")
    if len({item["scene"] for item in matrix}) != 8:
        raise ValueError("formal registration is not eight scenes")
    snapshots = cases = finalized = launches = 0
    for registration in matrix:
        root = _find_attempt_root(registration["attempt_id"])
        runtime = _read_json(root / "episode_runtime_summary.json")
        aggregate = _read_json(root / "codec_aggregate.json")
        aggregate_validation = _read_json(root / "codec_aggregate_validation.json")
        process = _read_json(root / "host_process_result.json")
        final = _read_json(root / "m6a_v2_final_success.json")
        terminal = _read_json(root / ".m6a_v2_ownership_terminal.json")
        identity = runtime.get("identity", {})
        if (identity.get("episode_id"), identity.get("scene"), identity.get("seed")) != (
            registration["episode_id"], registration["scene"], registration["seed"]
        ):
            raise ValueError("runtime identity changed during study-scale export")
        if runtime.get("success") is not True or runtime.get("actual_snapshot_count") != 4:
            raise ValueError("formal runtime is not complete")
        if aggregate.get("case_count") != 32 or aggregate.get("expected_case_count") != 32:
            raise ValueError("formal aggregate is not 32 cases")
        if aggregate_validation.get("passed") is not True:
            raise ValueError("formal aggregate validation failed")
        if process.get("launch_performed") is not True or process.get("return_code") != 0 or process.get("timed_out") is not False:
            raise ValueError("formal process evidence is not a successful single launch")
        if final.get("joint_pass") is not True or terminal.get("state") != "completed":
            raise ValueError("formal finalization evidence is incomplete")
        snapshots += 4
        cases += 32
        launches += 1
        finalized += 1
    if len(summary["secondary_rows"]) != finalized:
        raise ValueError("analysis/finalization episode count mismatch")
    rows = (
        {"metric": "scenes", "label": "Scenes", "value": 8, "unit": "scenes", "source_path": _relative(PREREGISTRATION_PATH)},
        {"metric": "episodes", "label": "Episodes", "value": len(matrix), "unit": "episodes", "source_path": _relative(PREREGISTRATION_PATH)},
        {"metric": "snapshots", "label": "Snapshots", "value": snapshots, "unit": "snapshots", "source_path": "data/m6a/pilot/<launch>/<attempt>/episode_runtime_summary.json"},
        {"metric": "codec_cases", "label": "Codec cases", "value": cases, "unit": "cases", "source_path": "data/m6a/pilot/<launch>/<attempt>/codec_aggregate.json"},
        {"metric": "finalized", "label": "Finalized", "value": finalized, "unit": "of 32", "source_path": "data/m6a/pilot/<launch>/<attempt>/m6a_v2_final_success.json"},
        {"metric": "retries", "label": "Retries", "value": launches - len(matrix), "unit": "retries", "source_path": "data/m6a/pilot/<launch>/<attempt>/host_process_result.json"},
    )
    path = source_dir / "m6_study_scale_validation.csv"
    _write_csv(path, list(rows), ("metric", "label", "value", "unit", "source_path"))
    return path


def _export_absolute_budget_quality(summary: dict[str, Any], source_dir: Path) -> Path:
    manifest = _read_json(V3_MANIFEST_PATH)
    records = manifest.get("records", [])
    if len(records) != 32:
        raise ValueError("unexpected v3 manifest coverage")
    budget_maps = {json.dumps(record["budgets"], sort_keys=True) for record in records}
    if len(budget_maps) != 1:
        raise ValueError("formal budget targets differ by identity")
    budgets = records[0]["budgets"]
    means = summary["secondary_method_means"]
    rows: list[dict[str, Any]] = []
    for budget in BUDGETS:
        for method in METHODS:
            rows.append({
                "budget": budget,
                "target_bytes": budgets[budget],
                "method": method,
                "n_episodes": 32,
                "mean_full_psnr_db": means["full_psnr_db"][budget][method],
                "mean_full_ssim": means["full_ssim"][budget][method],
                "mean_charged_bytes": means["charged_bytes"][budget][method],
                "source_path": _relative(ANALYSIS_ROOT / "analysis_summary.json"),
                "budget_source_path": _relative(V3_MANIFEST_PATH),
            })
    path = source_dir / "m6_absolute_budget_quality.csv"
    _write_csv(path, rows, ("budget", "target_bytes", "method", "n_episodes", "mean_full_psnr_db",
                             "mean_full_ssim", "mean_charged_bytes", "source_path", "budget_source_path"))
    return path


def _export_m5_baseline_source(source_dir: Path) -> Path:
    snapshot = _read_json(M5_SNAPSHOT_PATH)
    rows = [row for row in snapshot["primary_bootstrap"] if row["budget_label"] in {"severe", "low"}]
    if len(rows) != 6 or {row["baseline_method"] for row in rows} != {"uniform", "center_roi", "object_roi"}:
        raise ValueError("unexpected frozen M5 primary coverage")
    output = [{
        "budget": row["budget_label"],
        "baseline": row["baseline_method"],
        "baseline_label": {"uniform": "Uniform", "center_roi": "Center ROI", "object_roi": "Object ROI"}[row["baseline_method"]],
        "n_episodes": row["episode_count"],
        "risk_minus_baseline_rw_psnr_db": row["observed_equal_scenario_mean_difference"],
        "ci_low": row["ci_lower_95"],
        "ci_high": row["ci_upper_95"],
        "source_path": _relative(M5_SNAPSHOT_PATH),
    } for row in rows]
    path = source_dir / "m5_primary_baseline_effects.csv"
    _write_csv(path, output, ("budget", "baseline", "baseline_label", "n_episodes",
                              "risk_minus_baseline_rw_psnr_db", "ci_low", "ci_high", "source_path"))
    return path


def _export_eligibility_source(summary: dict[str, Any], source_dir: Path) -> Path:
    preregistration = _read_json(PREREGISTRATION_PATH)
    included = {row["episode_id"] for row in summary["included"]}
    exclusions = {row["episode_id"]: row["reason"] for row in summary["exclusions"]}
    rows = []
    for item in sorted(preregistration["matrix"], key=lambda row: (row["scene"], row["seed"])):
        episode_id = item["episode_id"]
        if episode_id in included:
            eligible, reason = 1, "eligible"
        elif episode_id in exclusions:
            eligible, reason = 0, exclusions[episode_id]
        else:
            raise ValueError(f"unclassified formal episode: {episode_id}")
        rows.append({
            "scene": item["scene"],
            "seed": item["seed"],
            "episode_id": episode_id,
            "eligible": eligible,
            "status": reason,
        })
    if len(rows) != 32 or sum(row["eligible"] for row in rows) != 17:
        raise ValueError("unexpected publication eligibility coverage")
    path = source_dir / "m6_episode_eligibility.csv"
    _write_csv(path, rows, ("scene", "seed", "episode_id", "eligible", "status"))
    return path


def _export_tcobr_source(summary: dict[str, Any], source_dir: Path) -> Path:
    conditional = summary["conditional_analysis"]
    rows = [{
        "contrast": "primary_severe_low",
        "label": "Primary: Severe + Low",
        "budget": "primary",
        "n_episodes": 17,
        **{key: conditional["primary"][key] for key in ("estimate", "ci_low", "ci_high")},
    }]
    for budget in BUDGETS:
        result = conditional["budgets"][budget]
        rows.append({
            "contrast": budget,
            "label": BUDGET_LABELS[budget],
            "budget": budget,
            "n_episodes": 17,
            **{key: result[key] for key in ("estimate", "ci_low", "ci_high")},
        })
    path = source_dir / "m6_tcobr_budget_effects.csv"
    _write_csv(path, rows, ("contrast", "label", "budget", "n_episodes", "estimate", "ci_low", "ci_high"))
    return path


def _export_secondary_source(summary: dict[str, Any], source_dir: Path) -> Path:
    rows = []
    for budget in BUDGETS:
        rows.append({
            "budget": budget,
            "n_episodes": 32,
            "psnr_effect_db": summary["secondary"]["full_psnr_db"][budget],
            "ssim_effect": summary["secondary"]["full_ssim"][budget],
            "charged_bytes_effect": summary["secondary"]["charged_bytes"][budget],
            "roi_area_effect_ratio": summary["secondary"]["roi_area_ratio"][budget],
            "roi_area_effect_percentage_points": 100.0 * summary["secondary"]["roi_area_ratio"][budget],
        })
    path = source_dir / "m6_secondary_effects.csv"
    _write_csv(path, rows, (
        "budget", "n_episodes", "psnr_effect_db", "ssim_effect", "charged_bytes_effect",
        "roi_area_effect_ratio", "roi_area_effect_percentage_points",
    ))
    return path


def _find_attempt_root(attempt_id: str) -> Path:
    matches = sorted((PROJECT_ROOT / "data/m6a/pilot").glob(f"*/{attempt_id}"))
    if len(matches) != 1 or not matches[0].is_dir():
        raise ValueError(f"expected one immutable runtime root for {attempt_id}")
    return matches[0]


def _export_qualitative_source(summary: dict[str, Any], source_dir: Path) -> Path:
    # Deterministic non-cherry-picked rule: earliest eligible episode, earliest
    # snapshot, one fixed baseline, and the frozen budget endpoints.
    selected = min(summary["included"], key=lambda row: row["episode_id"])
    preregistration = _read_json(PREREGISTRATION_PATH)
    registration = next(row for row in preregistration["matrix"] if row["episode_id"] == selected["episode_id"])
    attempt_id = registration["attempt_id"]
    attempt_root = _find_attempt_root(attempt_id)
    runtime_path = PROJECT_ROOT / "results/m6a_v2_control/prepared" / attempt_id / "runtime_config.json"
    runtime = _read_json(runtime_path)
    snapshot_id, method = "0", "state_only_risk_roi"
    metadata_path = attempt_root / "raw" / f"{snapshot_id}.json"
    raw_path = attempt_root / "raw" / f"{snapshot_id}.rgb"
    metadata = _read_json(metadata_path)
    raw = raw_path.read_bytes()
    original = np.frombuffer(raw, dtype=np.uint8).reshape(120, 160, 3).copy()
    if _sha(raw) != metadata["frame_sha256"]:
        raise ValueError("qualitative original hash mismatch")
    state = CurrentState(**metadata["state"])
    schedule = ScheduleEvidence(
        metadata["schedule_id"],
        metadata["schedule_available_time_s"],
        tuple(CommandSegment(**segment) for segment in metadata["schedule_segments"]),
    )
    snapshot = SnapshotCodecInput.create(
        runtime_config=runtime,
        snapshot_id=snapshot_id,
        timestamp_s=metadata["simulation_timestamp_s"],
        image=original,
        state=state,
        schedule=schedule,
        camera_context=metadata["camera_context"],
    )
    aggregate_path = attempt_root / "codec_aggregate.json"
    aggregate = _read_json(aggregate_path)
    aggregate_cases = aggregate["snapshot_evidence"][0]["cases"]
    reconstructions: dict[str, dict[str, Any]] = {}
    for budget in ("severe", "high"):
        mask, mask_payload = build_method_mask(runtime, snapshot, method)
        case = encode_reconstruct_case(runtime, snapshot, mask, mask_payload, budget)
        recorded = next(item for item in aggregate_cases if item["method"] == method and item["budget"] == budget)
        if case.reconstruction_sha256 != recorded["tcobr_evidence"]["reconstruction_sha256"]:
            raise ValueError("qualitative reconstruction does not match frozen evidence")
        reconstructions[budget] = {
            "rgb_base64": base64.b64encode(case.reconstruction.tobytes()).decode("ascii"),
            "sha256": case.reconstruction_sha256,
            "full_psnr_db": recorded["full_psnr_db"],
            "full_ssim": recorded["full_ssim"],
            "charged_bytes": recorded["charged_bytes"],
        }
    value = {
        "schema_version": "m6-publication-qualitative-source-v2",
        "selection_rule": "lexicographically_first_eligible_episode_then_snapshot_0_then_state_only_then_budget_endpoints",
        "episode_id": selected["episode_id"],
        "attempt_id": attempt_id,
        "scene": selected["scene"],
        "seed": selected["seed"],
        "snapshot_id": snapshot_id,
        "method": method,
        "budgets": ["severe", "high"],
        "width_px": 160,
        "height_px": 120,
        "original_rgb_base64": base64.b64encode(original.tobytes()).decode("ascii"),
        "original_sha256": _sha(original.tobytes()),
        "reconstructions": reconstructions,
        "source_evidence": {
            "runtime_config": _relative(runtime_path),
            "raw_metadata": _relative(metadata_path),
            "raw_frame": _relative(raw_path),
            "codec_aggregate": _relative(aggregate_path),
        },
    }
    path = source_dir / "m6_qualitative_source.json"
    _write_json(path, value)
    return path


def export_publication_source_data(
    analysis_root: Path = ANALYSIS_ROOT,
    source_dir: Path = SOURCE_DIR,
) -> tuple[Path, ...]:
    summary = _read_json(analysis_root / "analysis_summary.json")
    _validate_summary(summary)
    if len(_read_csv(analysis_root / "episode_effects.csv")) != 17:
        raise ValueError("unexpected eligible episode CSV coverage")
    if len(_read_csv(analysis_root / "secondary_episode_effects.csv")) != 32:
        raise ValueError("unexpected secondary episode CSV coverage")
    return (
        _export_capability_source(source_dir),
        _export_pipeline_source(source_dir),
        _export_study_scale_source(summary, source_dir),
        _export_absolute_budget_quality(summary, source_dir),
        _export_eligibility_source(summary, source_dir),
        _export_tcobr_source(summary, source_dir),
        _export_secondary_source(summary, source_dir),
        _export_m5_baseline_source(source_dir),
        _export_qualitative_source(summary, source_dir),
    )


def validate_publication_source_data(source_dir: Path = SOURCE_DIR) -> dict[str, Any]:
    capability = _read_csv(source_dir / "m6_capability_evolution.csv")
    pipeline = _read_csv(source_dir / "m6_pipeline_nodes.csv")
    scale = _read_csv(source_dir / "m6_study_scale_validation.csv")
    absolute = _read_csv(source_dir / "m6_absolute_budget_quality.csv")
    eligibility = _read_csv(source_dir / "m6_episode_eligibility.csv")
    tcobr = _read_csv(source_dir / "m6_tcobr_budget_effects.csv")
    secondary = _read_csv(source_dir / "m6_secondary_effects.csv")
    m5 = _read_csv(source_dir / "m5_primary_baseline_effects.csv")
    qualitative = _read_json(source_dir / "m6_qualitative_source.json")
    if len(capability) != 6 or [row["milestone"] for row in capability] != [f"M{i}" for i in range(1, 7)]:
        raise ValueError("invalid capability-evolution source")
    if len(pipeline) != 7 or [int(row["order"]) for row in pipeline] != list(range(1, 8)):
        raise ValueError("invalid pipeline source")
    expected_scale = {"scenes": 8, "episodes": 32, "snapshots": 128, "codec_cases": 1024,
                      "finalized": 32, "retries": 0}
    if {row["metric"]: int(row["value"]) for row in scale} != expected_scale:
        raise ValueError("invalid formal study scale source")
    if len(absolute) != 8 or {(row["budget"], row["method"]) for row in absolute} != {
        (budget, method) for budget in BUDGETS for method in METHODS
    }:
        raise ValueError("invalid absolute budget-quality source")
    targets = {"severe": 31466, "low": 32374, "medium": 33509, "high": 34871}
    for row in absolute:
        if int(row["target_bytes"]) != targets[row["budget"]] or int(row["n_episodes"]) != 32:
            raise ValueError("absolute budget-quality binding changed")
        if float(row["mean_charged_bytes"]) > float(row["target_bytes"]):
            raise ValueError("mean actual bytes exceed frozen target")
    if len(eligibility) != 32 or sum(int(row["eligible"]) for row in eligibility) != 17:
        raise ValueError("invalid eligibility source")
    if len(tcobr) != 5 or any(float(row[key]) != 0.0 for row in tcobr for key in ("estimate", "ci_low", "ci_high")):
        raise ValueError("invalid frozen TCOBR source")
    if len(secondary) != 4 or {row["budget"] for row in secondary} != set(BUDGETS):
        raise ValueError("invalid secondary source")
    if len(m5) != 6 or {(row["budget"], row["baseline"]) for row in m5} != {
        (budget, baseline) for budget in ("severe", "low") for baseline in ("uniform", "center_roi", "object_roi")
    }:
        raise ValueError("invalid M5 primary-baseline source")
    m5_values = {(row["budget"], row["baseline"]): float(row["risk_minus_baseline_rw_psnr_db"]) for row in m5}
    if not (m5_values[("low", "uniform")] > 0 and m5_values[("low", "center_roi")] > 0
            and m5_values[("severe", "uniform")] < 0 and m5_values[("severe", "object_roi")] < 0):
        raise ValueError("M5 positive/adverse findings changed")
    if qualitative.get("selection_rule") != "lexicographically_first_eligible_episode_then_snapshot_0_then_state_only_then_budget_endpoints":
        raise ValueError("qualitative selection rule changed")
    if qualitative.get("method") != "state_only_risk_roi" or qualitative.get("budgets") != ["severe", "high"]:
        raise ValueError("qualitative method or budget endpoints changed")
    expected_size = 120 * 160 * 3
    original = base64.b64decode(qualitative["original_rgb_base64"], validate=True)
    if len(original) != expected_size or _sha(original) != qualitative["original_sha256"]:
        raise ValueError("invalid qualitative original")
    for budget in ("severe", "high"):
        reconstruction = base64.b64decode(qualitative["reconstructions"][budget]["rgb_base64"], validate=True)
        if len(reconstruction) != expected_size or _sha(reconstruction) != qualitative["reconstructions"][budget]["sha256"]:
            raise ValueError("invalid qualitative reconstruction")
    if not (float(qualitative["reconstructions"]["high"]["full_psnr_db"])
            > float(qualitative["reconstructions"]["severe"]["full_psnr_db"])
            and float(qualitative["reconstructions"]["high"]["full_ssim"])
            > float(qualitative["reconstructions"]["severe"]["full_ssim"])):
        raise ValueError("qualitative endpoint quality is not monotonic")
    return {
        "capability": capability,
        "pipeline": pipeline,
        "scale": scale,
        "absolute": absolute,
        "eligibility": eligibility,
        "tcobr": tcobr,
        "secondary": secondary,
        "m5": m5,
        "qualitative": qualitative,
    }


def _style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9.5,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "figure.titlesize": 14,
        "legend.fontsize": 8.5,
        "svg.hashsalt": "ravc-m6-publication-v1",
    })


def _normalize_svg(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text("\n".join(line.rstrip() for line in text.splitlines()) + "\n", encoding="utf-8", newline="\n")


def _save_pair(figure: plt.Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png, svg = output_dir / f"{stem}.png", output_dir / f"{stem}.svg"
    figure.savefig(
        png,
        dpi=360,
        bbox_inches="tight",
        metadata={"Software": "risk-aware-visual-communication M6 publication figures"},
    )
    figure.savefig(svg, bbox_inches="tight", metadata={"Date": None, "Creator": "RAVC M6 publication figures"})
    _normalize_svg(svg)
    plt.close(figure)
    return png, svg


def _plot_capability(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    figure, axis = plt.subplots(figsize=(13.2, 4.2), constrained_layout=True)
    axis.set_xlim(-1.0, 11.0)
    axis.set_ylim(-0.75, 2.2)
    axis.axis("off")
    colors = ("#E8F1F8", "#DCEFE8", "#DCEFE8", "#FFF2CC", "#F5E6F2", "#DDEAF7")
    for index, (row, color) in enumerate(zip(rows, colors)):
        x = index * 2.0
        axis.plot([x, x + 2.0] if index < 5 else [x, x], [0.42, 0.42], color="#7A7A7A", lw=2.0, zorder=0)
        axis.scatter([x], [0.42], s=185, color="#0072B2", edgecolor="white", linewidth=1.2, zorder=2)
        axis.text(x, 0.42, row["milestone"], ha="center", va="center", color="white", weight="bold", fontsize=9)
        box = FancyBboxPatch((x - 0.78, 0.82), 1.56, 0.92, boxstyle="round,pad=0.06,rounding_size=0.06",
                             linewidth=1.0, edgecolor="#4D4D4D", facecolor=color)
        axis.add_patch(box)
        axis.text(x, 1.47, row["capability"], ha="center", va="center", fontsize=9, weight="bold")
        axis.text(x, 1.12, textwrap.fill(row["verified_output"], width=25), ha="center", va="center",
                  fontsize=7.4, color="#444444")
    axis.set_title("Verified research capability evolution: synchronized evidence to formal inference", weight="bold", pad=12)
    axis.text(5.0, -0.34, "Each milestone adds a validated research capability; scientific method effects remain a separate question.",
              ha="center", fontsize=9, color="#444444")
    return _save_pair(figure, output_dir, "m6_capability_evolution")


def _plot_study_scale(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    figure, axes = plt.subplots(2, 3, figsize=(11.2, 5.5), constrained_layout=True)
    colors = ("#E8F1F8", "#E8F1F8", "#DCEFE8", "#FFF2CC", "#DDEAF7", "#F5E6F2")
    for axis, row, color in zip(axes.flat, rows, colors):
        axis.set_facecolor(color)
        axis.text(0.5, 0.61, f"{int(row['value']):,}", ha="center", va="center", fontsize=28,
                  weight="bold", color="#163A59", transform=axis.transAxes)
        axis.text(0.5, 0.31, row["label"], ha="center", va="center", fontsize=11, weight="bold",
                  transform=axis.transAxes)
        if row["metric"] == "finalized":
            axis.text(0.5, 0.13, "32 / 32 registered", ha="center", va="center", fontsize=8.5,
                      color="#444444", transform=axis.transAxes)
        axis.set_xticks([]); axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_color("#6A6A6A"); spine.set_linewidth(0.8)
    figure.suptitle("Frozen M6 formal-study scale and lifecycle validation", weight="bold")
    return _save_pair(figure, output_dir, "m6_study_scale_validation")


def _plot_absolute_budget_quality(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.2), constrained_layout=True)
    method_style = {
        "state_only_risk_roi": ("#0072B2", "o"),
        "command_conditioned_risk_roi": ("#D55E00", "s"),
    }
    x = [int(next(row for row in rows if row["budget"] == budget)["target_bytes"]) for budget in BUDGETS]
    panels = (
        ("mean_full_psnr_db", "Full-frame PSNR", "Mean PSNR (dB)"),
        ("mean_full_ssim", "Full-frame SSIM", "Mean SSIM"),
        ("mean_charged_bytes", "Actual complete-container bytes", "Mean actual bytes/frame"),
    )
    for axis, (key, title, ylabel) in zip(axes, panels):
        for method in METHODS:
            method_rows = {row["budget"]: row for row in rows if row["method"] == method}
            values = [float(method_rows[budget][key]) for budget in BUDGETS]
            color, marker = method_style[method]
            axis.plot(x, values, color=color, marker=marker, linewidth=1.8, markersize=6,
                      label=METHOD_LABELS[method])
        if key == "mean_charged_bytes":
            axis.plot(x, x, color="#555555", linestyle="--", linewidth=1.1, label="Budget target")
        axis.set_xticks(x, [f"{BUDGET_LABELS[budget]}\n{target:,}" for budget, target in zip(BUDGETS, x)])
        axis.set_xlabel("Frozen target budget (bytes/frame)")
        axis.set_ylabel(ylabel)
        axis.set_title(title, weight="bold")
        axis.grid(alpha=0.2)
    axes[0].legend(frameon=False, loc="best")
    axes[2].legend(frameon=False, loc="best")
    figure.suptitle("Absolute budget-quality operating points across all 32 formal episodes", weight="bold")
    figure.text(0.5, -0.03, "Points are absolute method means (n=32), not command-conditioned effect estimates.",
                ha="center", fontsize=8.6)
    return _save_pair(figure, output_dir, "m6_absolute_budget_quality")


def _plot_pipeline(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    figure, axis = plt.subplots(figsize=(14.0, 3.1), constrained_layout=True)
    axis.set_xlim(-0.9, 13.0)
    axis.set_ylim(-0.8, 2.1)
    axis.axis("off")
    colors = ("#E8F1F8", "#E8F1F8", "#DCEFE8", "#DCEFE8", "#FFF2CC", "#F5E6F2", "#F5E6F2")
    for index, (row, color) in enumerate(zip(rows, colors)):
        label = row["label"].replace(" / ", "\n")
        stage = row["stage"]
        x = index * 2.0
        box = FancyBboxPatch((x - 0.73, 0.0), 1.46, 1.0, boxstyle="round,pad=0.08,rounding_size=0.08",
                             linewidth=1.2, edgecolor="#333333", facecolor=color)
        axis.add_patch(box)
        axis.text(x, 0.5, label, ha="center", va="center", fontsize=9, weight="bold")
        axis.text(x, -0.28, stage, ha="center", va="center", fontsize=8, color="#555555")
        if index < len(rows) - 1:
            axis.annotate("", xy=(x + 1.27, 0.5), xytext=(x + 0.78, 0.5),
                          arrowprops={"arrowstyle": "-|>", "color": "#555555", "lw": 1.3})
    axis.set_title("M6 end-to-end evidence path: simulation to paired episode inference", pad=12, weight="bold")
    axis.text(6.0, 1.62, "No actual-future trajectory enters either allocation method", ha="center", color="#8B1A1A", fontsize=9)
    return _save_pair(figure, output_dir, "m6_pipeline")


def _plot_eligibility(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    matrix = np.zeros((8, 4), dtype=int)
    labels = np.empty((8, 4), dtype=object)
    for scene_index in range(8):
        scene_rows = sorted((row for row in rows if row["scene"] == f"S{scene_index + 1}"), key=lambda row: int(row["seed"]))
        if len(scene_rows) != 4:
            raise ValueError("eligibility scene coverage changed")
        for episode_index, row in enumerate(scene_rows):
            matrix[scene_index, episode_index] = int(row["eligible"])
            labels[scene_index, episode_index] = str(row["seed"])[-3:]
    figure, axis = plt.subplots(figsize=(8.4, 5.4), constrained_layout=True)
    axis.imshow(matrix, cmap=ListedColormap(["#D9D9D9", "#0072B2"]), vmin=0, vmax=1, aspect="auto")
    for (row, column), value in np.ndenumerate(matrix):
        axis.text(column, row, f"{'E' if value else 'U'}\n{labels[row, column]}", ha="center", va="center",
                  color="white" if value else "#333333", weight="bold", fontsize=9)
    axis.set_xticks(range(4), ["Episode 1", "Episode 2", "Episode 3", "Episode 4"])
    axis.set_yticks(range(8), [f"S{index}" for index in range(1, 9)])
    axis.set_xlabel("Registered episode within scene (cell shows seed suffix)")
    axis.set_ylabel("Scene")
    axis.set_title("TCOBR episode eligibility across the frozen 32-episode study", weight="bold")
    axis.text(0.0, -0.15, "E = eligible; U = undefined because no eligible critical obstacle. 17 eligible, 15 undefined.",
              transform=axis.transAxes, fontsize=8.5)
    return _save_pair(figure, output_dir, "m6_episode_eligibility")


def _plot_tcobr(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    figure, axis = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    positions = np.arange(len(rows))
    for position, row in zip(positions, rows):
        estimate, lower, upper = (float(row[key]) for key in ("estimate", "ci_low", "ci_high"))
        color = "#4D4D4D" if row["budget"] == "primary" else BUDGET_COLORS[row["budget"]]
        axis.errorbar(estimate, position, xerr=[[estimate - lower], [upper - estimate]], fmt="o", color=color,
                      markersize=7, capsize=4, linewidth=1.8, zorder=3)
        axis.annotate(f"{estimate:+.3f} [{lower:+.3f}, {upper:+.3f}]", (estimate, position),
                      xytext=(9, 0), textcoords="offset points", va="center", fontsize=8.5)
    axis.axvline(0.0, color="#222222", linewidth=1.2, linestyle="--", zorder=1)
    axis.set_xlim(-0.055, 0.055)
    axis.set_yticks(positions, [f"{row['label']} (n={row['n_episodes']})" for row in rows])
    axis.invert_yaxis()
    axis.set_xlabel("Command-conditioned minus state-only TCOBR")
    axis.set_title("Eligibility-conditional paired TCOBR effects", weight="bold")
    axis.grid(axis="x", alpha=0.2)
    axis.text(0.0, -0.17, "Within-scene episode bootstrap; five eligible scenes equally weighted; 10,000 replicates.",
              transform=axis.transAxes, fontsize=8.5)
    return _save_pair(figure, output_dir, "m6_tcobr_budget_forest")


def _plot_secondary(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    metrics = (
        ("psnr_effect_db", "Full-frame PSNR", "Difference (dB)"),
        ("ssim_effect", "Full-frame SSIM", "Difference"),
        ("charged_bytes_effect", "Actual charged bytes", "Difference (bytes/frame)"),
        ("roi_area_effect_percentage_points", "ROI area", "Difference (percentage points)"),
    )
    figure, axes = plt.subplots(2, 2, figsize=(10.5, 7.1), constrained_layout=True)
    for axis, (key, title, ylabel) in zip(axes.flat, metrics):
        values = [float(row[key]) for row in rows]
        axis.bar(range(4), values, color=[BUDGET_COLORS[row["budget"]] for row in rows], edgecolor="#333333", linewidth=0.6)
        axis.axhline(0.0, color="#222222", linewidth=1.0, linestyle="--")
        axis.set_xticks(range(4), [BUDGET_LABELS[row["budget"]] for row in rows])
        axis.set_ylabel(ylabel)
        axis.set_title(title, weight="bold")
        axis.grid(axis="y", alpha=0.18)
        span = max(max(abs(value) for value in values), 1e-8)
        for index, value in enumerate(values):
            label = f"{value:+.4f}" if key != "charged_bytes_effect" else f"{value:+.1f}"
            axis.annotate(label, (index, value), xytext=(0, 5 if value >= 0 else -11), textcoords="offset points",
                          ha="center", va="bottom" if value >= 0 else "top", fontsize=8)
        axis.set_ylim(min(min(values) - 0.28 * span, -0.12 * span), max(max(values) + 0.28 * span, 0.12 * span))
    figure.suptitle("Secondary paired effects across all 32 validated episodes\nCommand-conditioned minus state-only", weight="bold")
    figure.text(0.5, -0.01, "n=32 episodes for every budget; zero and negative effects are retained.", ha="center", fontsize=8.5)
    return _save_pair(figure, output_dir, "m6_secondary_budget_effects")


def _plot_m5_baselines(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path]:
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.8), sharex=True, constrained_layout=True)
    order = ("uniform", "center_roi", "object_roi")
    colors = {"uniform": "#0072B2", "center_roi": "#009E73", "object_roi": "#CC79A7"}
    for axis, budget in zip(axes, ("severe", "low")):
        budget_rows = {row["baseline"]: row for row in rows if row["budget"] == budget}
        for position, baseline in enumerate(order):
            row = budget_rows[baseline]
            estimate, lower, upper = (float(row[key]) for key in
                                      ("risk_minus_baseline_rw_psnr_db", "ci_low", "ci_high"))
            axis.errorbar(estimate, position, xerr=[[estimate - lower], [upper - estimate]], fmt="o",
                          color=colors[baseline], markersize=7, capsize=4, linewidth=1.8)
            axis.annotate(f"{estimate:+.3f}", (estimate, position), xytext=(0, 8),
                          textcoords="offset points", ha="center", fontsize=8)
        axis.axvline(0.0, color="#222222", linewidth=1.1, linestyle="--")
        axis.set_yticks(range(3), [budget_rows[item]["baseline_label"] for item in order])
        axis.invert_yaxis()
        axis.set_title(f"{budget.title()} budget", weight="bold")
        axis.set_xlabel("Risk ROI minus baseline RW-PSNR (dB)")
        axis.grid(axis="x", alpha=0.2)
        axis.set_xlim(-1.65, 3.65)
    figure.suptitle("M5 matched-byte Risk ROI effects: positive Low results and adverse Severe results", weight="bold")
    figure.text(0.5, -0.02, "Equal-weight mean of eight scene means; 95% scenario-stratified bootstrap CI; n=64 episodes.",
                ha="center", fontsize=8.5)
    return _save_pair(figure, output_dir, "m5_primary_baseline_effects")


def _decode_rgb(encoded: str, height: int, width: int) -> np.ndarray:
    return np.frombuffer(base64.b64decode(encoded, validate=True), dtype=np.uint8).reshape(height, width, 3)


def _plot_qualitative(value: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    height, width = int(value["height_px"]), int(value["width_px"])
    panels = [
        ("Original", _decode_rgb(value["original_rgb_base64"], height, width), "Frozen camera frame"),
    ]
    for budget in ("severe", "high"):
        item = value["reconstructions"][budget]
        panels.append((f"{budget.title()} budget", _decode_rgb(item["rgb_base64"], height, width),
                       f"PSNR {item['full_psnr_db']:.2f} dB | SSIM {item['full_ssim']:.3f}\n{item['charged_bytes']} bytes"))
    figure, axes = plt.subplots(1, 3, figsize=(11.0, 3.6), constrained_layout=True)
    for axis, (title, image, subtitle) in zip(axes, panels):
        axis.imshow(image, interpolation="nearest")
        axis.set_title(title, weight="bold")
        axis.set_xlabel(subtitle, fontsize=8.3)
        axis.set_xticks([]); axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_color("#444444"); spine.set_linewidth(0.8)
    figure.suptitle(
        f"Budget-quality reconstruction progression: {value['scene']}, seed {value['seed']}, snapshot {value['snapshot_id']}, State-only",
        weight="bold",
    )
    figure.text(0.5, -0.02,
                "Selection: lexicographically first eligible episode, snapshot 0, fixed State-only method, and budget endpoints; no effect-based selection.",
                ha="center", fontsize=8.5)
    return _save_pair(figure, output_dir, "m6_qualitative_comparison")


def render_publication_figures(
    source_dir: Path = SOURCE_DIR,
    output_dir: Path = FIGURE_DIR,
) -> tuple[Path, ...]:
    _style()
    source = validate_publication_source_data(source_dir)
    outputs: list[Path] = []
    outputs.extend(_plot_capability(source["capability"], output_dir))
    outputs.extend(_plot_pipeline(source["pipeline"], output_dir))
    outputs.extend(_plot_study_scale(source["scale"], output_dir))
    outputs.extend(_plot_absolute_budget_quality(source["absolute"], output_dir))
    outputs.extend(_plot_eligibility(source["eligibility"], output_dir))
    outputs.extend(_plot_tcobr(source["tcobr"], output_dir))
    outputs.extend(_plot_secondary(source["secondary"], output_dir))
    outputs.extend(_plot_m5_baselines(source["m5"], output_dir))
    outputs.extend(_plot_qualitative(source["qualitative"], output_dir))
    return tuple(outputs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-source-data", action="store_true", help="extract checked source tables from frozen local evidence")
    parser.add_argument("--analysis-root", type=Path, default=ANALYSIS_ROOT)
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=FIGURE_DIR)
    args = parser.parse_args()
    if args.refresh_source_data:
        export_publication_source_data(args.analysis_root, args.source_dir)
    outputs = render_publication_figures(args.source_dir, args.output_dir)
    print(json.dumps({"outputs": [_relative(path) if PROJECT_ROOT.resolve() in path.resolve().parents else str(path) for path in outputs]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
