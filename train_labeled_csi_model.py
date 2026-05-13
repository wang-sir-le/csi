#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Train a supervised CSI classifier after real labels are provided.

Before running this script, copy or edit:
    data/multi_group/labels_template.csv
and fill the label column with real action/state labels.
"""

from pathlib import Path
import json

import matplotlib.pyplot as plt
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
)
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DATA_DIR = Path("data/multi_group")
FEATURE_CSV = DATA_DIR / "features" / "csi_features.csv"
LABEL_CANDIDATES = [DATA_DIR / "labels.csv", DATA_DIR / "labels_template.csv"]
OUT_DIR = DATA_DIR / "features"
FIG_DIR = DATA_DIR / "figures"
MODEL_DIR = DATA_DIR / "models"
MODEL_PATH = MODEL_DIR / "csi_state_classifier.joblib"
MODEL_META_PATH = MODEL_DIR / "csi_state_classifier_meta.json"


def find_label_file() -> Path:
    for path in LABEL_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("No labels.csv or labels_template.csv found.")


def load_labeled_features() -> tuple[pd.DataFrame, list[str]]:
    features = pd.read_csv(FEATURE_CSV)
    labels_path = find_label_file()
    labels = pd.read_csv(labels_path)

    required = {"group", "label"}
    if not required.issubset(labels.columns):
        raise ValueError("Label file must contain columns: group,label")

    labels["label"] = labels["label"].astype(str).str.strip()
    invalid = labels["label"].isin(["", "待填写", "nan", "None"])
    if invalid.any():
        missing_groups = labels.loc[invalid, "group"].tolist()
        raise ValueError(
            "真实标签尚未填写，无法训练监督模型。请先填写这些组的 label: "
            + ", ".join(missing_groups)
        )

    merged = features.merge(labels[["group", "label"]], on="group", how="left", suffixes=("", "_real"))
    if merged["label_real"].isna().any():
        missing_groups = sorted(merged.loc[merged["label_real"].isna(), "group"].unique())
        raise ValueError("标签表缺少这些组: " + ", ".join(missing_groups))

    merged["label"] = merged["label_real"]
    merged = merged.drop(columns=["label_real"])

    meta_cols = {"group", "label", "start_index", "end_index", "window_size"}
    feature_cols = [col for col in merged.columns if col not in meta_cols]
    return merged, feature_cols


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    df, feature_cols = load_labeled_features()
    x = df[feature_cols]
    y = df["label"]
    groups = df["group"]

    min_class_count = int(y.value_counts().min())
    n_groups = int(groups.nunique())
    if y.nunique() < 2:
        raise ValueError("至少需要两个不同类别才能训练分类模型。")
    if min_class_count < 3:
        raise ValueError("每个类别至少建议有 3 个窗口样本，当前最小类别样本数不足。")

    clf = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=500,
                    min_samples_leaf=2,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )

    n_splits = min(5, n_groups)
    cv = GroupKFold(n_splits=n_splits)
    y_pred = cross_val_predict(clf, x, y, cv=cv, groups=groups)

    report = pd.DataFrame(classification_report(y, y_pred, output_dict=True, zero_division=0)).T
    metrics = pd.DataFrame(
        [
            {
                "accuracy": accuracy_score(y, y_pred),
                "macro_f1": report.loc["macro avg", "f1-score"],
                "n_classes": y.nunique(),
                "n_samples": len(y),
                "n_groups": n_groups,
                "cv_splits": n_splits,
                "cv_method": "GroupKFold",
            }
        ]
    )

    metrics.to_csv(OUT_DIR / "labeled_model_metrics.csv", index=False, encoding="utf-8-sig")
    report.to_csv(OUT_DIR / "labeled_model_classification_report.csv", encoding="utf-8-sig")

    ConfusionMatrixDisplay.from_predictions(y, y_pred, xticks_rotation=45, cmap="Blues")
    plt.title("Labeled CSI classification confusion matrix")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "labeled_model_confusion_matrix.png", dpi=180)
    plt.close()

    clf.fit(x, y)
    model_bundle = {
        "model": clf,
        "feature_cols": feature_cols,
        "labels": sorted(y.unique().tolist()),
    }
    joblib.dump(model_bundle, MODEL_PATH)
    with MODEL_META_PATH.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "model_path": str(MODEL_PATH),
                "feature_cols": feature_cols,
                "labels": sorted(y.unique().tolist()),
                "n_classes": int(y.nunique()),
                "n_samples": int(len(y)),
                "n_groups": int(n_groups),
                "cv_method": "GroupKFold",
                "accuracy": float(metrics.loc[0, "accuracy"]),
                "macro_f1": float(metrics.loc[0, "macro_f1"]),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    importance = pd.DataFrame(
        {
            "feature": feature_cols,
            "importance": clf.named_steps["rf"].feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    importance.to_csv(OUT_DIR / "labeled_model_feature_importance.csv", index=False, encoding="utf-8-sig")

    top = importance.head(15).iloc[::-1]
    plt.figure(figsize=(8, 6))
    plt.barh(top["feature"], top["importance"])
    plt.xlabel("Importance")
    plt.title("Labeled CSI model feature importance")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "labeled_model_feature_importance.png", dpi=180)
    plt.close()

    print(metrics.to_string(index=False))
    print("\nClassification report:")
    print(report.round(3).to_string())
    print(f"\nSaved model: {MODEL_PATH}")


if __name__ == "__main__":
    main()
