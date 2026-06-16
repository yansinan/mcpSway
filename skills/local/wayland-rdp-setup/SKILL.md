---
name: wayland-rdp-setup
description: "Install, configure, and troubleshoot RDP server on Linux/Wayland for remote desktop access from any RDP client. Covers lamco-rdp-server across sway, Hyprland, GNOME, KDE with Tailscale integration, OpenH264, and EGFX debugging."
source:
  - https://github.com/lamco-admin/lamco-rdp-server
  - https://lamco.ai/products/lamco-rdp-server/
tags: [rdp, remote-desktop, wayland, tailscale, linux, troubleshooting, compositor, lamco, wayland]
---

# Wayland RDP Setup

Install and configure RDP remote desktop access on Debian systems running Wayland.

## Triggers

- User asks to install or set up RDP, remote desktop, screen sharing
- User wants to connect to their Linux desktop from another device
- User mentions lamco-rdp-server, wayvnc, gnome-remote-desktop, or krdp
- User wants Tailscale + RDP integration

## Prerequisites Check

```
# Verify PipeWire stack (required for Wayland screen capture)
dpkg -l | grep -E 'pipewire|wireplumber'

# Verify Wayland session
echo $WAYLAND_DISPLAY

# Verify Tailscale (if using Tailscale integration)
tailscale status
tailscale ip -4
```

## OpenH264 Requirement

**lamco-rdp-server requires OpenH264 for H.264 video encoding** (AVC420/AVC444). Without it, the server falls back to RemoteFX, which causes **black screen with Windows MSTSC** clients (the session establishes but no frames render).

**Debian 13 (Trixie):**
```bash
sudo apt install -y libopenh264-8
```
The server's dynamic loader auto-detects ABI v7 (.so.7) or v8 (.so.8)—both supported.

**Verify loading succeeded at next client connect:**
```bash
journalctl --user -u lamco-rdp-server*.service --no-pager | grep -i "DMA-BUF"
# ✅ EGFX[AVC444,AVC420,RFX]  → AVC encoders available
# ❌           EGFX[RFX]      → OpenH264 missing
```

## lamco-rdp-server (Recommended for wlroots/sway)

### 1. Download & Install

```bash
# Find latest release tag
RELEASE_INFO=$(curl -sL https://api.github.com/repos/lamco-admin/lamco-rdp-server/releases/latest)
TAG=$(echo "$RELEASE_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tag_name'))")
echo "Latest: $TAG"

# List available assets
echo "$RELEASE_INFO" | python3 -c "import json,sys; [print(a['name']) for a in json.load(sys.stdin).get('assets',[])]"

# Download Debian .deb
# If multiple assets match _amd64.deb, pick the one without distro suffix (generic)
curl -sL -o /tmp/lamco-rdp-server.deb \
  "https://github.com/lamco-admin/lamco-rdp-server/releases/download/${TAG}/lamco-rdp-server_*_amd64.deb"

# Install
sudo dpkg -i /tmp/lamco-rdp-server_*.deb
sudo apt install -f -y
```

### 2. TLS Certificates

Two options:

**Option A — Tailscale cert (recommended, trusted by all clients)** — requires Tailscale MagicDNS:

```bash
tailscale cert <hostname>.tailXXXXX.ts.net
# Produces: <hostname>.tailXXXXX.ts.net.crt + .key
# These are valid Let's Encrypt certs, accepted by iOS/macOS/Windows RDP clients
```

**Option B — Self-signed (quick test, may be rejected by iOS/macOS clients):**

```bash
mkdir -p ~/.config/lamco-rdp-server && chmod 700 ~/.config/lamco-rdp-server
cd ~/.config/lamco-rdp-server
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem \
  -days 3650 -nodes -subj "/CN=$(hostname)"
chmod 600 key.pem cert.pem
```

### 3. Config File

Write to `~/.config/lamco-rdp-server/config.toml`:

```toml
[server]
listen_addr = "0.0.0.0:3389"
max_connections = 5

[security]
# Cert paths: use Tailscale cert if available, else self-signed
cert_path = "/home/<user>/.config/lamco-rdp-server/cert.pem"
key_path = "/home/<user>/.config/lamco-rdp-server/key.pem"

# Authentication: "none" = no password (anyone on the network connects directly)
#               "pam" = system username/password via PAM (requires enable_nla = true)
auth_method = "none"
# enable_nla = false    # NLA authenticates before RDP session starts (requires "pam")

[video]
target_fps = 30

[audio]
enabled = true
codec = "auto"

[input]
use_libei = true

[clipboard]
enabled = true

[hardware_encoding]
enabled = true
vaapi_device = "/dev/dri/renderD128"
fallback_to_software = true
```

### 4. systemd User Service

