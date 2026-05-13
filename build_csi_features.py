#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build window-level CSI features from multi-group amplitude arrays.

The label column currently uses the group name. Replace it with real action
labels after manual annotation if these groups correspond to different actions.
"""

from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("data/multi_group")
OUT_DIR = DATA_DIR / "features"
FEATURE_CSV = OUT_DIR / "csi_features.csv"


WINDOW_SIZE = 128
STEP_SIZE = 64


def zero_crossing_rate(x: np.ndarray) -> float:
    centered = x - np.mean(x)
    signs = np.sign(centered)
    return float(np.mean(signs[1:] != signs[:-1])) if len(signs) > 1 else 0.0


def extract_window_features(window: np.ndarray) -> dict:
    time_mean = window.mean(axis=1)
    subcarrier_mean = window.mean(axis=0)
    subcarrier_std = window.std(axis=0)
    diff = np.diff(time_mean)

    spectrum = np.abs(np.fft.rfft(time_mean - np.mean(time_mean)))
    if len(spectrum) > 1:
        dominant_bin = int(np.argmax(spectrum[1:]) + 1)
        spectral_energy = float(np.sum(spectrum[1:] ** 2))
    else:
        dominant_bin = 0
        spectral_energy = 0.0

    features = {
        "amp_mean": float(np.mean(window)),
        "amp_std": float(np.std(window)),
        "amp_min": float(np.min(window)),
        "amp_max": float(np.max(window)),
        "amp_median": float(np.median(window)),
        "amp_p25": float(np.percentile(window, 25)),
        "amp_p75": float(np.percentile(window, 75)),
        "time_mean_std": float(np.std(time_mean)),
        "time_mean_range": float(np.max(time_mean) - np.min(time_mean)),
        "time_diff_mean_abs": float(np.mean(np.abs(diff))) if len(diff) else 0.0,
        "time_zero_crossing": zero_crossing_rate(time_mean),
        "subcarrier_std_mean": float(np.mean(subcarrier_std)),
        "subcarrier_std_max": float(np.max(subcarrier_std)),
        "subcarrier_mean_peak": int(np.argmax(subcarrier_mean)),
        "fft_dominant_bin": dominant_bin,
        "fft_energy": spectral_energy,
    }

    bands = np.array_split(window, 4, axis=1)
    for idx, band in enumerate(bands, start=1):
        features[f"band{idx}_mean"] = float(np.mean(band))
        features[f"band{idx}_std"] = float(np.std(band))

    return features


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []

    for amp_path in sorted(DATA_DIR.glob("group_*_amplitude.npy")):
        group = amp_path.stem.replace("_amplitude", "")
        amp = np.load(amp_path).astype(float)

        for start in range(0, amp.shape[0] - WINDOW_SIZE + 1, STEP_SIZE):
            end = start + WINDOW_SIZE
            row = {
                "group": group,
                "label": group,
                "start_index": start,
                "end_index": end,
                "window_size": WINDOW_SIZE,
            }
            row.update(extract_window_features(amp[start:end]))
            rows.append(row)

    features = pd.DataFrame(rows)
    features.to_csv(FEATURE_CSV, index=False, encoding="utf-8-sig")
    print(features.groupby("group").size().rename("windows").to_string())
    print(f"\nSaved features: {FEATURE_CSV}")
    print(f"Feature table shape: {features.shape}")


if __name__ == "__main__":
    main()
