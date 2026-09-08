"""Meridian console — a lightweight Flask app serving a static chat UI plus
one small JSON endpoint so the UI can show real tenant/environment/GPU
context resolved on this host. Everything conversational is canned content
that ships with the frontend; nothing here calls an actual model.
"""
from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, send_from_directory

from meridian.config import load_config
from meridian.context import ConsoleContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=None)
context = ConsoleContext(load_config())


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
    app.run(host="127.0.0.1", port=port)
