"""Caches what the console shows in its header.

Tenant/environment/host label are baked once into context.json by the push
deploy (see deploy_tools/) and never re-fetched over the network from here
— this fleet's compute nodes have no outbound path to Netris or the jump
host. The only thing ever re-checked live is GPU count/model via a local
`nvidia-smi` call, which needs no network at all. The refresh loop still
re-reads context.json from disk periodically, so an operator can push an
updated context (e.g. the environment changed) and have it picked up
without restarting the service.
"""
from __future__ import annotations

import logging
import threading
import time

from meridian import gpu_detect
from meridian.config import StaticContext, load_static_context

logger = logging.getLogger("meridian.context")

REFRESH_SECONDS = 300


class ConsoleContext:
    def __init__(self, static_context: StaticContext):
        self.static_context = static_context
        self._lock = threading.Lock()
        self._state = self._build_state()
        threading.Thread(target=self._refresh_loop, daemon=True, name="meridian-context-refresh").start()

    def _build_state(self) -> dict:
        gpus = gpu_detect.detect_gpus()
        return {
            "tenant_name": self.static_context.tenant_name,
            "environment_name": self.static_context.environment_name,
            "host_label": self.static_context.host_label,
            "gpu_count": len(gpus) if gpus else self.static_context.gpus_per_server,
            "gpu_model": gpus[0]["name"] if gpus else "Simulated GPU",
            "resolved": True,
        }

    def _refresh_loop(self) -> None:
        while True:
            time.sleep(REFRESH_SECONDS)
            try:
                self.static_context = load_static_context()
                state = self._build_state()
                with self._lock:
                    self._state = state
            except Exception:
                logger.exception("Context refresh failed, keeping last known state")

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._state)
