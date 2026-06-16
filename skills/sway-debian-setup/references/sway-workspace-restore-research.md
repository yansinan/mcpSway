# Sway Workspace Restore — Research Survey

Survey date: 2026-06-14 (initial), 2026-06-15 (follow-up session)
Source: web search + GitHub API + tool READMEs + live sway session capture

## The Problem

User wants sway to persist window content and layout across reboots — restore all previously open windows to their original workspaces after restart.

## The Core Limitation

**Sway does NOT support `append_layout`** — the i3 feature that restores saved layout JSON. Without it, there is no way to replay the exact tiling geometry (split orientation, split ratios, floating positions) after restart.

- Issue: swaywm/sway#1005 (opened 2016-12-23, still open)
- Reddit (2026): "there is no swaymsg append_layout and there likely never will be"
- Reason: wlroots architecture does not support injecting placeholder windows into the tree the way i3 did via X11's `_NET_WM_WINDOW_TYPE` / `_NET_WM_STATE`

## Tool Survey

### i3-resurrect (JonnyHaystack/i3-resurrect)
- **Language**: Python
- **Stars**: ~600
- **Saves**: layout JSON + program launch cmds (from psutil)
- **Restores**: i3's built-in layout restore + xdotool to "re-swallow" windows
- **Sway compatible?**: **NO** — uses xdotool (X11-only) and i3's `append_layout` (not in sway)
- **Conclusion**: X11 only, not portable to Wayland

### swayrst (Nama/swayrst)
- **Language**: Rust
- **Availability**: AUR (`yay -S swayrst-git`), GitHub Actions releases
- **Saves**: workspace↔display mapping + which windows are on which workspace (from `swaymsg -t get_tree`)
- **Restores**: moves already-open windows to their correct workspaces
- **Limitation**: works with ALREADY OPEN windows only — does NOT launch apps. After reboot, windows don't exist yet, so swayrst can't help.
- **Use case**: switching between display profiles (desk ↔ mobile) without losing window placement

### sway-toolwait (rorosen/sway-toolwait)
- **Language**: Rust
- **Availability**: `cargo install sway-toolwait`, AUR
- **What it does**: launches a command and blocks until a new window appears on the specified workspace
- **Not**: a session save/restore tool. It's an **autostart ordering utility**.
- **Sway compatible?**: Yes — uses `swaymsg subscribe` to watch for window creation events
- **Use case**: when you have multiple `exec` lines in sway config, this ensures they appear in the right order on the right workspaces

