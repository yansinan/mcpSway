# wechat-route proxy layer — 2026-05-31 (updated 2026-05-31)

## What was built

Added `proxy.py` to wechat-route — a pure Python (stdlib) path-based reverse proxy that unifies multiple agent-specific ports into one entry point.

## Architecture

```
Agent (client)  →  proxy.py (:19990)  →  router.py (:19998/:19997/:19996/:19999)
```

Each backend agent connects to `http://host:19990/<agent-name>/...` instead of its own port. Nginx/Caddy eliminated — zero extra deps.

## Files created/modified

| File | Role |
|---|---|
| `proxy.py` (new) | Path-routing reverse proxy, reads `agents.json` at startup |
| `bin/entrypoint.sh` (new) | Docker entrypoint: starts proxy.py in background, exec router.py in foreground |
| `Dockerfile` (mod) | Added COPY proxy.py, CMD → `entrypoint.sh`, EXPOSE 19990 |
| `docker-compose.yml` (mod) | Added `PROXY_PORT=19990` env var |
| `.env.example` (mod) | Documented PROXY_PORT |
| `tests/test_proxy.py` (new) | Integration test: mock backends + proxy routing verification |

## proxy.py design

### Route matching

```
agents.json (agents[].name)  →  routes["/<name>"] = (host, port)
Request path                 →  match longest prefix → strip → forward
```

Uses `sorted(routes, key=len, reverse=True)` so `browser.hermes` (len=16) matches before `hermes` (len=6).

### Security: iLink endpoint allowlist

Matches `router.py`'s `PROXY_ALLOWLIST` — only forwards known iLink endpoints:

```python
PROXY_ALLOWLIST = frozenset([
    "ilink/bot/getupdates", "ilink/bot/sendmessage",
    "ilink/bot/getuploadurl", "ilink/bot/sendtyping",
    "ilink/bot/getconfig", "ilink/bot/get_bot_qrcode",
    "ilink/bot/get_qrcode_status",
])
```

Requests to endpoints outside this list return 404.

### Forwarding mechanics

- Uses `http.client.HTTPConnection` for outbound request
- Strips the agent prefix from the path before forwarding
- Preserves query string
- Forwards **all HTTP headers except** `host`, `connection`, `transfer-encoding`, `content-encoding`
- Reads body via Content-Length (standard HTTP, no chunked encoding)
- Streams response back in 8KB chunks
- Timeout: 60s (sufficient for iLink long-poll at 35s)

### Multi-process Docker entrypoint

```sh
#!/bin/sh
set -e
python3 proxy.py &     # background: reverse proxy
exec python3 router.py # foreground: main router (SIGTERM-aware)
```

Key: `exec` ensures signals reach router.py, not a shell wrapper.

## Design decisions

| Decision | Why |
|---|---|
| **Pure stdlib** over nginx/Caddy | Zero extra deps, image stays ~57MB, runtime config reload by restart |
| **`ThreadingHTTPServer`** over `HTTPServer` | iLink uses long-poll (35s); threading handles concurrent connections without blocking |
| **agents.json at startup** (not hot-reload) | Simple, predictable, restart is cheap in Docker. Hot-reload adds complexity for marginal gain |
| **Allowlist** in proxy.py | Defense-in-depth: even if a backend port is compromised, proxy won't forward unknown endpoints |
| **Longest-prefix matching** | Prevents `browser.hermes` from being caught by `hermes` prefix |

### Port selection history

| Port | Why tried | Why rejected |
|---|---|---|
| **19995** | First choice — no conflict range | Changed to match user preference |
| **19999** | Asked by user | Conflict: `openclaw` backend already bound to 19999 in router.py |
| **19990** (final) | Safe range, no conflict | — |

**Lesson**: always verify the target port isn't already claimed by another agent in `agents.json` before setting `PROXY_PORT`.

## Agent configuration change

Backend agents (Hermes, Helix, OpenClaw) must update their `base_url` / `WEIXIN_BASE_URL`:

| Before | After |
|---|---|
| `http://host:19998` | `http://host:19990/hermes` |
| `http://host:19997` | `http://host:19990/browser.hermes` |
| `http://host:19996` | `http://host:19990/helix` |
| `http://host:19999` | `http://host:19990/openclaw` |

Old port-based connections **still work** — router.py's per-agent handlers remain unchanged. The proxy is an additional entry point on `:19990`.

## Emergency: run proxy on host when Docker Hub is unreachable

If the Docker registry is unreachable and you can't rebuild the container:

```bash
cd /path/to/wechat-route
python3 proxy.py
# Proxy listens on :19990, reads agents.json from same directory
# router.py still runs inside Docker — proxy forwards to localhost:1999x
```

This works because:
- router.py runs in `host` network mode — its ports are exposed on `127.0.0.1`
- proxy.py binds `0.0.0.0:19990` — external agents connect to it
- The host-based proxy and Docker-based router can coexist as long as port 19990 isn't claimed by Docker

To stop: `Ctrl+C` or `kill $(pgrep -f "python3 proxy.py")`

## Pitfalls encountered

### Duplicate 'Server' header (HTTP 400)

**Symptom:** Backend agent (Hermes WeChat gateway) reports `400, message="Duplicate 'Server' header found."`

**Root cause:** `BaseHTTPRequestHandler.send_response()` auto-emits `Server` + `Date` headers. Forwarding backend's `Server`/`Date` via `send_header()` creates duplicates.

**Fix:** Filter `"server"` and `"date"` from forwarded response headers:
```python
self.send_response(resp.status)
for k, v in resp.getheaders():
    if k.lower() not in ("transfer-encoding", "content-encoding",
                         "connection", "server", "date"):
        self.send_header(k, v)
self.end_headers()
```

**Verification:** `curl -s -D- -o /dev/null <url>` shows exactly one `Server` + one `Date` line.

### Shell heredoc in terminal
- **Port conflict in tests**: The mock backends used 19996-19999 which might be occupied by running instances. Use a test-only port range (e.g. 18996-18999) with a test-only agents.json via `AGENTS_FILE` env var.
- **http.server Handler class factory**: Each mock backend needs a distinct handler class (not the same class rebound). Use a closure/factory function (`make_handler(name)`) to create independent classes, otherwise `backend_name` gets overwritten by the last iteration.
- **Mock handler `log_message` signature**: Override `log_message(self, *a)` to suppress logs. Pyright warns about param incompatibility (`format` is keyword) but it works fine at runtime — safe to ignore.
- **Port conflict with existing agent**: Always check `agents.json` before choosing `PROXY_PORT`. The port must not collide with any existing agent's port. In this session, `:19999` was initially chosen but openclaw already used it — detected via curl returning 501 (router.py's handler responding instead of proxy).
