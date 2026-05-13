#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze CSI amplitude quality for multiple collected groups.

Outputs:
1. Per-group heatmaps and mean curves.
2. Cross-group mean comparison plot.
3. Summary CSV for data scale and amplitude statistics.
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DATA_DIR = Path("data/multi_group")
FIG_DIR = DATA_DIR / "figures"
SUMMARY_CSV = DATA_DIR / "quality_summary.csv"


def moving_average(values: np.ndarray, window: int = 15) -> np.ndarray:
    """Smooth a one-dimensional sequence with a centered moving average."""
    if len(values) < window:
        return values
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def load_stats(group: str) -> dict:
    stats_path = DATA_DIR / f"{group}_stats.json"
    if not stats_path.exists():
        return {}
    with stats_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def plot_group(group: str, amp: np.ndarray) -> dict:
    amp = np.asarray(amp, dtype=float)
    time_mean = amp.mean(axis=1)
    subcarrier_mean = amp.mean(axis=0)
    subcarrier_std = amp.std(axis=0)

    plt.figure(figsize=(12, 5))
    plt.imshow(amp.T, aspect="auto", origin="lower", cmap="viridis")
    plt.colorbar(label="Amplitude")
    plt.xlabel("Packet index")
    plt.ylabel("Subcarrier index")
    plt.title(f"{group} CSI amplitude heatmap")
    plt.tight_layout()
    plt.savefig(FIG_DIR / f"{group}_heatmap.png", dpi=180)
    plt.close()

    plt.figure(figsize=(12, 4))
    plt.plot(time_mean, linewidth=0.8, alpha=0.55, label="Raw mean amplitude")
    plt.plot(moving_average(time_mean), linewidth=1.8, label="Smoothed mean amplitude")
    plt.xlabel("Packet index")
    plt.ylabel("Mean amplitude")
    plt.title(f"{group} mean amplitude over time")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / f"{group}_mean_curve.png", dpi=180)
    plt.close()

    plt.figure(figsize=(12, 4))
    plt.plot(subcarrier_std, linewidth=1.2)
    plt.xlabel("Subcarrier index")
    plt.ylabel("Standard deviation")
    plt.title(f"{group} subcarrier fluctuation")
    plt.tight_layout()
    plt.savefig(FIG_DIR / f"{group}_subcarrier_std.png", dpi=180)
    plt.close()

    stats = load_stats(group)
    return {
        "group": group,
        "packets": int(amp.shape[0]),
        "subcarriers": int(amp.shape[1]),
        "duration_sec": float(stats.get("total_time", np.nan)),
        "rate_hz": float(stats.get("data_rate_hz", np.nan)),
        "amp_mean": float(np.mean(amp)),
        "amp_std": float(np.std(amp)),
        "amp_min": float(np.min(amp)),
        "amp_max": float(np.max(amp)),
        "time_mean_std": float(np.std(time_mean)),
        "subcarrier_std_mean": float(np.mean(subcarrier_std)),
        "subcarrier_mean_peak": int(np.argmax(subcarrier_mean)),
    }


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    group_curves = []
    amp_files = sorted(DATA_DIR.glob("group_*_amplitude.npy"))
    if not amp_files:
        raise FileNotFoundError(f"No amplitude files found in {DATA_DIR}")

    for amp_path in amp_files:
        group = amp_path.stem.replace("_amplitude", "")
        amp = np.load(amp_path)
        rows.append(plot_group(group, amp))
        curve = amp.mean(axis=1)
        group_curves.append((group, moving_average(curve)))

    summary = pd.DataFrame(rows)
    summary.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")

    plt.figure(figsize=(12, 5))
    for group, curve in group_curves:
        plt.plot(curve, linewidth=1.2, label=group)
    plt.xlabel("Packet index")
    plt.ylabel("Smoothed mean amplitude")
    plt.title("Cross-group mean amplitude comparison")
    plt.legend(ncol=3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "all_groups_mean_comparison.png", dpi=180)
    plt.close()

    print(summary.to_string(index=False))
    print(f"\nSaved summary: {SUMMARY_CSV}")
    print(f"Saved figures: {FIG_DIR}")


if __name__ == "__main__":
    main()
