"""Meridian console — a lightweight Flask app serving a static chat UI plus
one small JSON endpoint for real (but deploy-time-resolved) tenant,
environment and GPU context. Nothing here calls a real model, and nothing
here calls out over the network at runtime — this fleet's compute nodes
have no outbound path to Netris or the jump host, so context is baked in
once by the push deploy (see deploy_tools/) rather than fetched live.

Binds 0.0.0.0 and serves TLS directly via a self-signed cert generated at
push time — there's no Caddy here, since installing it needs an apt
repository these compute nodes can't reach.
"""
from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, send_from_directory

from meridian.config import load_static_context
from meridian.context import ConsoleContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=None)
context = ConsoleContext(load_static_context())


@app.get("/api/context")
def api_context():
    return jsonify(context.snapshot())


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/<path:path>")
def static_files(path):
    return send_from_directory(STATIC_DIR, path)


if __name__ == "__main__":
    port = int(os.environ.get("MERIDIAN_PORT", "8765"))
    cert_file = os.environ.get("MERIDIAN_TLS_CERT")
    key_file = os.environ.get("MERIDIAN_TLS_KEY")
    ssl_context = (cert_file, key_file) if cert_file and key_file else None
    app.run(host="0.0.0.0", port=port, ssl_context=ssl_context)
