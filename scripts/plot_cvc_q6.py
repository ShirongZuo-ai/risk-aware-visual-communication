"""Static technical figures for the CVC-Q6 development record."""
from pathlib import Path
import json
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/cvc_q6_analysis/q6-g3-opportunity-persistent.json"
OUT = ROOT / "figures/cvc_q6"

def main() -> None:
    data = json.loads(DATA.read_text())
    families = list(data["families"])
    labels = [name.replace("_", "\n") for name in families]
    danger = [data["families"][name]["U0"]["mean_danger_steps_delta"] for name in families]
    clearance = [1000 * data["families"][name]["U0"]["mean_min_clearance_delta_m"] for name in families]
    palette = ["#2F5D7C" if value <= 0 else "#B24C4C" for value in danger]
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.8))
    y = np.arange(len(families))
    axes[0].barh(y, danger, color=palette)
    axes[0].axvline(0, color="#303030", linewidth=.9)
    axes[0].set_yticks(y, labels); axes[0].invert_yaxis()
    axes[0].set_xlabel("A1 − U0 danger steps per cell")
    axes[0].set_title("Danger exposure (lower is safer)")
    axes[1].barh(y, clearance, color=["#2F5D7C" if value >= 0 else "#B24C4C" for value in clearance])
    axes[1].axvline(0, color="#303030", linewidth=.9)
    axes[1].set_yticks(y, []); axes[1].invert_yaxis()
    axes[1].set_xlabel("A1 − U0 minimum clearance (mm)")
    axes[1].set_title("Clearance (higher is safer)")
    fig.suptitle("CVC-Q6 final rule-based development method: family-level effects", fontsize=13)
    fig.subplots_adjust(left=.17, right=.985, top=.80, bottom=.22, wspace=.05)
    fig.text(.5, .035, "Blue indicates the safer direction; red indicates an adverse direction. Exact cost: 72,000 wire bytes/episode.",
             ha="center", fontsize=8.5, color="#505050")
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "q6_family_safety.png", dpi=180, bbox_inches="tight")
    fig.savefig(OUT / "q6_family_safety.pdf", bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__": main()
