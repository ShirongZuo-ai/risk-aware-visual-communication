"""Schema-shaped dense JSONL logger. Construction never launches Webots."""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED = {"schema_version", "protocol_version", "episode_id", "split", "scenario_family", "parameter_set_id", "seed", "timestep_index", "timestamp_s", "basic_timestep_s", "robot_state", "applied_command", "future_command_schedule", "obstacles", "robot_footprint", "raw_contact_observation", "validated_collision_event", "provenance"}

def validate_step_record(record: dict) -> None:
    missing = REQUIRED - record.keys()
    if missing:
        raise ValueError(f"missing step fields: {sorted(missing)}")
    if record["schema_version"] != "m9a-step-log-v2" or record["protocol_version"] != "m9a-p-v1":
        raise ValueError("version mismatch")
    if record["timestep_index"] < 0 or record["timestamp_s"] < 0 or record["basic_timestep_s"] <= 0:
        raise ValueError("invalid time fields")
    raw = record["raw_contact_observation"]
    validated = record["validated_collision_event"]
    if raw.get("raw_contact_point_count") != len(raw.get("points", [])) or not isinstance(validated.get("collision_active"), bool):
        raise ValueError("invalid contact fields")

class DenseStepLogger:
    def __init__(self, path: Path):
        self.path = Path(path); self._last_step = -1; self._last_time = -1.0
    def append(self, record: dict) -> None:
        validate_step_record(record)
        if record["timestep_index"] != self._last_step + 1 or record["timestamp_s"] <= self._last_time:
            raise ValueError("steps must be dense and timestamps strictly increasing")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        self._last_step, self._last_time = record["timestep_index"], record["timestamp_s"]

