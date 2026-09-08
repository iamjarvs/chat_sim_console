"""Minimal, read-only Netris controller client.

Deliberately a small subset of what the Provider Portal's own
app/netris/client.py can do — this console only ever needs to log in and
look up which cluster a server belongs to, never to create or delete
anything. Field names (data.user_id, server.name/site/serverClusterID,
cluster.id/name) are confirmed against a live controller.
"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger("meridian.netris")


class NetrisError(Exception):
    pass


class NetrisClient:
    def __init__(self, base_url: str, username: str, password: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self._username = username
        self._password = password

    def login(self) -> None:
        try:
            resp = self.session.post(
                f"{self.base_url}/api/auth",
                json={"user": self._username, "password": self._password, "auth_scheme_id": 1},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise NetrisError(f"Could not reach Netris controller: {exc}") from exc
        if resp.status_code >= 400:
            raise NetrisError(f"Netris login failed (HTTP {resp.status_code})")

    def _get_json(self, path: str, action: str) -> dict:
        try:
            resp = self.session.get(f"{self.base_url}{path}", timeout=15)
        except requests.RequestException as exc:
            raise NetrisError(f"{action} failed: could not reach Netris controller: {exc}") from exc
        if resp.status_code >= 400:
            raise NetrisError(f"{action} failed (HTTP {resp.status_code})")
        try:
            return resp.json() or {}
        except ValueError as exc:
            # A reachable-but-wrong endpoint (proxy/maintenance page, expired
            # session redirected to HTML) still returns 200 with a non-JSON
            # body — surface that as a NetrisError like every other failure
            # mode here, instead of letting a raw JSONDecodeError escape.
            raise NetrisError(f"{action} returned a non-JSON response") from exc

    def list_servers(self) -> list[dict]:
        return self._get_json("/api/v2/server-cluster/servers", "List servers").get("data") or []

    def list_clusters(self) -> list[dict]:
        return self._get_json("/api/v2/server-cluster", "List clusters").get("data") or []

    def find_environment_for_server(self, server_name: str) -> str | None:
        """Returns the owning cluster's name (== the Portal's environment
        name — confirmed the Portal sets them equal on create), or None if
        the server isn't currently attached to any cluster."""
        servers = self.list_servers()
        cluster_id = next(
            (s.get("serverClusterID") for s in servers if s.get("name") == server_name and s.get("serverClusterID")),
            None,
        )
        if cluster_id is None:
            return None
        clusters = self.list_clusters()
        cluster = next((c for c in clusters if c.get("id") == cluster_id), None)
        return cluster.get("name") if cluster else None
