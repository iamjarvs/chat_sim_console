"""Loads the config.json that install.sh writes from the Portal's
/ops/api/device-credentials response. Missing entirely (e.g. running the
app straight from a checkout for local development) falls back to a demo
config rather than refusing to start.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

DEFAULT_CONFIG_PATH = "/etc/meridian-console/config.json"


@dataclass(frozen=True)
class Config:
    netris_base_url: str | None
    netris_username: str | None
    netris_password: str | None
    netris_verify_ssl: bool
    ssh_jump_host: str | None
    ssh_jump_port: int
    ssh_jump_username: str | None
    ssh_jump_password: str | None
    tenant_display_name: str
    gpus_per_server: int


def _demo_config() -> Config:
    return Config(
        netris_base_url=None,
        netris_username=None,
        netris_password=None,
        netris_verify_ssl=True,
        ssh_jump_host=None,
        ssh_jump_port=22,
        ssh_jump_username=None,
        ssh_jump_password=None,
        tenant_display_name="Demo Tenant",
        gpus_per_server=8,
    )


def load_config() -> Config:
    path = os.environ.get("MERIDIAN_CONFIG", DEFAULT_CONFIG_PATH)
    if not os.path.exists(path):
        return _demo_config()

    with open(path) as f:
        data = json.load(f)

    return Config(
        netris_base_url=data.get("netris_base_url"),
        netris_username=data.get("netris_username"),
        netris_password=data.get("netris_password"),
        netris_verify_ssl=bool(data.get("netris_verify_ssl", True)),
        ssh_jump_host=data.get("ssh_jump_host"),
        ssh_jump_port=int(data.get("ssh_jump_port") or 22),
        ssh_jump_username=data.get("ssh_jump_username"),
        ssh_jump_password=data.get("ssh_jump_password"),
        tenant_display_name=data.get("tenant_display_name") or "Demo Tenant",
        gpus_per_server=int(data.get("gpus_per_server") or 8),
    )
