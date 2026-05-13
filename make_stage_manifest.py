#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a manifest for the current CSI multi-group analysis stage."""

from pathlib import Path
import json

import numpy as np
import pandas as pd


DATA_DIR = Path("data/multi_group")
OUT_CSV = DATA_DIR / "stage_manifest.csv"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def shape_of(path: Path) -> str:
    if not path.exists():
        return ""
    return "x".join(map(str, np.load(path).shape))


def main() -> None:
    rows = []
    for stats_path in sorted(DATA_DIR.glob("group_*_stats.json")):
        group = stats_path.stem.replace("_stats", "")
        stats = load_json(stats_path)
        rows.append(
            {
                "group": group,
                "csv": str(DATA_DIR / f"{group}.csv"),
                "amplitude_npy": str(DATA_DIR / f"{group}_amplitude.npy"),
                "phase_npy": str(DATA_DIR / f"{group}_phase.npy"),
                "complex_npy": str(DATA_DIR / f"{group}_csi_complex.npy"),
                "amplitude_shape": shape_of(DATA_DIR / f"{group}_amplitude.npy"),
                "phase_shape": shape_of(DATA_DIR / f"{group}_phase.npy"),
                "complex_shape": shape_of(DATA_DIR / f"{group}_csi_complex.npy"),
                "valid_packets": stats.get("valid_packets"),
                "duration_sec": stats.get("total_time"),
                "rate_hz": stats.get("data_rate_hz"),
            }
        )

    manifest = pd.DataFrame(rows)
    manifest.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(manifest.to_string(index=False))
    print(f"\nSaved manifest: {OUT_CSV}")


if __name__ == "__main__":
    main()
