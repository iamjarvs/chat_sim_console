#!/usr/bin/env bash
# Removes the Meridian console: stops and deletes the systemd service, its
# Caddy site block, the code checkout, and the pulled credentials. Safe to
# re-run — every step tolerates already being gone.
set -euo pipefail

INSTALL_DIR="/opt/meridian-console"
CONFIG_DIR="/etc/meridian-console"
SERVICE_NAME="meridian-console"

[ "$(id -u)" = "0" ] || { echo "Run as root (sudo)." >&2; exit 1; }

echo "==> Stopping service"
systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

echo "==> Removing Caddy site"
rm -f /etc/caddy/sites/meridian-console.caddy
systemctl reload caddy 2>/dev/null || true

echo "==> Removing code and credentials"
rm -rf "$INSTALL_DIR"
rm -rf "$CONFIG_DIR"

echo "==> Meridian console uninstalled."