### swayr (swaywm/swayr)
- **Language**: Rust
- **Availability**: `cargo install swayr`, AUR
- **Features**: window switcher (Alt+Tab style), workspace navigation
- **`record-window-layout`**: saves current layout to JSON
- **`restore-window-layout`**: recreates placeholder windows via... (limited — doesn't launch apps)
- **Sway compatible?**: Yes — uses sway IPC
- **Limitation**: restore only creates empty placeholders, doesn't relaunch programs

## Community Approaches

### 1. Static autostart (most common)
Directly in `~/.config/sway/config`:
```
workspace 1
exec foot
workspace 2
exec firefox
```

This is the most robust approach — no external dependencies, works reliably across reboots.

### 2. for_window + assign rules
```
assign [app_id="firefox"] → workspace 2
assign [app_id="code"] → workspace 3
```
Then `exec` each app without workspace targeting. `assign` rules catch them wherever they appear.

### 3. Custom save/restore script
Save: `swaymsg -t get_tree | jq ...` to extract app_id per workspace
Restore: read saved list, switch to workspace, launch app

## Quoted Excerpts

From i3-resurrect README:
> "xdotool is used to make i3 see existing windows as new windows. This is necessary on older i3 versions for matching by window title..."

From swaywm/sway issue #1005 (2016):
> "Layout save/restore is an i3 feature that serializes your layout to JSON and attempts to arrange windows in the same way in a later session."

From r/swaywm (2026):
> "there is no swaymsg append_layout and there likely never will be"

## Conclusion

No mature "save everything and restore after reboot" tool exists for sway on Wayland. The two viable approaches are:
1. **Static autostart** (config-based, most reliable)
2. **Custom dynamic save/restore script** (flexible, requires maintenance)

Neither restores window CONTENT (that's app-level), but both restore the WORKSPACE LAYOUT.

A complete reference implementation in Python (combined save + restore + 5-minute daemon) is in `templates/sway-session.py`, and a Python tree parser for environments without `jq` is in `scripts/sway-tree-parser.py`.

## Real-World Layout (from dr's session, 2026-06-14)

Captured from a Debian 13 machine with sway 1.12+, Kaby Lake iGPU, Philips BDM4350 USB-C dock.

### Display configuration

| Output | Monitor | Resolution | Position | Active ws |
|---|---|---|---|---|
| eDP-1 | LG Display 0x0582 (tablet, rotated 270°) | 1000×1500 | (0, 660) | WS 2 |
| DP-5 | Philips BDM4350 (USB-C dock) | 3840×2160 | (1000, 0) | WS 1 |

### WS 2 (tablet screen) — fullscreen
- Chrome PWA running Hermes WebUI (`--app-id=ggodlfkjnmplcjoknpmbaadcecnfflfd`)

### WS 1 (external monitor) — splith, fullscreen
```
┌───────────────────────────┬──────────────────────┐
│  [tab] code-server (PWA)  │  [tab] foot          │
│  [tab] HERMES (PWA)       │                      │
│  [tab] Google Search      ├──────────────────────┤
│                           │  [tab] NotebookLM    │
│  ~2551px / ~1289px        │  [tab] Tailscale    │
│                           │  [tab] Tech          │
└───────────────────────────┴──────────────────────┘
         splith                         │
                                  splitv 上下
```

### Process breakdown

| PID | Type | app_id | Command |
|---|---|---|---|
| 295114 | Chrome PWA | chrome-ggodlf... & chrome-gjcmcpl... | `chrome --app-id=ggod...` (Hermes WebUI + NotebookLM — two PWA windows in ONE process) |
| 295643 | Terminal | foot | `foot` (the session interacting with Hermes) |
| 295749 | Chrome main | google-chrome | `chrome` (shared instance for all non-PWA tabs) |
| 360601 | Chrome CDP | google-chrome | `chrome --remote-debugging-port=9222 --ozone-platform=wayland` (under Hermes control) |

### Key observations

1. **Chrome PWAs get unique app_ids** (e.g. `chrome-ggodlfkjnmplcjoknpmbaadcecnfflfd-Default`) that survive restarts — good for targeting with `for_window` rules.

2. **Multiple Chrome instances share app_id "google-chrome"** but differ in launch flags — `/proc/PID/cmdline` is essential to distinguish them.

3. **Same PID → same cmdline → can host multiple PWA windows**. PID 295114 hosts both Hermes WebUI and NotebookLM as separate app_ids. They share `--user-data-dir` and `--app-id=ggod...`. The cmdline dedup in restore scripts will only launch this once. The second PWA (NotebookLM) may or may not be recovered by Chrome's own session logic.

4. **The foot terminal running Hermes itself is part of the session layout** — restoring the layout creates a terminal session for the agent.

5. **No floating windows** — straightforward tiling layout, relatively flat structure.

### What the restore script achieves for this layout

| Expectation | Achieved? |
|---|---|
| WS2: Hermes PWA fullscreen on tablet | ✓ |
| WS1: main Chrome opens, tabs auto-restore | ✓ |
| WS1: CDP Chrome on correct workspace | ✓ |
| WS1: foot terminal | ✓ |
| WS1: 2551/1289 split ratio | ✗ (defaults to 50/50) |
| WS1: tabbed group nesting | Partial (launch order arranges, but exact nesting may differ) |
| NotebookLM PWA reopens | ✗ (same PID/cmdline as Hermes PWA) |
| Split proportions | ✗ (sway IPC cannot set width_fraction) |
