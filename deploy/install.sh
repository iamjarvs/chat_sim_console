#!/usr/bin/env bash
# Installs the Meridian demo console on this host: pulls the code, fetches
# Netris + SSH credentials from the Provider Portal, and runs it behind Caddy
# with a self-signed cert (Caddy's `tls internal`). Safe to re-run — it
# re-pulls the code and credentials and restarts the service.
set -euo pipefail

REPO_URL="${MERIDIAN_REPO_URL:-git@github.com:iamjarvs/chat_sim_console.git}"
INSTALL_DIR="/opt/meridian-console"
CONFIG_DIR="/etc/meridian-console"
SERVICE_NAME="meridian-console"
APP_PORT="${MERIDIAN_PORT:-8765}"

usage() {
  cat <<USAGE
Usage: $0 <portal-url> [operator-username] [operator-password]

  <portal-url>          Base URL of the Provider Portal, e.g. https://portal.example.com
  [operator-username]   Falls back to \$OPERATOR_USERNAME, then prompts
  [operator-password]   Falls back to \$OPERATOR_PASSWORD, then prompts (hidden input)

Must be run as root (it writes systemd units and /etc/caddy config).
USAGE
  exit 1
}

[ "$(id -u)" = "0" ] || { echo "Run as root (sudo)." >&2; exit 1; }
[ $# -ge 1 ] || usage

PORTAL_URL="${1%/}"
OPERATOR_USER="${2:-${OPERATOR_USERNAME:-}}"
OPERATOR_PASS="${3:-${OPERATOR_PASSWORD:-}}"

if [ -z "$OPERATOR_USER" ]; then
  read -rp "Operator username: " OPERATOR_USER
fi
if [ -z "$OPERATOR_PASS" ]; then
  read -rsp "Operator password: " OPERATOR_PASS
  echo
fi

echo "==> Fetching credentials from ${PORTAL_URL}"
mkdir -p "$CONFIG_DIR"
HTTP_CODE=$(curl -sk -o "$CONFIG_DIR/config.json" -w "%{http_code}" \
  -u "${OPERATOR_USER}:${OPERATOR_PASS}" \
  "${PORTAL_URL}/ops/api/device-credentials")
if [ "$HTTP_CODE" != "200" ]; then
  echo "Failed to fetch credentials (HTTP ${HTTP_CODE}) — check the portal URL and operator login." >&2
  rm -f "$CONFIG_DIR/config.json"
  exit 1
fi
chmod 600 "$CONFIG_DIR/config.json"
unset OPERATOR_PASS

echo "==> Fetching code"
if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" fetch --depth 1 origin
  git -C "$INSTALL_DIR" reset --hard origin/HEAD
else
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

echo "==> Python environment"
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

echo "==> Caddy (self-signed HTTPS via 'tls internal')"
if ! command -v caddy >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl gnupg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
      | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
      | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    apt-get update -qq
    apt-get install -y -qq caddy
  else
    echo "caddy isn't installed and this isn't a Debian/Ubuntu host." >&2
    echo "Install caddy manually (https://caddyserver.com/docs/install), then re-run this script." >&2
    exit 1
  fi
fi

mkdir -p /etc/caddy/sites
cat > /etc/caddy/sites/meridian-console.caddy <<EOF
:443 {
    tls internal
    reverse_proxy 127.0.0.1:${APP_PORT}
}
EOF
touch /etc/caddy/Caddyfile
if ! grep -qF "import sites/*.caddy" /etc/caddy/Caddyfile; then
  echo "import sites/*.caddy" >> /etc/caddy/Caddyfile
fi
systemctl enable caddy >/dev/null 2>&1 || true
systemctl reload caddy 2>/dev/null || systemctl restart caddy

echo "==> systemd service"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Meridian demo console
After=network.target

[Service]
Type=simple
ExecStart=${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/server.py
WorkingDirectory=${INSTALL_DIR}
Environment=MERIDIAN_CONFIG=${CONFIG_DIR}/config.json
Environment=MERIDIAN_PORT=${APP_PORT}
Restart=on-failure
RestartSec=2
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}" >/dev/null
systemctl restart "${SERVICE_NAME}"

HOSTNAME_LABEL="$(hostname -f 2>/dev/null || hostname)"
echo
echo "==> Done. Meridian console running at https://${HOSTNAME_LABEL}"
echo "    Self-signed certificate — your browser will warn once on first visit, that's expected."
echo "    Logs: journalctl -u ${SERVICE_NAME} -f"
