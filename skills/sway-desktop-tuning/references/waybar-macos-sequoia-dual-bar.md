# Waybar macOS Sequoia Dual-Bar Reference

Developed during a live session on Debian 13 (sway 1.10.1, waybar 0.12.0).
Combines a top menu bar (macOS menubar style) with a floating bottom dock (wlr/taskbar).

## Architecture note

Waybar with a dual-bar JSON array runs as **1 process** (not 2). The two bars are threads within the same process. `pgrep -x waybar` returns exactly 1 PID. This is normal — don't expect 2 PIDs.

## Layout

```
┌─ Top bar (24px, exclusive) ────────────────────────────────────┐
│ workspace │ window/title │    󰉋   │ °C CPU MEM ♪   TS 📅 │
│           │ (rewrite:empty│ quick-launch │    system status     │
│           │  →"浏览器")   │  buttons     │  temp+bluetooth+net  │
└──────────────────────────────────────────────────────────────────┘

┌─ Bottom dock (48px, floating, exclusive=false) ────────────────┐
│ DeepSeek│Hermes│Rclone│Code│iCloud│OneNote│ …  │[Chrome][终端]  │    │
│           PWA launcher buttons            │  wlr/taskbar       │launch│
│         (always visible, click to open)   │ (open windows)     │ btn  │
└──────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Waybar** (`apt install waybar`)
- **Nerd Font Symbols Only** (for icon rendering, see main skill)
- **No swaybar** — must disable via config (see main skill)

## Configuration

### `~/.config/waybar/config` (JSON array, 2 bars)

```json
[
  // ── Top bar (menubar) ──
  {
    "layer": "top",
    "position": "top",
    "exclusive": true,
    "height": 24,
    "spacing": 4,
    "modules-left": ["sway/workspaces"],
    "modules-center": [
      "sway/window",
      "custom/term",
      "custom/chrome",
      "custom/files",
      "custom/fuzzel"
    ],
    "modules-right": [
      "temperature","cpu","memory","pulseaudio","bluetooth",
      "network","custom/tailscale","clock"
    ],
    "sway/workspaces": { "all-outputs": true },
    "sway/window": {
      "max-length": 50,
      "rewrite": { "^(?!.*\\S).*": "浏览器" }
    },
    "custom/term":   { "format": "  ", "on-click": "foot", "tooltip": false },
    "custom/chrome": { "format": "  ", "on-click": "google-chrome-stable", "tooltip": false },
    "custom/files":  { "format": " 󰉋 ", "on-click": "nautilus", "tooltip": false },
    "custom/fuzzel": { "format": "  ", "on-click": "fuzzel", "tooltip": false },
    "temperature": {
      "hwmon-path-abs": "/sys/devices/platform/coretemp.0/hwmon",
      "input-filename": "temp2_input",
      "critical-threshold": 80,
      "format": "{temperatureC}°C",
      "interval": 5
    },
    "cpu":    { "format": " {usage}%", "interval": 5 },
    "memory": { "format": " {percentage}%", "interval": 5 },
    "pulseaudio": {
      "format": "{icon} {volume}%",
      "format-muted": "♫",
      "on-click": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
      "scroll-step": 5
    },
    "bluetooth": {
      "format": " {status}",
      "format-connected": "",
      "on-click": "blueman-manager"
    },
    "network": {
      "format-wifi": "{essid}",
      "format-ethernet": " {ifname}",
      "format-disconnected": "󰖪"
    },
    "custom/tailscale": {
      "exec": "/home/dr/.local/bin/ts-status.sh",
      "return-type": "json",
      "interval": 30,
      "format": "{icon}",
      "format-icons": { "connected": "", "disconnected": "󰖪" }
    },
    "clock": { "format": "{:%H:%M}" }
  },

  // ── Bottom bar (dock) ──
  {
    "layer": "top",
    "position": "bottom",
    "exclusive": false,
    "height": 48,
    "modules-left": ["custom/os_button"],
    "modules-center": ["wlr/taskbar"],
    "custom/os_button": {
      "format": "  ",
      "on-click": "fuzzel",
      "tooltip": false
    },
    "wlr/taskbar": {
      "format": "{icon}",
      "icon-size": 36,
      "spacing": 4,
      "on-click": "activate",
      "on-click-middle": "close",
      "tooltip-format": "{title}"
    }
  }
]
```

### `~/.config/waybar/style.css` (dark macOS menubar + transparent dock)

```css
* {
  font-family: "Symbols Nerd Font", "Noto Sans CJK SC", "Noto Sans", sans-serif;
  font-size: 12px;
  min-height: 0;
}

