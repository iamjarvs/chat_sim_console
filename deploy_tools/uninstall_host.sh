#!/usr/bin/env bash
# Run FROM the jump host, same as push_to_host.sh. Removes the console from
# one compute node: stops + disables the service, deletes the code and the
# context file. Safe to re-run.
set -euo pipefail

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR)

SERVER_NAME="${1:?Usage: uninstall_host.sh <server-name>}"

ALIAS_LINE=$(grep "alias ${SERVER_NAME}=" ~/.bash_aliases || true)
[ -n "$ALIAS_LINE" ] || { echo "No alias found for '${SERVER_NAME}' in ~/.bash_aliases" >&2; exit 1; }
TARGET_IP=$(echo "$ALIAS_LINE" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+')
echo "==> Uninstalling from ${SERVER_NAME} (${TARGET_IP})"

ssh "${SSH_OPTS[@]}" root@"${TARGET_IP}" '
systemctl stop meridian-console 2>/dev/null || true
systemctl disable meridian-console 2>/dev/null || true
rm -f /etc/systemd/system/meridian-console.service
systemctl daemon-reload
rm -rf /opt/meridian-console /etc/meridian-console
echo "Uninstalled."
'
