---
name: uxplay
source: https://github.com/FDH2/UxPlay
description: "Install, configure, and use UxPlay — an open-source AirPlay mirroring server that lets iOS/macOS clients mirror their screen to a Linux display. Covers Debian install, sway/Wayland compatibility via XWayland, and common usage patterns."
---

# UxPlay — AirPlay mirroring server for Linux

[UxPlay](https://github.com/FDH2/UxPlay) (fork, 2800+ stars) / [antimof/UxPlay](https://github.com/antimof/UxPlay) (upstream, 2000+ stars). Uses GStreamer + avahi mDNS so the Linux box appears as an AirPlay target on the local network.

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

### Common flags

| Flag | Purpose |
|------|---------|
| `-n "Some Name"` | Custom AirPlay display name |
| `-nh` | Don't append `@hostname` |
| `-s wxh` | Requested client resolution (default `1920x1080`; e.g. `-s 3840x2160` for 4K). Client may not honor exactly. |
| `-s wxh@r` | Resolution + refresh rate in Hz (default `@60`). |
| `-h265` | Enable H.265 (4K) video. Changes default `-s` from 1080p → 4K. Needs recent Apple device. |
| `-fps n` | Max frame rate request to client (default 30; `-fps 60` for smoother video) |
| `-fs` | Fullscreen mode (works with Wayland/X11/KMS/D3D11). 与 `-vs "waylandsink fullscreen=true"` 或 sway `for_window` 规则配合使用。 |
| `-vs videosink` | Choose GStreamer videosink. On sway/Wayland: `-vs "waylandsink fullscreen=true"` — 用引号将 videosink 名和属性括起来作为单个参数，这是文档指定的写法（`-fs` 也同时生效）。 |
| `-p` | Random PIN code on each connect |
| `-p 1234` | Fixed PIN code |
| `-vsync no` | Disable audio/video sync if out of sync |

### 分辨率/渲染窗口控制

UxPlay 有两个层面可以控制画面大小：

**客户端分辨率（`-s`）** — 向 iPhone/iPad 请求特定的流分辨率。这只是建议，客户端可能不严格遵守。默认 1920×1080；与 `-h265` 组合时默认升为 3840×2160。

**渲染窗口（`-vs` + `-fs` + sway rules）** — GStreamer 视频输出窗口的行为由 videosink 参数控制。文档指定写法：`-vs "waylandsink fullscreen=true"`（引号将 videosink 名和属性作为单个参数传入）。在 sway 中三层全屏可共存：

| 层 | 方式 | 说明 |
|----|------|------|
| GStreamer 层 | `-vs "waylandsink fullscreen=true"` | 让 waylandsink 窗口创建即全屏 |
| uxplay 层 | `-fs` | uxplay 自身请求全屏模式 |
| sway 层 | `for_window [app_id="uxplay"] fullscreen enable` | sway 窗口规则兜底 |

**推荐组合（x1tablet 实测）：**
```bash
uxplay -n x1tablet -s 3840x2160 -h265 -fps 60 -fs -vs "waylandsink fullscreen=true"
```

sway 端配合：
```ini
# ~/.config/sway/config
exec_always uxplay -n x1tablet -s 3840x2160 -h265 -fps 60 -fs -vs "waylandsink fullscreen=true"
for_window [app_id="uxplay"] fullscreen enable
```

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
- **firwall**: port 7000/7001 (AirPlay) must be open on the LAN interface.

## Pitfalls

- **Not a daemon by default**: `uxplay` runs in the foreground. To background it, either use `systemd --user` to wrap it, or background via terminal with `notify_on_complete=false`.
- **XWayland only**: if sway doesn't have XWayland enabled (`sway --version` + check `dpkg -l xwayland`), UxPlay will fail to open a window. Fix: `sudo apt install xwayland` and restart sway.
- **No audio** on some Wayland setups: UxPlay expects PulseAudio/PipeWire. if audio doesn't work, check `pactl info` — UxPlay routes audio through GStreamer's PulseAudio sink.
- **iPhone won't find UxPlay**: check `ss -tlnp | grep -E ':7000|7001'` and `avahi-browse -a` to confirm mDNS registration. If avahi is running but no registration, try `uxplay -n "AirPlay Server"` with an explicit name.
- **One session at a time**: only one client can mirror at once. Disconnect the current client before connecting another.
