#!/usr/bin/env bash
# Instala o Liquido neste servidor (systemd + Tailscale). Pode ser executado de novo sem problemas.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="${SUDO_USER:-$(id -un)}"
UNIT_DST="/etc/systemd/system/liquido.service"

erro() { echo "ERRO: $*" >&2; exit 1; }
info() { echo "==> $*"; }

if [ "$(id -u)" -eq 0 ] && [ -z "${SUDO_USER:-}" ]; then
  erro "não execute como root. Rode como o seu usuário; o script pede sudo só quando precisa."
fi

command -v uv >/dev/null 2>&1 || erro "'uv' não encontrado. Instale em https://docs.astral.sh/uv/ e rode de novo."
command -v node >/dev/null 2>&1 || erro "'node' não encontrado. Instale o Node.js 20 ou mais novo."
command -v npm >/dev/null 2>&1 || erro "'npm' não encontrado. Ele vem junto com o Node.js."
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[ "$NODE_MAJOR" -ge 20 ] || erro "Node.js $NODE_MAJOR é muito antigo; é preciso a versão 20 ou mais nova."
command -v tailscale >/dev/null 2>&1 || erro "'tailscale' não encontrado. Instale em https://tailscale.com/download e entre na sua conta (tailscale up)."
command -v curl >/dev/null 2>&1 || erro "'curl' não encontrado. Instale-o (ex.: sudo apt install curl)."
command -v systemctl >/dev/null 2>&1 || erro "'systemctl' não encontrado: este script precisa de systemd."

info "Instalando dependências do backend"
(cd "$APP_DIR/backend" && uv sync --frozen)

info "Instalando dependências e gerando o frontend"
(cd "$APP_DIR/frontend" && npm ci && npm run build)

info "Instalando o serviço systemd (pede sudo)"
TMP_UNIT="$(mktemp)"
trap 'rm -f "$TMP_UNIT"' EXIT
sed -e "s|{APP_DIR}|$APP_DIR|g" -e "s|{USER}|$APP_USER|g" "$APP_DIR/deploy/liquido.service" > "$TMP_UNIT"
sudo install -m 644 "$TMP_UNIT" "$UNIT_DST"
sudo systemctl daemon-reload
sudo systemctl enable --now liquido
sudo systemctl restart liquido

info "Aguardando o serviço responder"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
[ "$ok" -eq 1 ] || erro "o serviço não respondeu em 30s. Veja: journalctl -u liquido -n 50"

info "Publicando na sua rede Tailscale (pede sudo)"
sudo tailscale serve --bg 8000

URL=""
if command -v python3 >/dev/null 2>&1; then
  DNS="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null)" || DNS=""
  [ -n "$DNS" ] && URL="https://$DNS"
fi

echo
echo "Pronto! O Liquido está no ar."
if [ -n "$URL" ]; then
  echo "Abra no celular ou no computador (conectado ao Tailscale): $URL"
else
  echo "Rode 'tailscale serve status' para ver o endereço https://<maquina>.<rede>.ts.net"
fi
