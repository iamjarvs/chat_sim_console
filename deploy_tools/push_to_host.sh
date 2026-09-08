#!/usr/bin/env bash
# Run this FROM the Netris controller / jump host (or anywhere with both
# real internet access and the fleet's `hgx-*` SSH aliases) — the compute
# nodes themselves have no outbound path to Netris, the Portal, or the
# internet, so all of that has to happen here instead, once per host.
#
# Usage:
#   push_to_host.sh <server-name> <portal-url> [operator-user] [operator-pass]
#
# Or, without a reachable Portal, set these in the environment instead:
#   NETRIS_BASE_URL, NETRIS_USERNAME, NETRIS_PASSWORD, NETRIS_VERIFY_SSL,
#   TENANT_DISPLAY_NAME, GPUS_PER_SERVER
#
# Safe to re-run for the same host (rebuilds/pushes in place) or a
# different one (the venv/cert build is cached and reused).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$HOME/.cache/meridian-console-build"
CERT_DIR="$HOME/.cache/meridian-console-cert"
SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR)

SERVER_NAME="${1:?Usage: push_to_host.sh <server-name> <portal-url> [operator-user] [operator-pass]}"
PORTAL_URL="${2:-}"
OPERATOR_USER="${3:-${OPERATOR_USERNAME:-}}"
OPERATOR_PASS="${4:-${OPERATOR_PASSWORD:-}}"

echo "==> Resolving ${SERVER_NAME}'s IP from ~/.bash_aliases"
ALIAS_LINE=$(grep "alias ${SERVER_NAME}=" ~/.bash_aliases || true)
[ -n "$ALIAS_LINE" ] || { echo "No alias found for '${SERVER_NAME}' in ~/.bash_aliases" >&2; exit 1; }
TARGET_IP=$(echo "$ALIAS_LINE" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+')
echo "    ${SERVER_NAME} -> ${TARGET_IP}"

CREDS_FILE="$(mktemp)"
trap 'rm -f "$CREDS_FILE"' EXIT

if [ -n "${NETRIS_BASE_URL:-}" ]; then
  echo "==> Using Netris credentials from the environment"
  python3 -c '
import json, os
print(json.dumps({
  "netris_base_url": os.environ["NETRIS_BASE_URL"],
  "netris_username": os.environ.get("NETRIS_USERNAME", ""),
  "netris_password": os.environ.get("NETRIS_PASSWORD", ""),
  "netris_verify_ssl": os.environ.get("NETRIS_VERIFY_SSL", "true").lower() == "true",
  "tenant_display_name": os.environ.get("TENANT_DISPLAY_NAME", "Demo Tenant"),
  "gpus_per_server": int(os.environ.get("GPUS_PER_SERVER", "8")),
}))' > "$CREDS_FILE"
else
  [ -n "$PORTAL_URL" ] || { echo "Provide a Portal URL, or set NETRIS_BASE_URL/etc in the environment." >&2; exit 1; }
  [ -n "$OPERATOR_USER" ] || read -rp "Operator username: " OPERATOR_USER
  if [ -z "$OPERATOR_PASS" ]; then read -rsp "Operator password: " OPERATOR_PASS; echo; fi
  echo "==> Fetching credentials from ${PORTAL_URL}"
  curl -sk -u "${OPERATOR_USER}:${OPERATOR_PASS}" "${PORTAL_URL%/}/ops/api/device-credentials" > "$CREDS_FILE"
fi

mkdir -p "$BUILD_DIR"

if [ ! -d "$BUILD_DIR/admin-venv" ]; then
  echo "==> Building the one-off admin (resolver) venv"
  python3 -m venv "$BUILD_DIR/admin-venv"
  "$BUILD_DIR/admin-venv/bin/pip" install --quiet -r "$REPO_DIR/deploy_tools/requirements.txt"
fi

echo "==> Resolving environment for ${SERVER_NAME}"
"$BUILD_DIR/admin-venv/bin/python" "$REPO_DIR/deploy_tools/resolve_context.py" "$SERVER_NAME" \
  < "$CREDS_FILE" > "$BUILD_DIR/context.json"
cat "$BUILD_DIR/context.json"

if [ ! -d "$BUILD_DIR/app-venv" ]; then
  echo "==> Building the app venv (pure-Python Flask — portable to any compute node)"
  python3 -m venv "$BUILD_DIR/app-venv"
  "$BUILD_DIR/app-venv/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"
fi

if [ ! -f "$CERT_DIR/cert.pem" ]; then
  echo "==> Generating a self-signed cert (shared across all hosts)"
  mkdir -p "$CERT_DIR"
  openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
    -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" \
    -subj "/CN=meridian-console" >/dev/null 2>&1
fi

STAGE_DIR="$BUILD_DIR/stage"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
cp -r "$REPO_DIR/server.py" "$REPO_DIR/meridian" "$REPO_DIR/static" "$STAGE_DIR/"
cp -r "$BUILD_DIR/app-venv" "$STAGE_DIR/.venv"
cp "$CERT_DIR/cert.pem" "$CERT_DIR/key.pem" "$STAGE_DIR/"
find "$STAGE_DIR" -name "__pycache__" -type d -exec rm -rf {} +

echo "==> Pushing to ${SERVER_NAME} (${TARGET_IP})"
ssh "${SSH_OPTS[@]}" root@"${TARGET_IP}" 'mkdir -p /opt/meridian-console /etc/meridian-console'
tar -C "$STAGE_DIR" -cf - . | ssh "${SSH_OPTS[@]}" root@"${TARGET_IP}" 'tar -C /opt/meridian-console -xf -'
cat "$BUILD_DIR/context.json" | ssh "${SSH_OPTS[@]}" root@"${TARGET_IP}" 'cat > /etc/meridian-console/context.json'

echo "==> Installing systemd unit and starting the service"
ssh "${SSH_OPTS[@]}" root@"${TARGET_IP}" bash -s <<'REMOTE'
set -euo pipefail
cat > /etc/systemd/system/meridian-console.service <<'EOF'
[Unit]
Description=Meridian demo console
After=network.target

[Service]
Type=simple
ExecStart=/opt/meridian-console/.venv/bin/python /opt/meridian-console/server.py
WorkingDirectory=/opt/meridian-console
Environment=MERIDIAN_CONTEXT=/etc/meridian-console/context.json
Environment=MERIDIAN_PORT=443
Environment=MERIDIAN_TLS_CERT=/opt/meridian-console/cert.pem
Environment=MERIDIAN_TLS_KEY=/opt/meridian-console/key.pem
Restart=on-failure
RestartSec=2
User=root

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable meridian-console >/dev/null
systemctl restart meridian-console
sleep 1
systemctl is-active meridian-console
curl -sk -o /dev/null -w "local check: HTTP %{http_code}\n" https://127.0.0.1/api/context
REMOTE

echo
echo "==> Done. https://${TARGET_IP} (self-signed cert — browser will warn once)"