/* Top bar */
window#waybar {
  background: rgba(30,30,30,0.88);
  color: #fff;
  border-bottom: 1px solid #444;
}

#workspaces button { padding: 0 5px; color: #777; border-bottom: 2px solid transparent; }
#workspaces button.focused { color: #fff; border-bottom: 2px solid #5294e2; }
#window { padding: 0 10px; color: #ccc; }

#custom-term, #custom-chrome, #custom-files, #custom-fuzzel {
  padding: 0 8px; color: #bbb; font-size: 14px;
}
#custom-term:hover, #custom-chrome:hover,
#custom-files:hover, #custom-fuzzel:hover {
  background: rgba(255,255,255,0.08); color: #fff;
}

#temperature, #cpu, #memory, #pulseaudio, #bluetooth, #network, #custom-tailscale, #clock {
  padding: 0 6px; color: #aaa; font-size: 11px;
}
#temperature { color: #e8a87c; }
#pulseaudio { color: #a0c4ff; }
#pulseaudio.muted { color: #e05252; }
#bluetooth { color: #7ec8e3; }
#bluetooth.off { color: #555; }
#network { color: #8fc9a8; }
#network.disconnected { color: #e05252; }
#custom-tailscale { color: #a78bfa; }
#custom-tailscale.disconnected { color: #555; }
#clock { font-weight: bold; color: #ddd; }

