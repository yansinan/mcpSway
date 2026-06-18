---
name: python-dockerize
source: https://docs.docker.com/compose/
description: "Dockerize a Python project with minimal footprint — Dockerfile, docker-compose, config management, restart policies, and repo cleanup before ship."
tags: [docker, python, deployment, devops]
---

# Python Project Dockerization

Class-level skill for packaging Python services into minimal Docker images with clean docker-compose orchestration.

## Trigger

Load this skill when the user asks to Dockerize a Python project, create a Dockerfile + compose setup, clean up a repo for container deployment, or reduce Docker image size.

## Workflow

### 1. Understand the project first

- Read `requirements.txt` / `pyproject.toml` — identify actual runtime deps
- Read `README.md` — understand purpose, ports, config files
- Check if there's already a `manager.py` or similar lifecycle script
- List all files (`find . -not -path './.git/*' -type f | sort`)

### 2. Minimal Dockerfile

#### Discovery: check actual imports first

Before writing the Dockerfile, **verify what the code actually imports**:

```bash
grep -rn '^import\|^from' *.py | grep -vE 'test_|conftest|__future__'
```

A project listing `flask` in `requirements.txt` may not actually import it — always verify. Pure-stdlib projects can use the Alpine approach and skip pip entirely.

#### Standard (pip deps required)

```
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir <runtime-deps-only>
COPY <runtime-files> ./
# Only copy what's needed at runtime — no tests, docs, scripts
CMD ["python3", "<main>.py"]
```

#### Advanced: Alpine-based for stdlib-only projects

If the project uses **only Python stdlib** (no Flask, requests, numpy, pandas), Alpine + apk python3 yields the smallest image:

```dockerfile
FROM alpine:3.21
WORKDIR /app
RUN apk add --no-cache python3 ca-certificates && \
    find /usr/lib/python3.* -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null; \
    rm -rf /usr/lib/python3.*/test /usr/lib/python3.*/idlelib \
           /usr/lib/python3.*/tkinter /usr/lib/python3.*/turtle* 2>/dev/null; \
    true
COPY <runtime-files> ./
CMD ["python3", "<main>.py"]
```

##### Sizing reference (2026-05-30)

| Approach | Size | Notes |
|---|---|---|
| `python:3.11-slim` + pip install | ~231MB | Baseline |
| `python:3.11-alpine` + pip install flask | ~108MB | Overkill if Flask unused |
| `python:3.11-alpine` pure stdlib | ~84MB | Still includes pip |
| `gcr.io/distroless/python3-debian12` | ~80MB | No shell, hard to debug |
| **`alpine:3.21` + apk python3 (stripped)** | **~56MB** | No pip, no tkinter/test/idle |

##### Verification for Alpine
- Check HTTPS: `apk add ca-certificates` is required for `urllib.request.urlopen`.
- Check for C extensions: Alpine uses musl libc. Pure-Python wheels (Flask, requests) work; binary wheels (numpy, pandas) may need build deps.
- Test module import AFTER stripping: ensure none of the removed modules (tkinter, turtle, idlelib, test) are imported by the code.

Principles:
- **slim base for pip deps, alpine for stdlib-only**
- **Strip python stdlib** for alpine: remove __pycache__, test/, idlelib/, tkinter/, turtle* saves ~28MB.
- **Only install runtime deps** in Dockerfile
- **COPY only runtime files** — exclude tests/, docs/, scripts/ via .dockerignore
- **State/data dirs** → `RUN mkdir -p logs` (mounted via volume at runtime)

### 3. docker-compose.yml

#### Port mapping (default)

```yaml
services:
  app:
    build: .
    container_name: <name>
    restart: on-failure:10   # restart on crash, max 10 retries, then stop
    ports:
      - "<host_port>:<container_port>"
    volumes:
      - ./logs:/app/logs          # persist runtime data
      - ./config.json:/app/config.json:ro  # config files as volumes
    environment:
      - KEY=VALUE
```

#### Host networking (agents distinguished by port)

When the app binds multiple ports and agents connect by port number (not host), use host networking to avoid mapping each port:

```yaml
services:
  app:
    build: .
    network_mode: "host"
    restart: on-failure:10
    volumes:
      - ./logs:/app/logs
      - ./config.json:/app/config.json:ro
    environment:
      - KEY=VALUE
```

No `ports:` needed — container directly binds host ports. Useful for proxy/routing apps where each backend uses a different port.

