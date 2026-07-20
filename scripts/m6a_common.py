"""Frozen manifest and preflight invariants for M6-A (no formal execution)."""
from __future__ import annotations
import argparse, hashlib, json
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION = "m6a-byte-fair-v1"
SCENES = tuple(f"S{i}" for i in range(1, 9))
METHODS = ("state_only_risk_roi", "command_conditioned_risk_roi")
BUDGETS = {"severe": 31466, "low": 32374, "medium": 33509, "high": 34871}
HORIZONS_S = (2.0,)
SNAPSHOT_PROGRESS = (0.20, 0.45, 0.70, 0.90)
SPLITS = {"calibration": (610000, 2), "formal": (620000, 4), "pilot": (600000, 1)}

@dataclass(frozen=True)
class Episode:
    split: str; scenario_id: str; seed: int; episode_id: str

def episodes(split: str) -> tuple[Episode, ...]:
    base, count = SPLITS[split]
    return tuple(Episode(split, scene, base + 100 * (index + 1) + seed_index,
                         f"m6a_{split}_{scene.lower()}_seed{base + 100 * (index + 1) + seed_index}")
                 for index, scene in enumerate(SCENES) for seed_index in range(count))

def manifest() -> dict:
    return {"protocol_version": VERSION, "methods": list(METHODS), "target_bytes": BUDGETS,
            "prediction_horizons_s": list(HORIZONS_S), "snapshot_progress": list(SNAPSHOT_PROGRESS),
            "actual_future_trajectory_used_by_methods": False,
            "command_conditioned_extra_input": "decision-time future command schedule only",
            "episodes": {split: [asdict(item) for item in episodes(split)] for split in SPLITS}}

def validate(data: dict) -> dict:
    if data.get("protocol_version") != VERSION or tuple(data.get("methods", ())) != METHODS: raise ValueError("M6-A protocol identity mismatch")
    if data.get("target_bytes") != BUDGETS or tuple(data.get("prediction_horizons_s", ())) != HORIZONS_S: raise ValueError("M6-A frozen budgets or horizons mismatch")
    if data.get("actual_future_trajectory_used_by_methods") is not False: raise ValueError("actual-future leakage flag is not false")
    seen=set(); coverage={}
    for split in ("calibration", "formal", "pilot"):
        rows=data["episodes"].get(split, []); expected=episodes(split)
        if [tuple((r[k] for k in ("split","scenario_id","seed","episode_id"))) for r in rows] != [tuple(asdict(x).values()) for x in expected]: raise ValueError(f"{split} episode schedule mismatch")
        ids={r["episode_id"] for r in rows}; seeds={r["seed"] for r in rows}
        if seen & ids or seen & seeds: raise ValueError("episode or seed overlap across M6-A splits")
        seen |= ids | seeds; coverage[split]=len(rows)
    if {r["episode_id"] for r in data["episodes"]["calibration"]} & {r["episode_id"] for r in data["episodes"]["formal"]}: raise ValueError("calibration/formal overlap")
    return {"calibration_episodes":coverage["calibration"],"formal_episodes":coverage["formal"],"pilot_episodes":coverage["pilot"],"formal_frames":coverage["formal"]*len(SNAPSHOT_PROGRESS),"formal_cases":coverage["formal"]*len(SNAPSHOT_PROGRESS)*len(METHODS)*len(BUDGETS)}

def write(path: Path) -> dict:
    data=manifest(); validate(data); text=json.dumps(data,indent=2,sort_keys=True)+"\n"
    if path.exists() and path.read_text(encoding="utf-8") != text: raise FileExistsError("refusing to replace frozen M6-A manifest")
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding="utf-8"); return data

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,default=PROJECT_ROOT/"docs/results/m6a_manifest.json"); args=parser.parse_args()
    data=write(args.output); print(json.dumps(validate(data),sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
