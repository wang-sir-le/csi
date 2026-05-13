#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Visualize window-level CSI features with PCA."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


DATA_DIR = Path("data/multi_group")
FEATURE_CSV = DATA_DIR / "features" / "csi_features.csv"
FIG_DIR = DATA_DIR / "figures"


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(FEATURE_CSV)
    meta_cols = {"group", "label", "start_index", "end_index", "window_size"}
    feature_cols = [col for col in df.columns if col not in meta_cols]

    x = StandardScaler().fit_transform(df[feature_cols])
    pca = PCA(n_components=2, random_state=42)
    xy = pca.fit_transform(x)

    plt.figure(figsize=(8, 6))
    for group, part in df.assign(pc1=xy[:, 0], pc2=xy[:, 1]).groupby("group"):
        plt.scatter(part["pc1"], part["pc2"], s=38, alpha=0.8, label=group)
    plt.xlabel(f"PC1 ({pca.explained_variance_ratio_[0] * 100:.1f}%)")
    plt.ylabel(f"PC2 ({pca.explained_variance_ratio_[1] * 100:.1f}%)")
    plt.title("PCA visualization of CSI window features")
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "feature_pca.png", dpi=180)
    plt.close()

    print("Explained variance ratio:", pca.explained_variance_ratio_)
    print(f"Saved PCA figure: {FIG_DIR / 'feature_pca.png'}")


if __name__ == "__main__":
    main()