Key restart policy guidance:
| Policy | Behavior | Use case |
|---|---|---|
| `no` | Never restart | Manual services |
| `on-failure:10` | Restart on crash, max 10 times | Services that should stop after persistent failure |
| `unless-stopped` | Always restart unless manually stopped | Daemons that should always run |
| `always` | Always restart (even after manual stop) | Rarely appropriate |

### 4. .dockerignore

- Exclude `.git/`, `__pycache__/`, `.env`, `logs/`
- Exclude `tests/`, `docs/`, `scripts/` (not needed at runtime)
- Exclude dev files: `.vscode/`, `.idea/`, `.DS_Store`
- **Do NOT exclude** config files the image needs at build time (e.g. `agents.json`)

### 5. Config management pattern

- Keep **one canonical config file** in the repo root
- Dockerfile COPYs it into the image as default
- docker-compose mounts a host copy at runtime to override: `./config.json:/app/config.json:ro`
- The code reads from the working directory — works the same in Docker and bare-metal
- **No separate config/ directory** — one source of truth

### 7. Multi-process containers (entrypoint pattern)

When a service needs **two (or more) processes** in one container (e.g. a main router + a reverse proxy), DO NOT use a process supervisor (supervisord, s6, systemd). Use a shell entrypoint instead:

```sh
#!/bin/sh
# entrypoint.sh — starts all processes, main one in foreground
set -e
python3 proxy.py &        # background: secondary process
exec python3 router.py    # foreground: main process (exec for signal handling)
```

Key rules:
- **At most one `exec`** — the foreground process. When it exits, Docker kills the container.
- **All others in background (`&`)** — Docker kills them when the foreground exits.
- **`exec` the main process** — ensures signals (SIGTERM, SIGINT) reach it directly. Without `exec`, `sh` is PID 1 and signals may not propagate.
- **`set -e`** — if `proxy.py` fails to start, the entrypoint exits immediately.
- **COPY entrypoint in Dockerfile** → `CMD ["sh", "bin/entrypoint.sh"]`

#### When NOT to use entrypoint

| Situation | Alternative |
|---|---|
| Processes need independent lifecycles | Split into two containers |
| Need health checks per process | Split into two containers |
| One process is CPU-bound | Split into two containers |
| Need per-process resource limits | Split into two containers |

The entrypoint pattern is for **co-dependent processes** — when one can't run without the other and they share the same lifecycle.

### 8. Pure-Python reverse proxy (zero-dependency HTTP forward proxy)

When you need a path-based reverse proxy but want to avoid nginx/Caddy:

```python
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

ROUTES = {"/hermes": ("127.0.0.1", 19998)}

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._proxy()
    def do_POST(self):
        self._proxy()

    def _proxy(self):
        path = urlparse(self.path).path
        # Match longest prefix first
        matched = None
        for prefix in sorted(ROUTES, key=len, reverse=True):
            if path == prefix or path.startswith(prefix + "/"):
                matched = prefix
                break
        if not matched:
            self._write_json(404, {"error": "no route"})
            return
        self._forward(matched)

    def _forward(self, prefix):
        host, port = ROUTES[prefix]
        target = path[len(prefix):] or "/"
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        conn = HTTPConnection(host, port, timeout=60)
        conn.request(self.command, target, body=body,
                     headers={k: v for k, v in self.headers.items()
                              if k.lower() not in ("host", "connection",
                                                   "transfer-encoding",
                                                   "content-encoding")})
        resp = conn.getresponse()
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in ("transfer-encoding", "content-encoding",
                                 "connection", "server", "date"):
                self.send_header(k, v)
        self.end_headers()
        while chunk := resp.read(8192):
            self.wfile.write(chunk)
        conn.close()
```

Key design choices:
- **`ThreadingHTTPServer`** — handles concurrent long-poll connections (needed for iLink getupdates) without blocking
- **`close_connection = True`** — prevents keep-alive connection pileup in proxy scenarios
- **Prefix sort by length descending** — ensures `browser.hermes` matches before `hermes` (longer prefix wins)
- **`HTTPConnection` from `http.client`** — pure stdlib, no dependency on `requests`/`httpx`

⚠️ **Critical: Duplicate header trap.** `BaseHTTPRequestHandler.send_response()` automatically emits `Server` and `Date` headers. When forwarding backend response headers verbatim, you MUST filter out `"server"` and `"date"` from the forwarded set, or the client receives duplicate headers and errors with `400 Duplicate 'Server' header found`. Always include them in the skip-list: `("transfer-encoding", "content-encoding", "connection", "server", "date")`.

### 6. Repo cleanup before ship

Before Dockerizing, clean the repo:

1. **Check references** before deleting any file (`grep -rn 'filename' .`)
2. **Merge configs** — if there are duplicate config files, consolidate to one
3. **Align naming** — project name in code (module names, loggers, docstrings) should match the repo name
4. **Remove redundant scripts** — if Docker handles lifecycle (restart, logs, status), management scripts are unnecessary
5. **Split concerns cleanly** — business logic in `<main>.py`, management in separate, delete unnecessary abstraction layers

## Pitfalls

- **pip outside venv**: In slim images, `pip` is system-level. Use `--no-cache-dir` to keep image small.
- **File not found in COPY**: Check `.dockerignore` — it may be excluding the file from the build context.
- **`.env` in dockerignore**: Standard `.gitignore` often excludes `.env`. If docker-compose needs it, either copy as `.env.example` or mount it explicitly.
- **Restart counting**: Don't build custom restart counters. Docker's `on-failure:<N>` already handles "max retries then stop".
- **manager.py in Docker**: If Docker handles container lifecycle, manager scripts that spawn/stop/check-status become redundant. The container entry point should be the main process directly.
- **Bare-metal vs Docker**: If the project supports both, the Docker path should be self-contained. Don't let bare-metal scripts (install.sh, systemd units) leak into the Docker image via COPY.
- **Subprocess spawn exits container**: If the entrypoint spawns the main process in background (manager.py start → subprocess.Popen → exit), the container exits immediately. Docker CMD must be a **foreground process** — the main Python script directly, not a lifecycle manager that spawns and returns.
- **Backend reconfiguration**: After deploying the Docker proxy, the backend agent (Hermes/OpenClaw gateway) may still be configured with the old iLink URL or port. Update its `WEIXIN_BASE_URL` / equivalent to point to the Docker proxy port, then **restart the backend** so it picks up the new config. A running gateway won't reload .env changes automatically.
- **Proxy port conflict with existing agent ports**: When adding a path-based reverse proxy to a multi-port app, the proxy's listening port must not collide with any existing backend port. Detect conflicts by `curl`-ing the target port — if you get a 501 (Unsupported method) response instead of 404, it means an existing handler already bound the port. Cross-reference against the config file (`agents.json`) before finalizing the proxy port.

## Extended Pitfalls (from dockerize-python)

### `.dockerignore` traps

- **Do NOT exclude build-required directories.** Excluding `config/` in `.dockerignore` causes `COPY config/` to fail with `not found`. Only exclude things truly not needed at build time (`.git/`, `tests/`, `__pycache__/`).
- **`host` network mode + `ports:` conflict.** Using `network_mode: "host"` with `ports:` produces `WARNING: Published ports are discarded when using host network mode`. Choose one or the other.
- **`on-failure` only counts non-zero exits.** `docker stop` (exit 0) does not trigger `on-failure`. Manual `docker stop` requires `docker compose up -d` to restart.
- **Port mapping needs host permission.** If `docker compose up` fails on port binding, try `sudo docker compose up` or ensure the user is in the `docker` group.

### Pre-Dockerization checklist

Before writing any Dockerfile:

1. **Verify actual imports** — `grep -rn '^import\\|^from' *.py` to confirm `requirements.txt` deps are real. A `flask` dependency may be unused, saving the entire `pip install` layer.
2. **Check if pure stdlib** — if the project only uses `urllib`, `http.server`, `json`, etc., Alpine + `apk python3` drops image from 231MB to 56MB.
3. **Read config loading** — does the code read `os.getenv("CONFIG_FILE")` or a hardcoded path? This determines volume mount strategy.
4. **Identify runtime dirs** — where does it write logs, PIDs, state? Mount those paths as volumes.
5. **Check entry point** — `main.py` / `app.py` / `cli.py` — align `CMD` accordingly.

### File cleanup before Dockerization

1. **Rename modules** to match repo name (`git mv` preserves history)
2. **Update import paths** in all files (including test patches)
3. **Delete genuinely unreferenced files** (check with `grep -rn`)
4. **Merge config files** into one canonical source
5. **Remove lifecycle scripts** Docker handles (watchdogs, restart counters, manager.py)
6. **Update documentation** — README, skill references, stale file paths

## References

- Docker restart policies: https://docs.docker.com/compose/compose-file/05-services/#restart
- python:3.11-slim on Docker Hub: https://hub.docker.com/_/python
- `references/wechat-route-proxy-2026-05-31.md` — full proxy.py implementation walkthrough: route matching, allowlist design, multi-process entrypoint, test patterns, agent config migration
- `references/wechat-route-dockerization-2026-05-30.md` — prior session: alpine stripping, host networking decision log