The built-in D-Bus service (`--dbus-service` mode) has over-strict systemd hardening (`MemoryDenyWriteExecute=yes`, syscall filters) that causes SIGSYS on startup. Create a custom user service instead:

```bash
mkdir -p ~/.config/systemd/user
```

Write to `~/.config/systemd/user/lamco-rdp-server.service`:

```ini
[Unit]
Description=Lamco RDP Server
After=graphical-session.target network-online.target
Wants=graphical-session.target
StartLimitIntervalSec=60
StartLimitBurst=3
ConditionEnvironment=WAYLAND_DISPLAY

[Service]
Type=simple
ExecStart=/usr/bin/lamco-rdp-server -c %h/.config/lamco-rdp-server/config.toml -vv
Restart=on-failure
RestartSec=5
Environment=RUST_LOG=info
NoNewPrivileges=yes

[Install]
WantedBy=graphical-session.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now lamco-rdp-server.service
```

### 5. Tailscale Serve Integration

⚠️ **IMPORTANT**: lamco-rdp-server always binds to `0.0.0.0:PORT` (ignores `listen_addr`). This means it **cannot** share port 3389 with `tailscale serve --tcp 3389`. Two options:

**Option A — Direct exposure (simpler, no tailscale serve):** Just use the Tailscale IP directly. Any tailnet peer connects to `100.x.x.x:3389`. No tailscale serve needed.

```bash
# Already works — skip tailscale serve
```

**Option B — Via tailscale serve (uses a non-default port for RDP server):**

```bash
# Stop the RDP server first
systemctl --user stop lamco-rdp-server.service

# Change config to use a different local port (e.g., 3390)
# edit listen_addr in ~/.config/lamco-rdp-server/config.toml to "127.0.0.1:3390"

# Set up Tailscale TCP forwarding from 3389 → 3390
tailscale serve --bg --tcp 3389 tcp://127.0.0.1:3390

# Restart RDP server
systemctl --user start lamco-rdp-server.service

# Users still connect to 100.x.x.x:3389 as usual
```

To verify the serve config:
```bash
tailscale serve status
```

Expected output:
```
|-- tcp://<hostname>.ts.net:3389 (TLS over TCP, tailnet only)
|-- tcp://<tailscale-ip>:3389
|--> tcp://127.0.0.1:3389
```

Remove serve config later:
```bash
tailscale serve --tcp=3389 off
```

### 6. Firewall

```bash
sudo ufw allow 3389/tcp
```

## Pitfalls

- **listen_addr is ignored**: lamco-rdp-server v1.4.2 always binds to `0.0.0.0:PORT`, regardless of `listen_addr` in config. Setting `127.0.0.1:3389` still results in `0.0.0.0:3389`. This is a known limitation — use Tailscale serve if you need to control exposure (option B above).
- **D-Bus service mode crashes**: The shipped `lamco-rdp-server.service` in `/usr/lib/systemd/user/` uses `--dbus-service` mode with `MemoryDenyWriteExecute=yes` and strict `SystemCallFilter=@system-service`. This blocks essential syscalls for OpenH264/PipeWire → immediate SIGSYS. Always create a custom `Type=simple` service without the hardening.
- **Port conflict with tailscale serve**: If tailscale serve is already listening on 3389, the RDP server's bind to `0.0.0.0:3389` will fail with "Address already in use". Either stop tailscale serve first, or run RDP on a different port (see step 5 Option B).
- **Server ignores SIGTERM**: `systemctl stop` / `kill <PID>` may not work — the server hangs during cleanup. Use `kill -9 <PID>` to force-stop. Always safe because no data is at risk (screen capture only).
- **High memory usage on first start**: The initial memory peak can be very high (several GB). This stabilizes after a few seconds.
- **xdg-desktop-portal dependency**: The DEB package requires `xdg-desktop-portal` which is not always installed. `sudo apt install -f -y` resolves this automatically.

## Troubleshooting

### Black screen (Windows MSTSC, any client with EGFX capable)

**Cause:** EGFX (AVC420/AVC444) is negotiated but OpenH264 is not installed. The session establishes (TLS OK, codec advertised as AVC) but no frames reach the client → black window.

**Diagnostic:** Check startup + client connection logs:
```bash
journalctl --user -u lamco-rdp-server*.service --no-pager | grep -i "FAILED\|OpenH264\|AVC\|encoder"
# Look for: "Failed to create AVC444 encoder: OpenH264 library not found"
#           "Failed to create AVC420 encoder: OpenH264 library not found"
#           "No H.264 encoder available, using RemoteFX bitmap path"
```

**Fix:** Install OpenH264:
```bash
sudo apt install -y libopenh264-8
```
Then restart the service (SIGKILL—SIGTERM may hang):
```bash
kill -9 $(pgrep lamco-rdp) && sleep 2
systemctl --user start lamco-rdp-server.service
```

