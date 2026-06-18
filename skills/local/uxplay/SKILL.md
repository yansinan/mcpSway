---
name: uxplay
source: https://github.com/FDH2/UxPlay
description: "Install, configure, and use UxPlay — an open-source AirPlay mirroring server that lets iOS/macOS clients mirror their screen to a Linux display. Covers Debian install, sway/Wayland compatibility via XWayland, auto-start, CLI flags, and troubleshooting."
tags: [uxplay, airplay, mirroring, wayland, sway]
---

# UxPlay — AirPlay mirroring server for Linux

[UxPlay](https://github.com/FDH2/UxPlay) (fork, 2800+ stars) / [antimof/UxPlay](https://github.com/antimof/UxPlay) (upstream, 2000+ stars). Uses GStreamer + avahi mDNS so the Linux box appears as an AirPlay target on the local network.

UXPlay is an open-source AirPlay mirroring server. Works as an Apple TV-style receiver for iOS/macOS screen mirroring.

## When to load

- User asks for "AirPlay to Linux", "screen mirror iPhone to Linux", "投屏", "UxPlay"
- User wants to stream iOS/macOS display to a sway/Wayland or X11 desktop
- User needs an AppleTV-like service for presentations or media streaming

## Install (Debian 13+)

```bash
sudo apt install uxplay
```

**Dependencies**: ~65 packages pulled in (gstreamer1.0-libav, ffmpeg codecs, avahi mDNS, VA-API, OpenCL, etc.). ~167 MB disk, ~55 MB download. May take 5+ minutes on slower connections.

**Note on Chinese network**: `security.debian.org` can be very slow from mainland China. If download times out (repeatedly hitting 300s+ for security updates), add a local mirror:
```bash
echo "deb http://mirrors.ustc.edu.cn/debian-security trixie-security main non-free-firmware" \
  | sudo tee /etc/apt/sources.list.d/ustc-security.list
sudo apt install uxplay -y
# After install:
sudo rm /etc/apt/sources.list.d/ustc-security.list
sudo apt update
```

## Usage (sway / Wayland)

UxPlay uses X11 output → on sway, runs through **XWayland** (a window appears).

### Basic
```bash
uxplay
```

This starts the service. iPhone/iPad/Mac (same LAN) sees the computer name in Control Center → Screen Mirroring.

### Auto-start with sway + auto-fullscreen on connect

uxplay's default behavior: **starts running headless; on client connect → pops a window; on client disconnect → closes the window**. This meshes perfectly with sway's `for_window` fullscreen rule.

Two approaches, choose based on whether you need `swaymsg reload` to restart the daemon:

#### Approach A: exec (one-shot, safe on reload)

Runs only on sway login. Repeated `swaymsg reload` does NOT spawn duplicates.

```
include /etc/sway/config

exec uxplay -n "我的设备" -nh -p
for_window [app_id="uxplay"] fullscreen enable
for_window [class~="(?i)uxplay"] fullscreen enable
```

#### Approach B: exec_always + kill-before-start (restarts on reload)

When you need `swaymsg reload` to kill and restart the daemon (e.g. to pick up flag changes), use a single-line kill-then-exec wrapper:

```
exec_always bash -c 'pkill -x uxplay 2>/dev/null; sleep 0.5; exec uxplay -n 餐桌 -s 1920x1080 -fps 60 -hls -fs -vs "waylandsink fullscreen=true"'
```

**How it works**: `pkill -x uxplay` kills any existing instance → `sleep 0.5` allows port/network release → `exec uxplay ...` replaces the bash process with a fresh instance. Only one instance exists at any time.

**Quoting pitfall**: the `-vs "waylandsink fullscreen=true"` argument uses bare double quotes inside the single-quoted bash -c string. This is correct — `"` inside `'...'` are literal quotes that bash interprets as argument grouping. Do NOT use `\\"` (backslash-escaped) inside single quotes — that produces a literal backslash in the argument.

**Verification** — after reload, confirm the old PID is gone and a new one started:
```bash
OLD=$(pgrep -x uxplay)
swaymsg reload
sleep 3
NEW=$(pgrep -x uxplay)
[ -n "$NEW" ] && [ "$OLD" != "$NEW" ] && echo "ok" || echo "failed"
```

**`exec` not bare `exec_always`**: using `exec_always uxplay ...` (without the kill wrapper) spawns a new instance on every reload. The old instances keep running (same port → only the first binds). Over several reloads this silently accumulates ~100 MB RSS per zombie. Approach A or B above avoids this.

How it works:
- `exec uxplay` — starts uxplay once at sway login, waiting for AirPlay connections (safe across `swaymsg reload`)
- `for_window [app_id="uxplay"]` — catches native Wayland window
- `for_window [class~="(?i)uxplay"]` — catches XWayland window (uxplay is an X11 app, runs under XWayland)
- When client disconnects → uxplay automatically closes the window → sway exits fullscreen naturally

### Common flags

| Flag | Purpose |
|------|---------|
| `-n "Some Name"` | Custom AirPlay display name |
| `-nh` | Don't append `@hostname` |
| `-p` | Use standard AirPlay legacy ports (TCP 7000/7001/7100, UDP 6000/6001/7011) instead of random high port |
| `-d` | Enable debug logging (stderr). **Caution**: output goes to parent tty/pipe, not a file or syslog — cannot be reviewed retroactively. |
| `-s wxh` | Requested client resolution (default 1920x1080; e.g. `-s 3840x2160` for 4K). Client may not honor exactly. |
| `-s wxh@r` | Resolution + refresh rate in Hz (default `@60`). |
| `-h265` | Enable H.265 (4K) video. Changes default `-s` from 1080p → 4K. Needs recent Apple device. |
| `-fps n` | Max frame rate request to client (default 30; `-fps 60` for smoother video) |
| `-fs` | Fullscreen mode (works with Wayland/X11/KMS/D3D11). Can combine with sway `for_window` rule. |
| `-nc` | **Do NOT** close video window when client stops mirroring |
| `-hls` | Use lossless ALAC audio codec (higher quality than default AAC) |
| `-pin xxxx` | Require 4-digit PIN |
| `-vs 0` | Audio-only mode (no video window) |
| `-vs videosink` | Choose GStreamer videosink. On sway: `-vs "waylandsink fullscreen=true"` |
| `-vd DECODER` | Choose video decoder: `avdec_h264` (software), `vaapih264dec` (Intel HW), `v4l2h264dec` |
| `-vsync no` | Disable audio/video sync if out of sync |

### Window behavior
- Press `q` or `Ctrl+C` in the running terminal to quit.
- From sway: run in a foot terminal, or bind to a key:
  ```bash
  # ~/.config/sway/config
  $mod+U   exec foot uxplay -nh
  ```
- Or launch via fuzzel (`$mod+d` → type `uxplay`).

## Requirements

- **Same LAN**: AirPlay uses Bonjour/mDNS for discovery. The iPhone and Linux box must be on the same broadcast domain. Tailscale / VPN does NOT carry mDNS.
- **avahi-daemon** must be running (systemd service) — usually installed as a dependency.
- **Firewall**: port 7000/7001 (AirPlay) must be open on the LAN interface.

## Troubleshooting: "can see the device but can't connect"

When iOS discovers the uxplay name but the connection fails (spins then times out or disconnects):

1. **Verify uxplay is actually running** — it may have crashed silently after starting (output goes to pipe):
   ```bash
   pgrep -a uxplay
   ss -tlnp | grep uxplay   # should show port 7000 or similar
   ```

2. **Check mDNS registration** — verify the service is properly advertised via avahi:
   ```bash
   avahi-browse _airplay._tcp -t -r 2>/dev/null | grep -A5 "wlp3s0 IPv4"
   ```
   Look for: correct IPv4 address (not a stale/different IP), correct port, correct hostname.

3. **Use standard AirPlay ports** — without `-p`, uxplay uses a random high port (e.g. 35447). Some iOS versions or network setups prefer standard ports:
   ```bash
   uxplay -n "My Name" -p    # TCP 7000/7001/7100, UDP 6000/6001/7011
   ```

4. **Use `-nh` to avoid @hostname suffix** — without it, iOS sees "Name@hostname.local", which can cause cache confusion:
   ```bash
   uxplay -n "我的设备" -nh -p   # iOS sees exactly "我的设备"
   ```

5. **Stale mDNS entries from previous uxplay instances** can confuse iOS (different MAC/port cached). Fix: kill all uxplay (`pkill -f uxplay`), refresh AirPlay list on iOS (toggle Airplane Mode or pull down Control Center → long-press screen mirroring).

6. **Enable debug logging** to see the connection attempt:
   ```bash
   uxplay -n "My Name" -nh -p -d
   # Watch stderr for handshake, auth, or codec errors
   ```

7. **Check avahi-daemon**: `systemctl status avahi-daemon`

8. **Same subnet**: iPhone must be on the same LAN as the host. `ip -4 addr show | grep -v 127.0.0.1`

## Pitfalls

- **Not a daemon by default**: `uxplay` runs in the foreground. To background it, either use `systemd --user` to wrap it, or `exec` from sway config.
- **XWayland only**: if sway doesn't have XWayland enabled, UxPlay will fail to open a window. Fix: `sudo apt install xwayland` and restart sway.
- **No audio** on some Wayland setups: UxPlay expects PulseAudio/PipeWire. If audio doesn't work, check `pactl info`.
- **iPhone won't find UxPlay**: check `ss -tlnp | grep -E ':7000|7001'` and `avahi-browse -a` to confirm mDNS registration.
- **One session at a time**: only one client can mirror at once.
- **uxplay is an X11 app** — runs via XWayland. Use `class~="(?i)uxplay"` (regex) to match its window, not `app_id`.
- **No `-nc` by default** — omitting `-nc` means the window auto-closes on disconnect, which is what you want with the sway `for_window` fullscreen pattern.
- **Needs avahi-daemon** — verify with `systemctl status avahi-daemon`.
- **Multiple uxplay instances leave stale mDNS records** — each restart with different flags creates a separate mDNS service entry. Kill old processes before starting a new one.
- **No firewall needed** — default `iptables INPUT policy ACCEPT` works for AirPlay ports.
