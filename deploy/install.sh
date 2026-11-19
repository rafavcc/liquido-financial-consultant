#!/usr/bin/env bash
# Instala o Liquido neste servidor (systemd + Tailscale). Pode ser executado de novo sem problemas.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="${SUDO_USER:-$(id -un)}"
UNIT_DST="/etc/systemd/system/liquido.service"
# Porta local do serviço (só em 127.0.0.1). Troque com: LIQUIDO_PORT=9000 ./deploy/install.sh
PORT="${LIQUIDO_PORT:-8456}"

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
[[ "$PORT" =~ ^[0-9]+$ ]] || erro "LIQUIDO_PORT inválida: $PORT"

# A porta precisa estar livre (ou já ser do próprio Liquido, numa reinstalação).
if ! systemctl is-active --quiet liquido 2>/dev/null && curl -s -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null; then
  erro "a porta $PORT já está em uso por outro serviço. Escolha outra: LIQUIDO_PORT=9000 $0"
fi

info "Instalando dependências do backend"
(cd "$APP_DIR/backend" && uv sync --frozen)

info "Instalando dependências e gerando o frontend"
(cd "$APP_DIR/frontend" && npm ci && npm run build)

info "Instalando o serviço systemd (pede sudo)"
TMP_UNIT="$(mktemp)"
trap 'rm -f "$TMP_UNIT"' EXIT
sed -e "s|{APP_DIR}|$APP_DIR|g" -e "s|{USER}|$APP_USER|g" -e "s|{PORT}|$PORT|g" "$APP_DIR/deploy/liquido.service" > "$TMP_UNIT"
sudo install -m 644 "$TMP_UNIT" "$UNIT_DST"
sudo systemctl daemon-reload
sudo systemctl enable --now liquido
sudo systemctl restart liquido

info "Aguardando o serviço responder"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null | grep -q '"status":"ok"'; then ok=1; break; fi
  sleep 1
done
[ "$ok" -eq 1 ] || erro "o serviço não respondeu em 30s. Veja: journalctl -u liquido -n 50"

info "Publicando na sua rede Tailscale (pede sudo)"
# Se o endereço https padrão (porta 443) já publica outro serviço, não o sobrescreve:
# o Liquido fica em https://<maquina>.<rede>.ts.net:$PORT
HTTPS_PORT=443
if command -v python3 >/dev/null 2>&1; then
  OCUPADO="$(sudo tailscale serve status --json 2>/dev/null | python3 -c '
import json, sys
port = sys.argv[1]
try:
    cfg = json.load(sys.stdin)
except Exception:
    sys.exit()
for host, web in (cfg.get("Web") or {}).items():
    if host.endswith(":443"):
        alvos = [h.get("Proxy", "") for h in (web.get("Handlers") or {}).values()]
        if any(not a.endswith(":" + port) for a in alvos):
            print("sim")
' "$PORT" 2>/dev/null)" || OCUPADO=""
  [ "$OCUPADO" = "sim" ] && HTTPS_PORT="$PORT"
else
  HTTPS_PORT="$PORT"
fi
sudo tailscale serve --bg --https="$HTTPS_PORT" "http://127.0.0.1:$PORT"

URL=""
if command -v python3 >/dev/null 2>&1; then
  DNS="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null)" || DNS=""
  if [ -n "$DNS" ]; then
    URL="https://$DNS"
    [ "$HTTPS_PORT" = "443" ] || URL="$URL:$HTTPS_PORT"
  fi
fi

echo
echo "Pronto! O Liquido está no ar."
if [ -n "$URL" ]; then
  echo "Abra no celular ou no computador (conectado ao Tailscale): $URL"
else
  echo "Rode 'tailscale serve status' para ver o endereço https://<maquina>.<rede>.ts.net"
fi
