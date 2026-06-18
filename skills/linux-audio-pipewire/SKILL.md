---
name: linux-audio-pipewire
category: devops
source: https://wiki.archlinux.org/title/PipeWire
description: Diagnose and fix PipeWire audio on sway/Wayland Linux — from application layer down to HDA codec pins, Bluetooth, card profiles, ALSA mixer state, and HDMI/DP audio over USB-C docks.
tags: [pipewire, audio, wayland, wireplumber, pulseaudio, alsa]
trigger: user reports no sound, audio device not detected, HDMI/DP audio not working, Bluetooth audio issues, or PipeWire/WirePlumber problems
---

# Linux Audio Diagnostics (PipeWire + sway/Wayland)

## Quick Status Check (start here)

```bash
# 1. Audio services running?
systemctl --user status pipewire pipewire-pulse wireplumber | grep "Active:"

# 2. All sinks/devices?
wpctl status

# 3. ALSA hardware devices
aplay -l

# 4. PipeWire node graph
pw-cli list-objects Node | grep -E "node.name|node.description|media.class"
```

## Audio Stack Layers (bottom → top)

```
ALSA (kernel) → PipeWire → WirePlumber (session mgr) → Applications
   ↑
   | hda-verb / amixer / aplay
```

- **ALSA**: kernel-level audio. `aplay -l` lists hardware devices.
- **PipeWire**: graph-based multimedia server. `pw-cli` for node inspection.
- **WirePlumber**: session & policy manager (creates sinks, manages routes). `wpctl` for volume/defaults.
- **PulseAudio compat**: `pipewire-pulse` provides `pactl` (via `pulseaudio-utils` pkg).

## Installation

```bash
sudo apt install -y pipewire pipewire-pulse pipewire-alsa wireplumber
```

**`pipewire-alsa` is critical** — without it, WirePlumber can't detect any ALSA audio hardware. The ALSA card shows up in `aplay -l` but `wpctl status` shows only "虚拟输出" (null sink).

Post-install, start the stack:
```bash
systemctl --user start pipewire.service pipewire-pulse.service wireplumber.service
```

Verify:
```bash
wpctl status
# Expected: Audio → Devices: [some device] → Sinks: [some sink, e.g. 内置音频 模拟立体声]
```

All three services are enabled by default and auto-start with sway's graphical session.

## ALSA Volume / Mute Check

PipeWire inherits ALSA's mixer state. If the ALSA Master is muted or at 0%, PipeWire may show correct devices but no sound:

```bash
amixer -c 0 sget Master
# If "Mono: Playback 0 [0%] [-65.25dB] [off]" → fix:
amixer -c 0 sset Master 80% unmute
```

## Card Profiles (Analog vs HDMI/DP)

A single HDA Intel sound card may expose multiple outputs: analog (built-in speaker/headphone jack) and digital (HDMI/DisplayPort audio to external monitors). WirePlumber defaults to the analog profile.

```bash
# List available profiles
pactl list cards

# Current active profile
pactl list cards | grep 'Active Profile'

# Switch to HDMI output + analog input (mic)
pactl set-card-profile alsa_card.pci-0000_00_1b.0 output:hdmi-stereo+input:analog-stereo

# Switch back to analog only
pactl set-card-profile alsa_card.pci-0000_00_1b.0 output:analog-stereo+input:analog-stereo
```

### Making the profile permanent

Add to `~/.config/sway/config` after the `include` line:

```
# ── Audio ──
# Default: HDMI output to external monitor, keep internal mic
exec_always pactl set-card-profile alsa_card.pci-0000_00_1b.0 output:hdmi-stereo+input:analog-stereo
```

## Adjust Volume / Defaults

```bash
# List sinks with IDs
wpctl status | grep -A10 'Sinks'

# Set default sink
wpctl set-default <ID>

# Adjust volume
wpctl set-volume <ID> 0.85
wpctl set-mute <ID> toggle

# PulseAudio equivalent
pactl set-sink-volume alsa_output.pci-0000_00_1b.0.hdmi-stereo 100%
```

## Common Diagnostic Commands

| Tool | Package | Purpose |
|------|--------|---------|
| `wpctl` | wireplumber | Default sink, volume, device listing |
| `pw-cli` | pipewire | Node/link/port introspection |
| `pw-dump` | pipewire | Full PipeWire graph JSON |
| `pw-play` | pipewire | Play audio to a specific node |
| `pw-top` | pipewire | Real-time audio stream monitor |
| `amixer` | alsa-utils | ALSA mixer state (mute/volume) |
| `aplay` | alsa-utils | List/play ALSA devices |
| `speaker-test` | alsa-utils | Audio output test |
| `pactl` | pulseaudio-utils | PulseAudio compat CLI |
| `hda-verb` | alsa-tools | HDA codec pin/verb manipulation |
| `edid-decode` | edid-decode | Parse EDID for audio capabilities |

