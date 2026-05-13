#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Train a baseline classifier using group names as temporary pseudo-labels.

This script evaluates feature separability across collected groups. It should
not be interpreted as a real action-recognition model until group labels are
replaced by actual action or state labels.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
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

    x = df[feature_cols]
    y = df["group"]

    clf = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=None,
                    min_samples_leaf=2,
                    random_state=42,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    cv = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
    y_pred = cross_val_predict(clf, x, y, cv=cv)

    report_dict = classification_report(y, y_pred, output_dict=True, zero_division=0)
    report = pd.DataFrame(report_dict).T
    report.to_csv(OUT_DIR / "group_baseline_classification_report.csv", encoding="utf-8-sig")

    acc = accuracy_score(y, y_pred)
    metrics = pd.DataFrame([{"accuracy": acc, "macro_f1": report.loc["macro avg", "f1-score"]}])
    metrics.to_csv(OUT_DIR / "group_baseline_metrics.csv", index=False, encoding="utf-8-sig")

    ConfusionMatrixDisplay.from_predictions(y, y_pred, xticks_rotation=45, cmap="Blues")
    plt.title("Pseudo-label group baseline confusion matrix")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "group_baseline_confusion_matrix.png", dpi=180)
    plt.close()

    clf.fit(x, y)
    rf = clf.named_steps["rf"]
    importance = pd.DataFrame(
        {"feature": feature_cols, "importance": rf.feature_importances_}
    ).sort_values("importance", ascending=False)
    importance.to_csv(OUT_DIR / "group_baseline_feature_importance.csv", index=False, encoding="utf-8-sig")

    top = importance.head(15).iloc[::-1]
    plt.figure(figsize=(8, 6))
    plt.barh(top["feature"], top["importance"])
    plt.xlabel("Importance")
    plt.title("Top feature importance for pseudo-label group baseline")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "group_baseline_feature_importance.png", dpi=180)
    plt.close()

    print(metrics.to_string(index=False))
    print("\nClassification report:")
    print(report.round(3).to_string())
    print(f"\nSaved baseline outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
