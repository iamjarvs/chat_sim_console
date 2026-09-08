"""Loads the static context.json a deploy pushes onto this specific host.

No live Netris/SSH calls happen here on purpose: this fleet's compute nodes
have no outbound network path to either the Netris controller or the jump
host (confirmed by hand against a real host — see deploy_tools/ for where
that resolution actually happens instead, once, at push time, from the jump
host, which does have the connectivity this box doesn't).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("meridian.config")

DEFAULT_CONTEXT_PATH = "/etc/meridian-console/context.json"


@dataclass(frozen=True)
class StaticContext:
    tenant_name: str
    environment_name: str
    host_label: str
    gpus_per_server: int


def _demo_context() -> StaticContext:
    return StaticContext(
        tenant_name="Demo Tenant",
        environment_name="Unknown",
        host_label="local-dev",
        gpus_per_server=8,
    )


def load_static_context() -> StaticContext:
    path = os.environ.get("MERIDIAN_CONTEXT", DEFAULT_CONTEXT_PATH)
    if not os.path.exists(path):
        return _demo_context()

    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        # A truncated/corrupt file must not crash the process at import
        # time — fall back the same as if the file were simply missing.
        logger.exception("Could not read/parse %s, starting in demo fallback", path)
        return _demo_context()

    return StaticContext(
        tenant_name=data.get("tenant_name") or "Demo Tenant",
        environment_name=data.get("environment_name") or "Unknown",
        host_label=data.get("host_label") or "unknown-host",
        gpus_per_server=int(data.get("gpus_per_server") or 8),
    )
