# CDP Browser Setup for Hermes Agent on Sway

Launch a headed (GUI) Chromium on Sway as a CDP remote-debug target for Hermes Agent, including profile setup, port conflict cleanup, and Hermes config integration.

## Use Case

Hermes Agent needs a CDP endpoint (`browser.cdp_url`) for the browser toolset (navigate, click, snapshot, console, etc.). On a Sway desktop, you want the browser to appear as a real GUI window, not run headless.

## Step-by-step

### 1. Create a dedicated profile

```bash
mkdir -p ~/.hermes/cdp-chrome/Default
```

Create a custom new-tab HTML for visual distinction:

```html
<!-- ~/.hermes/cdp-chrome/new-tab.html -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; }
  html, body { height: 100%; width: 100%; }
  body {
    background: #1a73e8;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: sans-serif;
    color: rgba(255,255,255,0.6);
    font-size: 14px;
  }
</style>
</head>
<body>
  <div>Hermes CDP Browser</div>
</body>
</html>
```

### 2. Check who owns port 9222 before launching

Port 9222 is the standard CDP port. Common conflicts:

```bash
ss -tlnp 'sport = 9222'
```

- **SSH tunnel to remote Mac**: `users:(("ssh",pid=N))` — kill with `kill N` and find+kill the paired `autossh` process
- **Headless Playwright Chromium**: running under `--headless=new` with `--remote-debugging-port=9222` — kill the main process (lives on the PID column of `ss`)
- **Previous headed instance**: same process hierarchy as yours — kill and relaunch

### 3. Launch headed Chromium from a non-GUI session

Hermes gateway/service runs in a TTY session (not inside Sway). The Wayland socket and display environment variables are NOT inherited. Set them explicitly:

```bash
export XDG_RUNTIME_DIR=/run/user/1000
export WAYLAND_DISPLAY=wayland-1
export XDG_SESSION_TYPE=wayland
chromium \
  --remote-debugging-port=9222 \
  --user-data-dir=/home/<USER>/.hermes/cdp-chrome \
  --no-first-run \
  --no-default-browser-check \
  --ozone-platform=wayland
```

**Key points:**
- `WAYLAND_DISPLAY` value = find the correct wayland socket: `ls /run/user/1000/wayland-*` — pick the one owned by your user (usually `wayland-1`, but can change after sway restart). **The socket name changes when sway restarts** — check before every launch.
- `--ozone-platform=wayland` is needed explicitly when starting from a TTY; the global `/etc/chromium.d/wayland` hook may not run in this context. Note that the system config's `VaapiVideoDecoder` flag may still be injected via the Chromium wrapper script — verify with `chrome://version`.
- Without the env vars, Chromium errors: `Missing X server or $DISPLAY` and exits

### 4. Find the CDP WebSocket URL

```bash
curl -s http://127.0.0.1:9222/json/version | python3 -m json.tool
# Look for "webSocketDebuggerUrl"
```

**Critical: CDP WS URL changes on every Chromium restart.** The URL is generated per-session (random UUID). After launching, always fetch the fresh URL — do not reuse a cached one.

### 5. Configure Hermes

```bash
hermes config set browser.cdp_url 'ws://127.0.0.1:9222/devtools/browser/<ID>'
```

### 6. Verify with a YouTube test

```bash
# In Hermes session:
browser_navigate(url='https://www.youtube.com/watch?v=dQw4w9WgXcQ')

# Check video state:
browser_console(expression='document.querySelector("video").paused')
# Expected: false (autoplay needs a click in headed mode)

# Check no errors:
browser_console()
```

## Pitfalls

- **Auto-play blocked** — headed Chromium on Wayland requires a user gesture for video playback. After navigating to YouTube, click the pause button (ref from snapshot) to start playing.
- **CDP works but daily browser doesn't** — compare launch flags. CDP browser typically has no `VaapiVideoDecoder` flag; the user's browser gets it from `/etc/chromium.d/wayland`. If the GPU doesn't support VP9 (check `vainfo`), YouTube black-screens. See main SKILL.md → VaapiVideoDecoder section for diagnosis.
  ```bash
  # Diagnostic: launch user's browser without VA-API to confirm
  chromium --disable-accelerated-video-decode
  # Compare CDP flags
  curl -s http://127.0.0.1:9222/json/version | python3 -c "import sys,json; print(json.load(sys.stdin)['webSocketDebuggerUrl'])"
  ```
- **SSH tunnel on same port** — if you previously used `plugins.cdp_extract` with `remote_host`, there may be an `autossh` process persisting. Kill both the SSH tunnel and autossh:
  ```bash
  kill <ssh_pid> <autossh_pid>
  ```
- **Clean up `plugins.cdp_extract`** — after switching from remote to local, clear the remote fields:
  ```bash
  hermes config set plugins.cdp_extract.remote_host ''
  hermes config set plugins.cdp_extract.ssh_key ''
  # ... etc for all remote_* fields
  ```
- **Multiple Chromium instances on same port** — only one process can bind port 9222. Kill stale instances first.
- **No swaymsg from outside sway** — you can't query window state from the Hermes session. Use `pgrep -af "chromium.*cdp-chrome"` to confirm the process is alive instead.
