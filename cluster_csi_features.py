#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run unsupervised clustering on CSI window-level features."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler


DATA_DIR = Path("data/multi_group")
FEATURE_CSV = DATA_DIR / "features" / "csi_features.csv"
FIG_DIR = DATA_DIR / "figures"
OUT_DIR = DATA_DIR / "features"


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(FEATURE_CSV)
    meta_cols = {"group", "label", "start_index", "end_index", "window_size"}
    feature_cols = [col for col in df.columns if col not in meta_cols]

    x = StandardScaler().fit_transform(df[feature_cols])
    k = df["group"].nunique()
    model = KMeans(n_clusters=k, random_state=42, n_init=50)
    clusters = model.fit_predict(x)

    result = df[["group", "start_index", "end_index"]].copy()
    result["cluster"] = clusters
    result.to_csv(OUT_DIR / "cluster_result.csv", index=False, encoding="utf-8-sig")

    crosstab = pd.crosstab(result["group"], result["cluster"])
    crosstab.to_csv(OUT_DIR / "cluster_group_crosstab.csv", encoding="utf-8-sig")

    sil = silhouette_score(x, clusters)
    ari = adjusted_rand_score(result["group"], clusters)
    metrics = pd.DataFrame(
        [{"n_clusters": k, "silhouette_score": sil, "adjusted_rand_index_vs_group": ari}]
    )
    metrics.to_csv(OUT_DIR / "cluster_metrics.csv", index=False, encoding="utf-8-sig")

    xy = PCA(n_components=2, random_state=42).fit_transform(x)
    plot_df = result.assign(pc1=xy[:, 0], pc2=xy[:, 1])

    plt.figure(figsize=(8, 6))
    for cluster, part in plot_df.groupby("cluster"):
        plt.scatter(part["pc1"], part["pc2"], s=42, alpha=0.8, label=f"cluster {cluster}")
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.title("KMeans clusters of CSI window features")
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "feature_kmeans_clusters.png", dpi=180)
    plt.close()

    print(metrics.to_string(index=False))
    print("\nCluster-group crosstab:")
    print(crosstab.to_string())
    print(f"\nSaved clustering outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
