#!/usr/bin/env bash
# Atualiza o Liquido para a versão mais nova do repositório.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

git pull --ff-only
(cd backend && uv sync --frozen)
(cd frontend && npm ci && npm run build)
sudo systemctl restart liquido

# Usa a mesma porta configurada na instalação.
PORT="$(systemctl cat liquido 2>/dev/null | sed -n 's/.*--port \([0-9]\+\).*/\1/p' | head -1)"
PORT="${PORT:-8456}"

ok=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health"; then ok=1; break; fi
  sleep 1
done
echo
[ "$ok" -eq 1 ] || { echo "ERRO: o serviço não respondeu. Veja: journalctl -u liquido -n 50" >&2; exit 1; }
echo "Atualizado."
