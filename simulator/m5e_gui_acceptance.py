"""Small GUI-acceptance helpers shared by the M5E runner and controller."""

from __future__ import annotations

from collections.abc import Callable, Mapping


GUI_ACCEPTANCE_ENVIRONMENT_VARIABLE = "M5E_GUI_ACCEPTANCE"


def gui_acceptance_requested(environment: Mapping[str, str]) -> bool:
    """Return whether this controller invocation should pause for GUI review."""

    return environment.get(GUI_ACCEPTANCE_ENVIRONMENT_VARIABLE) == "1"


def gui_acceptance_message(scenario_id: str, snapshot_count: int) -> str:
    return (
        "M5E GUI ACCEPTANCE READY\n"
        f"Scenario: {scenario_id}\n"
        f"Snapshots: {snapshot_count}\n"
        "Simulation paused. Inspect Scene Tree, geometry, robot stability, Camera alignment, overlays, and Console. "
        "Close Webots manually when finished."
    )


def pause_for_gui_acceptance(
    supervisor: object,
    scenario_id: str,
    snapshot_count: int,
    pause_mode: int,
    emit: Callable[[str], None] = print,
) -> None:
    """Pause the simulation after capture while leaving the GUI lifecycle to Webots."""

    supervisor.simulationSetMode(pause_mode)
    emit(gui_acceptance_message(scenario_id, snapshot_count))
