"""Generate the frozen 256-frame M5E-D formal dataset with Webots."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_dataset_common import manifest_row, resolve_output_root, summary_path, write_episode_manifest, write_job, write_manifest
from scripts.run_m5e_dataset_smoke import DEFAULT_WEBOTS, WORLD, _remove_episode_artifacts, _run_one
from scripts.validate_m5e_dataset import validate_episode
from simulator.m5e_config import MAX_REPLACEMENTS, SCENARIO_IDS, primary_seed, primary_seed_indices, replacement_seed
from simulator.m5e_scenarios import generate_scenario


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data/m5e_formal")
    parser.add_argument("--webots", default=str(DEFAULT_WEBOTS))
    parser.add_argument("--timeout-s", type=float, default=75.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scenario", action="append", choices=SCENARIO_IDS)
    parser.add_argument("--seed-index", type=int, action="append", choices=primary_seed_indices("formal"))
    return parser


def planned_formal_configs(selected_scenarios: tuple[str, ...] = SCENARIO_IDS, selected_seed_indices: tuple[int, ...] = primary_seed_indices("formal")):
    return tuple(
        generate_scenario(scenario_id, "formal", primary_seed("formal", scenario_index, seed_index))
        for scenario_index, scenario_id in enumerate(SCENARIO_IDS, start=1)
        if scenario_id in selected_scenarios
        for seed_index in selected_seed_indices
    )


def write_formal_seed_manifest(output_root: Path, configs, *, subset: bool = False) -> Path:
    destination = output_root / "metadata" / "m5e" / "formal_seed_manifest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "split": "formal",
        "subset": subset,
        "scenario_count": len({config.scenario_id for config in configs}),
        "episode_count": len(configs),
        "snapshot_count": len(configs) * 4,
        "seed_rule": "formal primary seeds are 200000 + 100 * scenario_index + seed_index, seed_index in 0..7",
        "replacement_rule": "formal replacement seeds are 200000 + 100 * scenario_index + 50 + replacement_index, replacement_index in 0..29",
        "smoke_seeds": {f"S{index}": 9000 + index for index in range(1, 9)},
        "calibration_seeds": {
            f"S{index}": [primary_seed("calibration", index, seed_index) for seed_index in primary_seed_indices("calibration")]
            for index in range(1, 9)
        },
        "formal_primary_seeds": {
            scenario_id: [config.seed for config in configs if config.scenario_id == scenario_id]
            for scenario_id in SCENARIO_IDS
            if any(config.scenario_id == scenario_id for config in configs)
        },
    }
    formal = {config.seed for config in configs}
    smoke = set(payload["smoke_seeds"].values())
    calibration = {seed for seeds in payload["calibration_seeds"].values() for seed in seeds}
    if formal & smoke or formal & calibration:
        raise ValueError("formal seeds overlap smoke or calibration seeds")
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def write_replacement_log(output_root: Path, summaries: list[dict]) -> Path:
    destination = output_root / "logs" / "m5" / "m5e_formal_replacement_log.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = ("scenario_id", "episode_id", "original_seed", "actual_seed", "replacement_index", "status", "failure_reason")
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in sorted(summaries, key=lambda value: (value["scenario_id"], int(value["original_seed"]), int(value["replacement_index"]))):
            writer.writerow({field: item.get(field, "") for field in fields})
    return destination


def write_failure_log(output_root: Path, summaries: list[dict]) -> Path:
    destination = output_root / "logs" / "m5" / "m5e_formal_failure_log.csv"
    fields = ("scenario_id", "episode_id", "original_seed", "actual_seed", "replacement_index", "status", "failure_reason")
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in summaries:
            if item.get("status") != "captured":
                writer.writerow({field: item.get(field, "") for field in fields})
    return destination


def main() -> int:
    args = _argument_parser().parse_args()
    if args.overwrite and args.resume:
        print("--overwrite and --resume are mutually exclusive")
        return 2
    webots = Path(args.webots)
    if not webots.exists():
        print(f"Webots executable not found: {webots}")
        return 2
    output_root = resolve_output_root(args.output_root)
    selected_scenarios = tuple(args.scenario or SCENARIO_IDS)
    selected_seed_indices = tuple(args.seed_index or primary_seed_indices("formal"))
    primary_configs = planned_formal_configs(selected_scenarios, selected_seed_indices)
    subset = selected_scenarios != SCENARIO_IDS or selected_seed_indices != primary_seed_indices("formal")
    for config in primary_configs:
        destination = summary_path(output_root, config, config.seed, 0)
        if destination.exists() and not (args.overwrite or args.resume):
            print(f"Refusing to overwrite existing episode: {destination}")
            return 2
        print(f"planned {config.scenario_id}: seed={config.seed} summary={destination}")
    write_formal_seed_manifest(output_root, primary_configs, subset=subset)
    if args.dry_run:
        print(f"dry-run command: {webots} --batch --mode=fast {WORLD}")
        print(f"formal episodes={len(primary_configs)} frames={len(primary_configs) * 4} subset={subset}")
        return 0

    rows: list[dict[str, str]] = []
    attempt_summaries: list[dict] = []
    for primary_config in primary_configs:
        scenario_number = SCENARIO_IDS.index(primary_config.scenario_id) + 1
        original_seed = primary_config.seed
        accepted = None
        for replacement_index in range(MAX_REPLACEMENTS["formal"] + 1):
            actual_seed = original_seed if replacement_index == 0 else replacement_seed("formal", scenario_number, replacement_index - 1)
            config = generate_scenario(primary_config.scenario_id, "formal", actual_seed)
            destination = summary_path(output_root, config, original_seed, replacement_index)
            if args.overwrite:
                _remove_episode_artifacts(output_root, config, original_seed, replacement_index)
            if destination.exists() and args.resume:
                print(f"resume {config.scenario_id}: seed={original_seed} using {destination}")
            else:
                job = write_job(output_root, config, original_seed, replacement_index)
                log = output_root / "logs" / "m5" / f"{destination.parent.name}.log"
                print(f"running {config.scenario_id}: original_seed={original_seed} actual_seed={actual_seed} replacement={replacement_index}")
                try:
                    _run_one(webots, job, destination, log, args.timeout_s, gui=False)
                except Exception as error:
                    print(f"attempt failed for {config.scenario_id}: {error}")
                    if destination.exists():
                        attempt_summaries.append(json.loads(destination.read_text(encoding="utf-8")))
                    continue
            try:
                summary = validate_episode(destination)
            except Exception as error:
                summary = json.loads(destination.read_text(encoding="utf-8"))
                summary["status"] = "invalid_scenario_validation"
                summary["failure_reason"] = str(error)
                destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                attempt_summaries.append(summary)
                print(f"scenario {config.scenario_id} attempt rejected: {error}")
                continue
            accepted = summary
            attempt_summaries.append(summary)
            rows.extend(manifest_row(summary, snapshot, scenario_validation_passed=True) for snapshot in summary["snapshots"])
            print(f"passed {config.scenario_id}: seed={original_seed} snapshots=4 replacement={replacement_index}")
            break
        if accepted is None:
            write_episode_manifest(output_root, attempt_summaries, split="formal")
            write_replacement_log(output_root, attempt_summaries)
            write_failure_log(output_root, attempt_summaries)
            print(f"replacement pool exhausted for {primary_config.scenario_id} seed={original_seed}")
            return 1
    write_manifest(output_root, rows)
    write_episode_manifest(output_root, attempt_summaries, split="formal")
    write_replacement_log(output_root, attempt_summaries)
    write_failure_log(output_root, attempt_summaries)
    expected_rows = len(primary_configs) * 4
    if len(rows) != expected_rows:
        print(f"unexpected accepted frame count: {len(rows)} != {expected_rows}")
        return 1
    print(f"M5E formal generation passed: episodes={len(primary_configs)} frames={len(rows)} subset={subset}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
