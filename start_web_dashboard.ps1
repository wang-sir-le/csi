$ErrorActionPreference = "Stop"

if (-not $env:WIFI_SLEEP_DB_HOST) { $env:WIFI_SLEEP_DB_HOST = "127.0.0.1" }
if (-not $env:WIFI_SLEEP_DB_PORT) { $env:WIFI_SLEEP_DB_PORT = "3306" }
if (-not $env:WIFI_SLEEP_DB_USER) { $env:WIFI_SLEEP_DB_USER = "root" }
if (-not $env:WIFI_SLEEP_DB_PASSWORD) { $env:WIFI_SLEEP_DB_PASSWORD = "henu" }
if (-not $env:WIFI_SLEEP_DB_NAME) { $env:WIFI_SLEEP_DB_NAME = "wifi_sleep_monitor" }

python -B realtime_csi_web_dashboard.py `
  --port COM13 `
  --host 127.0.0.1 `
  --http_port 8000 `
  --model data\multi_group\models\csi_state_classifier.joblib `
  --window 128 `
  --step 64 `
  --smooth 5 `
  --min_confidence 0.60
