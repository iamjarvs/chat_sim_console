"""Run once per host, from somewhere with real connectivity (the Netris
controller box, in this fleet), to produce the context.json a compute node
will read at runtime. The node itself can't do this lookup — see the
top-level README for why.

Usage:
    echo '<device-credentials JSON>' | python3 resolve_context.py <server-name>

Reads the Portal's /ops/api/device-credentials response (or an equivalent
JSON object with the same keys) from stdin, and prints context.json to
stdout.
"""
from __future__ import annotations

import json
import sys

from netris_client import NetrisClient


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1
    server_name = sys.argv[1]
    creds = json.load(sys.stdin)

    client = NetrisClient(
        creds["netris_base_url"],
        creds["netris_username"],
        creds["netris_password"],
        verify_ssl=bool(creds.get("netris_verify_ssl", True)),
    )
    client.login()
    environment_name = client.find_environment_for_server(server_name) or "Unassigned"

    print(json.dumps({
        "tenant_name": creds.get("tenant_display_name") or "Demo Tenant",
        "environment_name": environment_name,
        "host_label": server_name,
        "gpus_per_server": int(creds.get("gpus_per_server") or 8),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
