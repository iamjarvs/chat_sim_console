"""Resolves this host's own Netris server name.

The Netris-visible name for a physical box (e.g. `hgx-pod00-su0-h00`) isn't
its real Linux hostname — it only exists as a `hgx-*` bash alias on the SSH
jump host, mapping that name to the box's real IP (the same reachability
quirk the Portal's own app/ssh_client.py works around). This inverts that:
find every local IP this host actually has, then find which alias on the
jump host maps to one of them.
"""
from __future__ import annotations

import logging
import re
import socket
import subprocess

import paramiko

logger = logging.getLogger("meridian.ssh")

_ALIAS_RE = re.compile(r"alias (hgx-\S+)='ssh .*?root@([0-9.]+)'")


def resolve_aliases(host: str, port: int, username: str, password: str | None) -> dict[str, str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=username, password=password, timeout=10)
    try:
        # `timeout` here bounds the *channel* (a stuck `bash -i` waiting on a
        # banner/motd/tty would otherwise hang the read forever) — the
        # connect() timeout above only bounds the TCP handshake, not this.
        _, stdout, _ = client.exec_command("bash -i -c alias 2>/dev/null", timeout=10)
        output = stdout.read().decode(errors="ignore")
    finally:
        client.close()

    mapping: dict[str, str] = {}
    for line in output.splitlines():
        m = _ALIAS_RE.match(line.strip())
        if m:
            mapping[m.group(1)] = m.group(2)
    return mapping


def local_ips() -> set[str]:
    ips: set[str] = set()
    try:
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5)
        ips.update(result.stdout.split())
    except Exception:
        logger.debug("`hostname -I` unavailable", exc_info=True)
    try:
        ips.add(socket.gethostbyname(socket.gethostname()))
    except Exception:
        logger.debug("gethostbyname(gethostname()) failed", exc_info=True)
    return ips


def resolve_own_server_name(host: str, port: int, username: str, password: str | None) -> str | None:
    aliases = resolve_aliases(host, port, username, password)
    mine = local_ips()
    for name, ip in aliases.items():
        if ip in mine:
            return name
    return None