/* Bottom dock */
window#waybar:last-child {
  background: transparent; border: none;
}
#custom-os_button { font-size: 22px; padding: 0 14px; color: #ccc; }
#custom-os_button:hover { color: #fff; }
#taskbar button { padding: 2px 4px; border-bottom: 3px solid transparent; }
#taskbar button.active { border-bottom: 3px solid #5294e2; }
#taskbar button:hover { background: rgba(255,255,255,0.1); border-radius: 4px; }
```

### sway clean-reload pattern (avoids duplicate waybar on sway reload)

Add to sway config **instead of** bare `exec_always waybar`:

```bash
exec_always bash -c 'killall waybar 2>/dev/null; sleep 0.3; exec waybar'
```

This kills stale processes before starting a new instance. Without it, every `swaymsg reload` spawns an additional waybar (old process lingers, new one starts on top). The 0.3s sleep avoids a race where waybar's port isn't released yet.

### PWA launcher buttons (bottom dock alongside wlr/taskbar)

The bottom dock can hold both static launcher buttons (left) and the dynamic taskbar (center):

```json
{
  "layer": "top",
  "position": "bottom",
  "exclusive": false,
  "height": 48,
  "modules-left": [
    "custom/deepseek", "custom/hermes", "custom/rclone-webui",
    "custom/code-server", "custom/icloud-photos",
    "custom/onenote", "custom/notebooklm", "custom/dynalist"
  ],
  "modules-center": ["wlr/taskbar"],
  "modules-right": ["custom/os_button"]
}
```

Each PWA button uses the full `Exec=` command from Chrome's `--app-id` .desktop files. To launch a PWA without a window-manager chrome frame:

```bash
google-chrome --profile-directory=Default --app-id=<extension-id>
```

Example (DeepSeek PWA):

```json
"custom/deepseek": {
  "format": " DeepSeek ",
  "on-click": "/opt/google/chrome/google-chrome --profile-directory=Default --app-id=gaclnekabaleococgnghmjhcdfipepjj",
  "tooltip": false
}
```

**Tip**: Chrome PWA .desktop files in `~/.local/share/applications/` are auto-generated with names like `chrome-<24char-extension-id>-Default.desktop`. Rename them to human-readable names (`deepseek.desktop`, `rclone-webui.desktop`) — Chrome doesn't re-create renamed files unless re-installed. Deduplicate: if a PWA was installed twice (different extension IDs, same Name field), delete the duplicate .desktop by checking which `Exec=` path you actually want.

Replace `include /etc/sway/config` in `~/.config/sway/config` with:
1. Variable definitions at the top (`set $mod Mod4`, direction keys, `$term`)
2. All key bindings (workspace 1-10, focus movement, layout, resize mode, multimedia keys) — expect ~60 `bindsym` lines
3. `exec_always waybar` (already present)
4. `include /etc/sway/config.d/*` at the bottom (for systemd integration)
5. DO NOT include the `bar {}` block from the system config

See main skill for the full sway config structure and `$mod` ordering pitfall.

### Separator module

```json
"custom/sep": { "format": "│", "tooltip": false }
```

CSS: `#custom-sep { padding: 0 3px; color: #555; font-size: 14px; }`

### Taskbar visual states (macOS Dock dots)

```css
/* Focused window: blue underline dot */
#taskbar button.active {
  border-bottom: 3px solid #5294e2;
  border-radius: 0;
}
/* Background windows: grey underline dot */
#taskbar button:not(.active) {
  border-bottom: 3px solid rgba(255,255,255,0.2);
  border-radius: 0;
}
#taskbar button.urgent { background: rgba(224,82,82,0.2); }
#taskbar button:hover { background: rgba(255,255,255,0.1); border-radius: 4px; }
```

GTK3 CSS does NOT support `::after` pseudo-elements. Use `border-bottom` for the macOS-style active indicator.

### PWA .desktop StartupWMClass (taskbar shows correct icons)

Chrome PWA windows in sway have `app_id = chrome-<extension-id>-Default` (e.g. `chrome-gaclnekabaleococgnghmjhcdfipepjj-Default`). Without `StartupWMClass`, the taskbar shows Chrome's icon for all PWA windows. Add this to each PWA `.desktop` file:

```
StartupWMClass=chrome-<same-extension-id-as-in-app_id>-Default
```

Note: the `Extends=` field does NOT work for this (sway/wlroots matches `app_id` directly, not through freedesktop categories). `StartupWMClass` must match the **exact** `app_id` string the window exposes at runtime.

## sway clean-reload pattern (avoids duplicate waybar on sway reload)

### Bluetooth module crashes on Waybar v0.12.0 (Debian 13)

The `bluetooth` module in Waybar 0.12.0 **crashes** with `unhandled exception: argument not found` when `tooltip-format` contains `{controller_alias}` or `{num_connections}`, or when `format-connected` uses `{device_count}`. Safe config for v0.12.0:

```json
"bluetooth": {
  "format": " {status}",
  "format-connected": "",        // static text only, NO placeholders
  "on-click": "blueman-manager"   // NO tooltip-format key at all
}
```

If `tooltip-format` is set, WAYBAR HARD CRASHES with signal 133. No warning, no fallback. This was fixed in later releases, but Debian 13 ships 0.12.0.

### Tailscale module: text output is more intuitive than icons

Users may find the `` (antenna) icon confusing. A text-based approach is clearer:

**Script** (`~/.local/bin/ts-status.sh`):
```bash
#!/bin/bash
if output=$(tailscale status 2>/dev/null | head -4); then
  if echo "$output" | grep -q "100\\."; then
    count=$(echo "$output" | grep -cP "^100\\.")
    ips=$(echo "$output" | awk '{print $1}' | grep '100\\.' | head -3 | tr '\\n' ' ')
    echo "{\"text\":\"TS ${count}\",\"alt\":\"connected\",\"tooltip\":\"Tailscale\\n$ips\"}"
    exit 0
  fi
fi
echo "{\"text\":\"TS ✗\",\"alt\":\"disconnected\",\"tooltip\":\"Tailscale 未运行\"}"
```

**CSS**: `#custom-tailscale { color: #a78bfa; }` / `.disconnected { color: #555; }`

Note that with `return-type: json` and `format: "{icon}"` + `format-icons`, the script's `"alt"` field selects the icon. With text output (no format-icons), set `format: "{}"` to pass through the script text directly, or omit `format` entirely (defaults to `{}`).
