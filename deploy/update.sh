#!/usr/bin/env bash
# Atualiza o Liquido para a versão mais nova do repositório.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

git pull --ff-only
(cd backend && uv sync --frozen)
(cd frontend && npm ci && npm run build)
sudo systemctl restart liquido

ok=0
for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8000/api/health; then ok=1; break; fi
  sleep 1
done
echo
[ "$ok" -eq 1 ] || { echo "ERRO: o serviço não respondeu. Veja: journalctl -u liquido -n 50" >&2; exit 1; }
echo "Atualizado."
