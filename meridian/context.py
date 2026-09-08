"""Resolves and caches what the console shows in its header: tenant name,
environment name, this host's Netris identity, and GPU inventory.

Resolved once at startup (in the constructor, so the very first request
already has real data if the network cooperates) and then refreshed on a
background thread — never inline in a request, since Netris/SSH calls can
be slow or briefly unreachable and the demo must keep rendering regardless.
Any failure here is logged and falls back to the last-known-good state,
never raised past this module.
"""
from __future__ import annotations

import logging
import socket
import threading
import time

from meridian import gpu_detect
from meridian.config import Config
from meridian.netris_client import NetrisClient, NetrisError
from meridian.ssh_alias import resolve_own_server_name

logger = logging.getLogger("meridian.context")

REFRESH_SECONDS = 300


class ConsoleContext:
    def __init__(self, config: Config):
        self.config = config
        self._lock = threading.Lock()
        self._state = self._base_state()
        self._resolve_once()
        threading.Thread(target=self._refresh_loop, daemon=True, name="meridian-context-refresh").start()

    def _base_state(self) -> dict:
        gpus = gpu_detect.detect_gpus()
        return {
            "tenant_name": self.config.tenant_display_name,
            "environment_name": "Resolving…",
            "host_label": socket.gethostname(),
            "gpu_count": len(gpus) if gpus else self.config.gpus_per_server,
            "gpu_model": gpus[0]["name"] if gpus else "Simulated GPU",
            "resolved": False,
        }

    def _resolve_once(self) -> None:
        with self._lock:
            state = dict(self._state)

        gpus = gpu_detect.detect_gpus()
        if gpus:
            state["gpu_count"] = len(gpus)
            state["gpu_model"] = gpus[0]["name"]

        server_name = None
        if self.config.ssh_jump_host and self.config.ssh_jump_username:
            try:
                server_name = resolve_own_server_name(
                    self.config.ssh_jump_host,
                    self.config.ssh_jump_port,
                    self.config.ssh_jump_username,
                    self.config.ssh_jump_password,
                )
            except Exception:
                logger.warning("Could not resolve this host's Netris server name", exc_info=True)

        if server_name:
            state["host_label"] = server_name
            if self.config.netris_base_url and self.config.netris_username:
                try:
                    client = NetrisClient(
                        self.config.netris_base_url,
                        self.config.netris_username,
                        self.config.netris_password,
                        self.config.netris_verify_ssl,
                    )
                    client.login()
                    env_name = client.find_environment_for_server(server_name)
                    state["environment_name"] = env_name or "Unassigned"
                    state["resolved"] = True
                except NetrisError:
                    logger.warning("Netris lookup failed", exc_info=True)
                    if not state["resolved"]:
                        state["environment_name"] = "Unavailable"
        elif not state["resolved"]:
            state["environment_name"] = "Unknown"

        with self._lock:
            self._state = state

    def _refresh_loop(self) -> None:
        while True:
            time.sleep(REFRESH_SECONDS)
            try:
                self._resolve_once()
            except Exception:
                logger.exception("Context refresh failed, keeping last known state")

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._state)
