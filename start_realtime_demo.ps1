$ErrorActionPreference = "Stop"

python realtime_csi_state_monitor.py `
  --port COM13 `
  --duration 0 `
  --model data\multi_group\models\csi_state_classifier.joblib `
  --window 128 `
  --step 64 `
  --smooth 5 `
  --min_confidence 0.60
