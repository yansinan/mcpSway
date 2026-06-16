---
name: linux-audio-pipewire
category: devops
source: https://wiki.archlinux.org/title/PipeWire
description: Diagnose and fix PipeWire audio on sway/Wayland Linux — from application layer down to HDA codec pins, Bluetooth, and HDMI/DP audio over USB-C docks.
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
| `hda-verb` | alsa-tools | HDA codec pin/verb manipulation |
| `edid-decode` | edid-decode | Parse EDID for audio capabilities |

## Adjust Volume / Defaults

```bash
# List sinks with IDs
wpctl status

# Set default sink
wpctl set-default <ID>

# Adjust volume
wpctl set-volume <ID> 0.85
wpctl set-mute <ID> toggle

# Sink IDs are persistent across sessions (WirePlumber saves them)
```

## Test Audio Output

```bash
# Play to a specific sink by name
pw-play --target=alsa_output.pci-0000_00_1f.3.analog-stereo /usr/share/sounds/alsa/Front_Center.wav

# Play to default sink
pw-play /usr/share/sounds/alsa/Front_Center.wav
```

## Bluetooth Audio

- Install: `pipewire-pulse` + `libspa-0.2-bluetooth`
- Bluetooth speaker should appear as a bluez5 device + sink in `wpctl status`
- Switch with `wpctl set-default <bt_sink_id>`
- For A2DP vs HSP profile control, check `bluetoothctl info`

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

## 参考资料

- `references/hdmi-dp-audio-usbc-dock.md` — USB-C 扩展坞 HDMI/DP 音频调试
