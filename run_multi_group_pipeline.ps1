$ErrorActionPreference = "Stop"

Write-Host "Step 1/6: quality analysis"
python analyze_multi_group_csi.py

Write-Host "Step 2/6: feature extraction"
python build_csi_features.py

Write-Host "Step 3/6: PCA visualization"
python visualize_csi_features.py

Write-Host "Step 4/6: clustering analysis"
python cluster_csi_features.py

Write-Host "Step 5/6: pseudo-label group baseline"
python train_group_baseline.py

Write-Host "Step 6/6: stage manifest"
python make_stage_manifest.py

if (Test-Path "data\multi_group\labels.csv") {
    Write-Host "Real labels found. Training labeled CSI model."
    python train_labeled_csi_model.py
} else {
    Write-Host "No data\multi_group\labels.csv found. Skipping real supervised model."
    Write-Host "Fill data\multi_group\labels_template.csv and save it as labels.csv before running train_labeled_csi_model.py."
}
