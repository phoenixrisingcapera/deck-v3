#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
exec env APP_ROLE="${APP_ROLE:-worker}" python scripts/deck_processing_worker.py
