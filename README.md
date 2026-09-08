# Meridian Console

A lightweight, self-hosted "AI chat" demo prop for live GPU cloud demos.

It looks and behaves like a ChatGPT/Claude-style assistant — a sidebar with
past chats, suggested prompts, a simulated "thinking" trace before each
answer — but every response is canned, generic business Q&A. Nothing here
calls a real model.

What makes it worth deploying on real compute hosts: the header bar shows
**real** context for that specific box — which tenant and Netris environment
it currently belongs to, and which physical GPU (out of however many
`nvidia-smi` reports) is "serving" the current answer, chosen at random each
turn and highlighted in the GPU rail.

## Why this is a push deploy, not a `git clone` on each host

The original design had each compute host pull its own code and resolve its
own context live. Tested against a real fleet host (`hgx-pod00-su0-h00`) and
that doesn't hold up:

- **No outbound internet at all** from compute nodes — GitHub, PyPI, and the
  Caddy apt repo are all unreachable. `apt-get update` fails outright.
- **No `pip`, no `python3-venv`** on the node, and no way to install them.
- **No outbound path back to the Netris controller or the jump host either**
  — a compute node can only be reached *inbound*, by the jump host dialing
  in via its own trusted key (the same `hgx-*` alias mechanism the Portal's
  own `ssh_client.py` already uses).

What a compute node *does* have: Python 3 stdlib, `openssl`, and enough to
run a plain HTTP(S) server locally.

So instead: build once somewhere with real connectivity (the Netris
controller box doubles as this fleet's jump host, and has full internet
access), resolve each host's tenant/environment there — it has direct access
to the Netris API and to the SSH alias table — and push a ready-to-run
bundle to the compute node over the same inbound SSH path that already
works. The console itself becomes a small Flask app with **zero network
calls of its own**, TLS served directly via a self-signed cert generated at
push time (no Caddy — installing it needs the apt repo the node can't
reach).

## Deploying to a host

Run this **from the Netris controller / jump host**, not from the compute
node itself:

```bash
git clone https://github.com/iamjarvs/chat_sim_console.git
cd chat_sim_console
bash deploy_tools/push_to_host.sh hgx-pod00-su0-h00 https://your-portal.example.com
```

You'll be prompted for the Portal's operator username/password if you don't
pass them as extra arguments or set `$OPERATOR_USERNAME`/`$OPERATOR_PASSWORD`
— this fetches real Netris + SSH credentials once from the Portal's
`/ops/api/device-credentials` endpoint, resolves that specific server's
tenant/environment against the live Netris controller, and pushes the app +
a self-signed cert + that resolved context to the node.

No reachable Portal yet? Provide Netris credentials directly instead:

```bash
NETRIS_BASE_URL=https://your-netris-controller \
NETRIS_USERNAME=netris \
NETRIS_PASSWORD=... \
TENANT_DISPLAY_NAME="ACME Corp" \
GPUS_PER_SERVER=8 \
  bash deploy_tools/push_to_host.sh hgx-pod00-su0-h00
```

Re-running the script for the same host is safe (rebuilds and re-pushes in
place); the admin venv, app venv, and self-signed cert are all cached under
`~/.cache/meridian-console-*` and reused across hosts, so pushing to a
second host is fast.

The console then runs as the `meridian-console` systemd service on the
target, listening on `0.0.0.0:443` directly (no reverse proxy) — visit
`https://<that host's IP>`. Your browser will warn once on first visit,
which is expected for a self-signed cert.

## Uninstalling from a host

```bash
bash deploy_tools/uninstall_host.sh hgx-pod00-su0-h00
```

Stops and disables the systemd service and deletes the code + context file.

## Local development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python server.py
```

Without `/etc/meridian-console/context.json` present (or `$MERIDIAN_CONTEXT`
pointing elsewhere), it falls back to a demo context — "Demo Tenant", 8
simulated GPUs — so the UI is fully usable on a laptop with nothing else set
up. `MERIDIAN_PORT` defaults to 8765 without TLS unless
`$MERIDIAN_TLS_CERT`/`$MERIDIAN_TLS_KEY` are also set.

## Repo layout

```
server.py            Flask entrypoint — binds 0.0.0.0, serves static/ and GET /api/context
meridian/
  config.py            Loads the static context.json a deploy baked onto this host
  context.py            Caches header state; only nvidia-smi is ever checked live (no network)
  gpu_detect.py          nvidia-smi wrapper with a graceful fallback
static/               The chat UI (plain HTML/CSS/JS, no build step)
deploy_tools/
  push_to_host.sh        Run from the jump host: resolve context, build, push, start
  uninstall_host.sh       Reverses push_to_host.sh for one host
  resolve_context.py      Looks up a server's tenant/environment against live Netris
  netris_client.py        Minimal read-only Netris client (login + list servers/clusters)
```
