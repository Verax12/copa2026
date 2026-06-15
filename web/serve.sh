#!/usr/bin/env bash
# Gera os dados do modelo e sobe o dashboard. Uso: ./web/serve.sh [args do export_web]
set -e
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
echo "Gerando dados do modelo..."
"$PY" -m wc2026.export_web "$@"
echo "Servindo em http://127.0.0.1:8765  (Ctrl+C para parar)"
exec "$PY" -m http.server 8765 --bind 127.0.0.1 --directory web
