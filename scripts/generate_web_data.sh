#!/usr/bin/env bash
# Regenera apenas o artefato do dashboard (web/wc_data.js) de forma padronizada.
# Uso:
#   scripts/generate_web_data.sh
#   SIMS=50000 ENGINE=ensemble scripts/generate_web_data.sh --live
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -x ".venv/bin/python" ]]; then
  PY="${PY:-.venv/bin/python}"
else
  PY="${PY:-python3}"
fi
ENGINE="${ENGINE:-ensemble}"
SIMS="${SIMS:-200000}"

"$PY" -m wc2026.export_web --engine "$ENGINE" --sims "$SIMS" "$@"
"$PY" - << 'PY'
from pathlib import Path
import json
p = Path('web/wc_data.js')
s = p.read_text()
if '<<<<<<<' in s or '>>>>>>>' in s or '=======' in s:
    raise SystemExit('web/wc_data.js contém marcadores de conflito')
json.loads(s.split('=', 1)[1].rsplit(';', 1)[0])
print('OK: web/wc_data.js válido')
PY