**Thorough fix:** Combine with explicit AVC420 config to avoid any EGFX version negotiation issues:
```toml
[egfx]
enabled = true
codec = "avc420"
avc444_enabled = false
```

### iOS/Mac RDP client: error 0x204 ("Cannot connect")

**Cause**: The client rejects the TLS certificate. Self-signed certs are not trusted by iOS Remote Desktop app and macOS Screen Sharing.

**Fix**: Use `tailscale cert` (Option A in step 2) instead of a self-signed cert. Connect using the MagicDNS hostname (`<hostname>.tailXXXXX.ts.net`) so the TLS hostname match succeeds. If still failing, verify the service is reachable from the client's tailnet.

### Local connection test

```bash
# Test TCP connectivity
timeout 3 bash -c 'echo | nc -w 2 127.0.0.1 3389' && echo "TCP OK"

# Test via tailscale IP
timeout 3 bash -c 'echo | nc -w 2 100.x.x.x 3389' && echo "Tailscale OK"

# Check RDP server is listening
ss -tlnp | grep 3389

# Check logs
journalctl --user -u lamco-rdp-server.service --no-pager -n 30 | grep -iE "ERROR|bind|address|client"
```

### iOS/Mac RDP client: error 0x04 (\"The connection was interrupted\")

**Cause**: The Microsoft Remote Desktop client sends a newer EGFX (Graphics Pipeline Extension) CapabilityVersion that lamco-rdp-server v1.4.2's bundled IronRDP library doesn't support. The connection establishes at TCP/TLS level but fails during EGFX DVC negotiation:

```
ERROR: Connection error from <client-ip> after 3.s: client loop failure:
X224 input error: [GraphicsPipelineServer::process]
decode error: invalid `version`: invalid capability version
```

**Fix**: Force a compatible graphics codec in config to bypass EGFX negotiation. This makes the server fall back to RemoteFX, which doesn't go through EGFX DVC:

```toml
[egfx]
enabled = true
codec = "avc420"
avc444_enabled = false
zgfx_compression = "never"
```

After changing the config, restart the service. Verify the codec changed in logs:
```
INFO lamco_rdp_server::server:   Codec: RemoteFX
```

**Note**: Setting `[egfx] enabled = false` does NOT prevent the client EGFX DVC negotiation — it only stops the server from initiating EGFX encoding. The Dynamic Virtual Channel handler is still registered and will attempt to parse the client's CapabilityVersion. The `codec = "avc420"` + `avc444_enabled = false` combination is the reliable fix.

**Full debug transcript**: `references/ios-egfx-debug-2026-06-13.md` in this skill directory covers the complete diagnostic process, root cause analysis, and tested/untested approaches.

## User Preferences

- **Keep default ports**: Unless the user explicitly asks to change ports, use 3389 and let Tailscale IP handle access directly (Option A in step 5). Don't add unnecessary layering with tailscale serve TCP forwarding.
- **Auth first, ask later**: Users expect to know how to authenticate. If `auth_method = "none"`, state explicitly that no password is needed — any tailnet peer can connect directly.
- **Search docs before guessing**: When debugging connection issues, read the official docs (README, FAQ, open GitHub issues) BEFORE inventing workarounds. The example-config.toml, GitHub issues, and product FAQ are authoritative. If the doc search turns up nothing, then reason from first principles.
- **Start from defaults**: When a custom config causes problems, reset to minimal overrides (listen_addr + cert_path + key_path + auth_method only) and test. The shipped defaults are sensible—only override what the user needs.
- **Config pitfalls to document on discovery**: `[egfx] enabled = false` does NOT prevent EGFX DVC registration (server bug v1.4.2); `listen_addr` always binds to 0.0.0.0; `allowed_resolutions` in `[display]` limits client-requestable resolutions only, not server capture resolution.

## Platform Notes

| Compositor | Capture | Input | Clipboard | Notes |
|---|---|---|---|---|
| Sway (wlroots) | wlr-screencopy | wlr-virtual-input | wlr-data-control | Needs native install |
| Hyprland | wlr-screencopy | wlr-virtual-input | wlr-data-control | Needs native install |
| GNOME 45+ | Portal | Portal+EIS | Portal | Flatpak or native |
| KDE Plasma 6.3+ | Portal | Portal+EIS | Klipper | Flatpak or native |

## Verification

```bash
# Check service status
systemctl --user status lamco-rdp-server.service

# Check listening port
ss -tlnp | grep 3389

# Check logs for errors
journalctl --user -u lamco-rdp-server.service --no-pager -n 20 | grep -iE "ERROR|panic|bind"

# Connect from another Tailscale device
# Windows: mstsc /v:100.66.66.249:3389
# Linux:   freerdp3 /v:100.66.66.249:3389
```
