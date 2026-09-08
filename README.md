# Meridian Console

A lightweight, self-hosted "AI chat" demo prop for live GPU cloud demos.

It looks and behaves like a ChatGPT/Claude-style assistant — a sidebar with
past chats, suggested prompts, a simulated "thinking" trace before each
answer — but every response is canned, generic business Q&A. Nothing here
calls a real model.

What makes it worth deploying on real compute hosts: the header bar shows
**real** context resolved on that specific box — which tenant and Netris
environment it currently belongs to, and which physical GPU (out of however
many `nvidia-smi` reports) is "serving" the current answer, chosen at random
each turn and highlighted in the GPU rail.

## How it resolves context

1. At startup (and every 5 minutes after), it SSHes to the Netris jump host
   and resolves this box's own `hgx-podNN-suXX-hYY`-style Netris server name
   by matching the jump host's alias table against this host's own local
   IPs — the same alias table
   [Provider Portal's `ssh_client.py`](../Provider-Portal/app/ssh_client.py)
   already parses for its own SSH automation.
2. It logs into the Netris controller directly and looks up which cluster
   that server currently belongs to — the cluster's name **is** the
   Provider Portal's environment name (confirmed: the Portal sets a
   cluster's Netris name to its own `environments.netris_name` on create).
3. GPU count and model come from `nvidia-smi` on this box; the tenant name
   comes from Provider Portal's `tenant_display_name` setting.
4. Any step that fails (no network path to the jump host, Netris
   unreachable, no `nvidia-smi`) falls back gracefully — the console always
   renders, worst case with a generic "Unknown" label instead of crashing
   mid-demo.

## Installing on a compute host

Requires a Debian/Ubuntu host with root access, and the Provider Portal's
operator username/password (the same one that gates `/ops`).

```bash
curl -fsSL https://raw.githubusercontent.com/iamjarvs/chat_sim_console/main/deploy/install.sh -o install.sh
sudo bash install.sh https://your-portal.example.com
```

You'll be prompted for the operator username/password if you don't pass them
as extra arguments or set `$OPERATOR_USERNAME` / `$OPERATOR_PASSWORD`. This
one-time fetch pulls the actual Netris + SSH jump-host credentials from the
Portal's `/ops/api/device-credentials` endpoint and stores them at
`/etc/meridian-console/config.json` (mode 600) — nothing else touches this
host afterwards.

The console then runs as the `meridian-console` systemd service behind Caddy
on port 443, with a self-signed certificate (Caddy's `tls internal`) — your
browser will warn once on first visit, which is expected for an internal
demo box.

Re-running `install.sh` is safe: it re-pulls the code and credentials and
restarts the service, so it doubles as the update path.

By default it clones over SSH (`git@github.com:...`), which needs a deploy
key or forwarded SSH agent already trusted for GitHub on every fresh host.
If your hosts don't have that set up, override with an HTTPS URL (with a
token baked in, for a private repo) instead:

```bash
sudo MERIDIAN_REPO_URL="https://<token>@github.com/iamjarvs/chat_sim_console.git" \
  bash install.sh https://your-portal.example.com
```

## Uninstalling

```bash
curl -fsSL https://raw.githubusercontent.com/iamjarvs/chat_sim_console/main/deploy/uninstall.sh -o uninstall.sh
sudo bash uninstall.sh
```

Stops and removes the systemd service, the Caddy site block, the code
checkout, and the pulled credentials. Leaves Caddy itself installed (in case
anything else on the box uses it).

## Local development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python server.py
```

Without `/etc/meridian-console/config.json` present (or `$MERIDIAN_CONFIG`
pointing elsewhere), it falls back to a demo config — "Demo Tenant", 8
simulated GPUs, no real Netris/SSH lookups attempted — so the UI is fully
usable on a laptop with no Netris controller in reach. Copy
`config.example.json` and point `MERIDIAN_CONFIG` at it to test against a
real controller instead.

## Repo layout

```
server.py            Flask entrypoint — serves static/ and GET /api/context
meridian/
  config.py           Loads /etc/meridian-console/config.json
  netris_client.py     Minimal read-only Netris client (login + list servers/clusters)
  ssh_alias.py          Resolves this host's own Netris server name via the jump host
  gpu_detect.py         nvidia-smi wrapper with a graceful fallback
  context.py            Ties the above together, caches, refreshes on a timer
static/               The chat UI (plain HTML/CSS/JS, no build step)
deploy/
  install.sh            Fleet install: fetch credentials, pull code, Caddy + systemd
  uninstall.sh           Reverses install.sh
```
