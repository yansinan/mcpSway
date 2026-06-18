# wechat-route Dockerization — 2026-05-30

## Project
HermesClaw / wechat-route: WeChat iLink message router (Python, pure stdlib).

## Files created
- `Dockerfile` — alpine:3.21 + apk python3 + ca-certificates, stripped __pycache__/test/idlelib/tkinter, 56MB final
- `docker-compose.yml` — wechat-route service, ports 19998/19999, restart: on-failure:10
- `.dockerignore` — exclude tests/, .git/, logs/

## Key decisions
- **Alpine + apk python3** (not python:3.11-alpine image) — saves 28MB by avoiding pip, setuptools, __pycache__
- **Strip stdlib** — find + rm __pycache__, test/, idlelib/, tkinter/, turtle* saves ~28MB
- **Flask was unused** — router.py uses http.server.ThreadHTTPServer (stdlib), not Flask. Removed from deps.
- **`network_mode: "host"`** — 4 agent ports (19996-19999) distinguished by port, no port mapping needed. Host networking avoids `ports:` list maintenance as agents are added/removed.
- `restart: on-failure:10` — crash restarts capped at 10, then stops. Avoids infinite crash loop.
- No manager.py in Docker — container entry is router.py directly. Docker handles lifecycle.
- No watchdog scripts — Docker restart policy replaces cron-based watchdog.
- No restart counter — Docker's on-failure:N handles this natively.
- Single agents.json at root — mounted as volume in production. No separate config/ directory.

## Image size evolution during this session
| Stage | Size |
|---|---|
| python:3.11-slim + flask | 231MB |
| python:3.11-alpine + flask | 108MB |
| python:3.11-alpine no flask | 84MB |
| alpine:3.21 + apk python3 (stripped) | **56MB** |

## Files deleted
- manager.py, scripts/ (strict_watchdog.py, increment_restart_and_notify.py)
- config/ (duplicate agents.json template)
- mention_aliases.json (superseded by agents.json per-agent aliases)
- SKILL.md (outdated, referenced deleted files)
- requirements.txt (merged into README)
- TASK_START_POINT.md, docs/, CODE_OF_CONDUCT.md, CONTRIBUTING.md, PUSH_INSTRUCTIONS.md, LICENSE

## Renames
- hermesclaw.py -> router.py
- tests/test_hermesclaw.py -> tests/test_router.py
- All internal: logger name, docstrings, log file names, PID file names
