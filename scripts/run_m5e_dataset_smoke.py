"""Generate the deterministic 32-frame M5E-B smoke dataset with Webots."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.m5e_dataset_common import (
    manifest_row,
    resolve_output_root,
    summary_path,
    write_episode_manifest,
    write_job,
    write_manifest,
)
from scripts.validate_m5e_dataset import validate_episode
from simulator.m5e_config import MAX_REPLACEMENTS, SCENARIO_IDS, primary_seed, replacement_seed
from simulator.m5e_scenarios import generate_scenario


DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = PROJECT_ROOT / "simulator" / "worlds" / "m5e_dataset_generator.wbt"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data")
    parser.add_argument("--webots", default=str(DEFAULT_WEBOTS))
    parser.add_argument("--scenario", action="append", choices=SCENARIO_IDS)
    parser.add_argument("--timeout-s", type=float, default=75.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _run_one(webots: Path, job: Path, summary: Path, log_path: Path, timeout_s: float) -> None:
    environment = os.environ.copy()
    environment["M5E_CONFIG_PATH"] = str(job)
    process = subprocess.Popen(
        [str(webots), "--batch", "--mode=fast", str(WORLD)],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    started = time.monotonic()
    output = ""
    try:
        while time.monotonic() - started < timeout_s:
            if summary.exists():
                # The controller has already written all artifacts. Batch Webots can keep its
                # process alive briefly after controller completion, so terminate it here.
                process.terminate()
                break
            if process.poll() is not None:
                break
            time.sleep(0.25)
        else:
            process.kill()
            raise TimeoutError(f"Webots did not produce {summary} within {timeout_s:.1f}s")
        output, _ = process.communicate(timeout=15)
    finally:
        if process.poll() is None:
            process.kill()
    if not summary.exists():
        raise RuntimeError(f"Webots ended before the episode summary was written:\n{output[-4000:]}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    if "Traceback" in output or "status: 1" in output:
        raise RuntimeError(f"Webots controller output contains an error:\n{output[-4000:]}")


def _remove_episode_artifacts(output_root: Path, config, original_seed: int, replacement_index: int) -> None:
    identity = summary_path(output_root, config, original_seed, replacement_index).parent.name
    targets = (
        output_root / "frames" / "m5e" / config.split / config.scenario_id / identity,
        output_root / "masks" / "m5e" / config.split / config.scenario_id / identity,
        output_root / "metadata" / "m5e" / config.split / config.scenario_id / identity,
        output_root / "metadata" / "m5e" / "_jobs" / f"{identity}.json",
        output_root / "logs" / "m5" / f"{identity}.log",
    )
    for target in targets:
        resolved = target.resolve()
        if output_root.resolve() not in resolved.parents:
            raise ValueError(f"refusing to remove path outside output root: {resolved}")
        if resolved.is_dir():
            shutil.rmtree(resolved)
        elif resolved.exists():
            resolved.unlink()


def main() -> int:
    args = _parse_args()
    if args.overwrite and args.resume:
        print("--overwrite and --resume are mutually exclusive")
        return 2
    webots = Path(args.webots)
    if not webots.exists():
        print(f"Webots executable not found: {webots}")
        return 2
    output_root = resolve_output_root(args.output_root)
    selected = tuple(args.scenario or SCENARIO_IDS)
    configs = [generate_scenario(scenario, "smoke", primary_seed("smoke", SCENARIO_IDS.index(scenario) + 1, 0)) for scenario in selected]
    for config in configs:
        destination = summary_path(output_root, config, config.seed, 0)
        if destination.exists() and not (args.overwrite or args.resume):
            print(f"Refusing to overwrite existing episode: {destination}")
            return 2
        print(f"planned {config.scenario_id}: seed={config.seed} summary={destination}")
    if args.dry_run:
        print(f"dry-run command: {webots} --batch --mode=fast {WORLD}")
        return 0

    rows, attempt_summaries = [], []
    for primary_config in configs:
        scenario_number = SCENARIO_IDS.index(primary_config.scenario_id) + 1
        original_seed = primary_config.seed
        accepted = None
        for replacement_index in range(MAX_REPLACEMENTS["smoke"] + 1):
            actual_seed = original_seed if replacement_index == 0 else replacement_seed("smoke", scenario_number, replacement_index - 1)
            config = generate_scenario(primary_config.scenario_id, "smoke", actual_seed)
            destination = summary_path(output_root, config, original_seed, replacement_index)
            if args.overwrite:
                _remove_episode_artifacts(output_root, config, original_seed, replacement_index)
            if destination.exists() and args.resume:
                print(f"resume {config.scenario_id}: reusing {destination}")
            else:
                job = write_job(output_root, config, original_seed, replacement_index)
                log = output_root / "logs" / "m5" / f"{destination.parent.name}.log"
                print(f"running {config.scenario_id}: original_seed={original_seed} actual_seed={actual_seed} replacement={replacement_index}")
                try:
                    _run_one(webots, job, destination, log, args.timeout_s)
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
            print(f"passed {config.scenario_id}: snapshots=4 replacement={replacement_index}")
            break
        if accepted is None:
            write_episode_manifest(output_root, attempt_summaries)
            print(f"replacement pool exhausted for {primary_config.scenario_id}")
            return 1
    destination = write_manifest(output_root, rows)
    episode_destination = write_episode_manifest(output_root, attempt_summaries)
    expected_rows = len(selected) * 4
    if len(rows) != expected_rows:
        print(f"unexpected accepted frame count: {len(rows)} != {expected_rows}")
        return 1
    print(f"M5E smoke generation passed: scenarios={len(configs)} frames={len(rows)} manifest={destination} episode_manifest={episode_destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