## Test Audio Output

```bash
# Through PipeWire
speaker-test -c 2 -l 1 -D pipewire

# Direct to ALSA hardware (bypass PipeWire)
speaker-test -c 2 -l 1 -D hw:0,0   # analog
speaker-test -c 2 -l 1 -D hw:0,3   # HDMI/DP

# Play to a specific sink by name
pw-play --target=alsa_output.pci-0000_00_1f.3.analog-stereo /usr/share/sounds/alsa/Front_Center.wav
```

## Bluetooth Audio

- Install: `pipewire-pulse` + `libspa-0.2-bluetooth`
- Bluetooth speaker should appear as a bluez5 device + sink in `wpctl status`
- Switch with `wpctl set-default <bt_sink_id>`
- For A2DP vs HSP profile control, check `bluetoothctl info`

## Native Wayland Audio Management GUIs

See `references/audio-guis.md` for a comparison of GTK4/Rust/TUI audio tools:

| Need | Recommended Tool |
|------|-----------------|
| Volume control | pwvucontrol (GTK4) or wiremix (TUI) |
| Per-app routing | wiremix or ncpamixer |
| Equalizer/effects | EasyEffects |
| Full patchbay | qpwgraph (with `QT_QPA_PLATFORM=wayland`) |
| Keyboard-only | wiremix or ncpamixer |

## Troubleshooting Checklist

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `wpctl status` shows only "虚拟输出" | `pipewire-alsa` missing | `sudo apt install pipewire-alsa` |
| Devices visible but no sound | ALSA Master muted | `amixer sset Master 80% unmute` |
| HDMI audio device in `aplay -l` but not in WP | Wrong card profile | `pactl set-card-profile ... output:hdmi-stereo...` |
| HDMI sink shows but no sound through monitor | Monitor ELD / DP-MST issue | Test with `speaker-test -D hw:0,<N>` to isolate |
| Speaker test works but applications silent | Default sink not set | `pactl set-default-sink <name>` |
| Audio stuttering / glitches | Buffer/quantum too small | Try `PIPEWIRE_QUANTUM=256` or 512 |

## Known Issues

### HDMI/DP Audio Over USB-C Dock (Intel HDA)
Root cause: i915 driver fails to pass EDID audio info to snd_hda_intel.
- `aplay` succeeds but no sound → ELD missing (`/proc/asound/card0/eld#*` doesn't exist)
- Pin sense can show display connected but HDA codec pin isn't activated
- Fixes (in order of reliability):
  1. **3.5mm audio cable** from dock to monitor — bypasses DP audio entirely
  2. **EDID firmware override** (`drm.edid_firmware=DP-N:edid/<file>.bin`) — inject EDID with Audio Data Block
  3. Test with HDMI cable instead of DP (HDMI carries audio natively)

### aplay: set_params: Channels count non available
Use `plughw` instead of `hw`:
```bash
aplay -D plughw:0,3 -c 2 test.wav
```

### No Pactl
`pactl` requires `pulseaudio-utils` even with PipeWire-Pulse.

## Waybar Audio Module

```json
"pulseaudio": {
    "format": "{icon} {volume}%",
    "format-muted": "♫",
    "on-click": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
    "on-scroll-up": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.05+",
    "on-scroll-down": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.05-",
    "scroll-step": 5
}
```

## Useful audio utilities

```bash
sudo apt install -y pulseaudio-utils  # pactl — list cards, set profile, set default sink
sudo apt install -y alsa-utils        # amixer, speaker-test, aplay — direct ALSA access
```

## Hardware Video Acceleration (GStreamer + VA-API)

For Chromium and media apps that use GStreamer:
```bash
sudo apt install -y gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-vaapi vainfo
```

Verify VA-API (no display needed):
```bash
vainfo 2>&1 | grep -E 'Driver version|VAProfile'
# Intel HD 4000 (Ivy Bridge): i965 driver, H.264/MPEG2/VC1 hardware decode
# Intel Gen8+: iHD driver (intel-media-va-driver), adds HEVC/VP9
```

## 参考资料

- `references/hdmi-dp-audio-usbc-dock.md` — USB-C 扩展坞 HDMI/DP 音频调试
- `references/audio-guis.md` — Wayland-native audio management tools comparison
