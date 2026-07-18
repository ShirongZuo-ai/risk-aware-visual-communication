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
from simulator.m5e_gui_acceptance import GUI_ACCEPTANCE_ENVIRONMENT_VARIABLE
from simulator.m5e_scenarios import generate_scenario


DEFAULT_WEBOTS = Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = PROJECT_ROOT / "simulator" / "worlds" / "m5e_dataset_generator.wbt"


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="data")
    parser.add_argument("--webots", default=str(DEFAULT_WEBOTS))
    parser.add_argument("--scenario", action="append", choices=SCENARIO_IDS)
    parser.add_argument("--timeout-s", type=float, default=75.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch Webots interactively for manual GUI acceptance and keep the scene open after snapshot generation.",
    )
    return parser


def _parse_args() -> argparse.Namespace:
    parser = _argument_parser()
    return parser.parse_args()


def gui_world_path(scenario_id: str) -> Path:
    return WORLD.with_name(f".m5e_gui_acceptance_{scenario_id.lower()}.wbt")


def prepare_gui_world(scenario_id: str) -> Path:
    destination = gui_world_path(scenario_id)
    shutil.copyfile(WORLD, destination)
    return destination


def build_webots_command(webots: Path, *, gui: bool, world: Path = WORLD) -> list[str]:
    if gui:
        return [str(webots), "--mode=realtime", str(world)]
    return [str(webots), "--batch", "--mode=fast", str(world)]


def controller_environment(job: Path, *, gui: bool, parent_environment: dict[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if parent_environment is None else parent_environment)
    environment["M5E_CONFIG_PATH"] = str(job)
    if gui:
        environment[GUI_ACCEPTANCE_ENVIRONMENT_VARIABLE] = "1"
    else:
        environment.pop(GUI_ACCEPTANCE_ENVIRONMENT_VARIABLE, None)
    return environment


def validate_cli_arguments(args: argparse.Namespace) -> None:
    if args.gui and len(args.scenario or ()) != 1:
        raise ValueError("--gui requires exactly one --scenario")
    if args.gui and args.resume:
        raise ValueError("--gui cannot be combined with --resume because no GUI window would be launched")


def _wait_for_process(
    process: subprocess.Popen[str],
    summary: Path,
    timeout_s: float,
    *,
    gui: bool,
    monotonic=time.monotonic,
    sleep=time.sleep,
) -> None:
    if gui:
        # Manual acceptance deliberately has no automatic timeout: the user closes Webots.
        while process.poll() is None:
            sleep(0.25)
        return

    started = monotonic()
    while monotonic() - started < timeout_s:
        if summary.exists():
            # Batch Webots can keep its process alive briefly after controller completion.
            process.terminate()
            return
        if process.poll() is not None:
            return
        sleep(0.25)
    process.kill()
    raise TimeoutError(f"Webots did not produce {summary} within {timeout_s:.1f}s")


def _run_one(
    webots: Path,
    job: Path,
    summary: Path,
    log_path: Path,
    timeout_s: float,
    *,
    gui: bool,
    world: Path = WORLD,
) -> None:
    environment = controller_environment(job, gui=gui)
    process = subprocess.Popen(
        build_webots_command(webots, gui=gui, world=world),
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = ""
    try:
        _wait_for_process(process, summary, timeout_s, gui=gui)
        output, _ = process.communicate(timeout=15)
    except KeyboardInterrupt:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
        raise
    finally:
        if process.poll() is None:
            process.kill()
    if not summary.exists():
        raise RuntimeError(f"Webots ended before the episode summary was written:\n{output[-4000:]}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    if "Traceback" in output or "status: 1" in output:
        raise RuntimeError(f"Webots controller output contains an error:\n{output[-4000:]}")


def validate_completed_episode(summary: Path) -> dict:
    result = validate_episode(summary)
    if result["completed_snapshot_count"] != 4:
        raise ValueError("GUI/automatic run did not produce four snapshots")
    return result


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
    try:
        validate_cli_arguments(args)
    except ValueError as error:
        print(error)
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
        world = gui_world_path(selected[0]) if args.gui else WORLD
        print(f"dry-run command: {' '.join(build_webots_command(webots, gui=args.gui, world=world))}")
        return 0

    rows, attempt_summaries = [], []
    for primary_config in configs:
        scenario_number = SCENARIO_IDS.index(primary_config.scenario_id) + 1
        original_seed = primary_config.seed
        accepted = None
        attempt_count = 1 if args.gui else MAX_REPLACEMENTS["smoke"] + 1
        for replacement_index in range(attempt_count):
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
                gui_world = prepare_gui_world(config.scenario_id) if args.gui else WORLD
                try:
                    _run_one(webots, job, destination, log, args.timeout_s, gui=args.gui, world=gui_world)
                except Exception as error:
                    print(f"attempt failed for {config.scenario_id}: {error}")
                    if destination.exists():
                        attempt_summaries.append(json.loads(destination.read_text(encoding="utf-8")))
                    continue
                finally:
                    if args.gui and gui_world.exists():
                        gui_world.unlink()
            try:
                summary = validate_completed_episode(destination)
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
            if args.gui:
                print(f"GUI run did not produce a valid complete episode for {primary_config.scenario_id}")
            else:
                print(f"replacement pool exhausted for {primary_config.scenario_id}")
            return 1
    destination = write_manifest(output_root, rows)
    episode_destination = write_episode_manifest(output_root, attempt_summaries)
    expected_rows = len(selected) * 4
    if len(rows) != expected_rows:
        print(f"unexpected accepted frame count: {len(rows)} != {expected_rows}")
        return 1
    if args.gui:
        print(f"GUI run completed: scenario={selected[0]} snapshots=4")
    else:
        print(f"M5E smoke generation passed: scenarios={len(configs)} frames={len(rows)} manifest={destination} episode_manifest={episode_destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
