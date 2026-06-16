---
name: sway-debian-setup
source:
  - https://swaywm.org/download
  - https://manpages.debian.org/bookworm/sway/sway.5.en.html
description: "Install, configure, and troubleshoot Sway (Wayland compositor) on Debian — basic setup, dual monitor, display auto-switching, app launcher, common pitfalls."
tags: [sway, wayland, debian, display, input-method, bluetooth]
---

# Sway on Debian — Setup & Configuration

Trigger: user asks to install Sway, configure dual monitors, set up Wayland desktop, or troubleshoot Sway display issues.

## Installation

```bash
sudo apt install -y sway foot
```

Foot is Sway's default terminal. It runs natively on Wayland (no XWayland), supports server-side decorations, and is lightweight.

### Dynamic terminal titles (path + running command)

To show the current directory (idle) and running command in the window title, add this to `~/.bashrc` after the PS1 block:

```bash
case "$TERM" in
xterm*|rxvt*|foot*|*-256color*)
    PS1="\[\e]0;${debian_chroot:+($debian_chroot)}\u@\h: \w\a\]$PS1"
    trap 'printf "\033]0;%s → %s\007" "${BASH_COMMAND##*/}" "${PWD/#$HOME/~}"' DEBUG
    ;;
*)
    ;;
esac
```

The PS1 embeds an OSC escape sequence that sets the title on every prompt. The DEBUG trap overrides it to `command → ~/path` during execution, and the PS1 resets it back after. **Use single backslashes** `\[\e]0;` — double backslashes `\\[\\e]0;` are literal and won't work. Full details: **`references/bash-dynamic-terminal-title.md`**.

### foot configuration file
```bash
# Display management
sudo apt install -y wdisplays kanshi wlr-randr

# App launcher (Wayland-native) — recommend fuzzel for desktop files
# fuzzel (recommended): Wayland-native (wlroots layer-shell, Cairo rendering),
#   ~346KB. Scans .desktop files — finds Chrome PWAs, system apps, flatpaks.
#   Supports icons, fuzzy search. Config: fuzzel.ini.
# tofi: ~100KB, Wayland-native, layer-shell, text-only, dmenu-style.
#   No icons, prefix or fuzzy matching. Config: tofi.conf.
# wofi: GTK3-based, ~172KB. CSS theming, supports icons.
#   Config: wofi/style.css. More themeable than fuzzel but heavier.
# bemenu: ~100KB, layer-shell. Only scans PATH executables — no .desktop.
#   Pure text, no config file (env vars only).
# rofi: ~800KB+, X11 native (needs XWayland on sway — focus/scale issues).
#   Most feature-rich (drun/run/window/ssh modes). NOT recommended on sway.
# For most users: `sudo apt install -y fuzzel`
# Full comparison: skill_view(name='sway-debian-setup', file_path='references/app-launcher-comparison.md')
sudo apt install -y fuzzel
```

## Window Rules (for_window) — Criteria Syntax & Behavior

### Syntax — use `=`, value IS the regex

In sway, criteria attributes (`app_id`, `class`, `title`, etc.) use the **`=` operator**. The value is automatically treated as a PCRE2 regex for attributes that "can be a regular expression." **No tilde (`~`) operator needed** — that's old i3 syntax.

```ini
# ✓ CORRECT — sway reads the value as PCRE2 regex
for_window [app_id="^chrome-"] border pixel 1
for_window [app_id="google-chrome"] border pixel 1   # exact match

# ✗ BROKEN — parse errors in sway config
for_window [app_id~"^chrome-"] border pixel 1
for_window [app_id ~ "^chrome-"] border pixel 1
```

Several attributes support regex: `app_id`, `class`, `title`, `instance`, `shell`, `workspace`, `tag`, `sandbox_engine`, `sandbox_app_id`. Full reference: **`references/for_window-criteria.md`**.

### for_window only applies to NEW windows

Existing windows are not affected. To apply a command immediately:
```bash
swaymsg '[app_id="foot"]' border pixel 1
swaymsg '[app_id="google-chrome"]' border none
```

### border pixel vs tabbed/stacking titles

`border pixel 1` removes the **window-level** title bar. It does NOT remove **container-level** tabbed/stacking tab headers — those are parent container decorations. If you see a persistent "title bar" in a tabbed layout, that's the tab header. To remove it, change the layout:
```bash
swaymsg layout toggle split
```

### Stale SWAYSOCK

From a script or shell outside sway's own `exec`, `$SWAYSOCK` may point to a dead socket after sway restarted:
```bash
export SWAYSOCK=$(ls -t /run/user/1000/sway-ipc.*.sock | head -1)
```

## Basic Configuration

Sway reads `~/.config/sway/config` first, then falls back to `/etc/sway/config`.

### Config structure: include order matters

The default `/etc/sway/config` defines critical variables (`$mod`, `$term`, `$left`, `$right`, etc.) and sets up standard keybindings. **Always include it first** so variables are available to your custom rules:

```
include /etc/sway/config

# Your custom rules go here — they override defaults
bindsym $mod+Return exec foot
```

**Wrong** (will error "unknown $mod"):
```
bindsym $mod+Return exec foot
include /etc/sway/config
```

### Overriding bindings — use `unbindsym`, don't guess flags

If the default config already binds a key combo you want to change:

```
# Remove the old binding first, then add the new one
unbindsym $mod+d
# fuzzel: scans .desktop files (Chrome PWAs, system apps). bemenu: PATH only.
bindsym $mod+d exec fuzzel
```

**There is no `--overwrite` flag.** Check `man 5 sway` before guessing flags.

### Minimal working config

```
include /etc/sway/config
exec_always killall kanshi 2>/dev/null
exec_always kanshi
unbindsym $mod+d
# fuzzel: scans .desktop files (Chrome PWAs, system apps). bemenu: PATH only.
bindsym $mod+d exec fuzzel
```

## Dual Monitor Setup

### GUI method (wdisplays)

```bash
# Run inside Sway terminal
wdisplays
```

Drag monitors to arrange, click to set resolution. **Settings are NOT saved** — wdisplays applies changes to the running compositor's memory only. Restarting sway loses them. Persistent configuration requires writing to sway config or kanshi config.

### Manual output config

Find output names:

```bash
# Find current output names
swaymsg -t get_outputs
```

**⚠ Port names change across reboots.** Output names like `DP-2`, `DP-3`, etc. can fluctuate when:
- The cable is re-seated
- The dock is reconnected
- The kernel/driver is updated
- The monitor EDID changes

**Stable alternative:** use the monitor's make/model/serial tuple:

```bash
# Get the tuple from swaymsg output
swaymsg -t get_outputs | grep -E '\"make\"|\"model\"|\"serial\"'
```

Example config using stable identity:
```bash
output "Philips Consumer Electronics Company PHL BDM4350 0x000032DB" mode 3840x2160@60Hz position 1000 0 scale 1.0
output eDP-1 mode 3000x2000@60Hz position 0 660 scale 2.0 transform 270

workspace 1 output "Philips Consumer Electronics Company PHL BDM4350 0x000032DB"
workspace 2 output eDP-1
```

### Auto-switching (kanshi)

Kanshi detects monitor connect/disconnect and applies the right profile.

Install: `sudo apt install -y kanshi`

Config file: `~/.config/kanshi/config`

```bash
profile dual {
    output eDP-1 enable
    # ⚠ Use the CURRENT output name — verify with `swaymsg -t get_outputs` first
    output DP-2 enable mode 3840x2160@60Hz position 3000 0
}

profile single {
    output eDP-1 enable
    output DP-2 disable
}
```

Add to Sway config:

```
exec_always killall kanshi 2>/dev/null
exec_always kanshi
```

### Troubleshooting: monitor detected but no signal

If `swaymsg -t get_outputs` or `wlr-randr` shows a connected display but the physical monitor shows no signal, follow this structured diagnosis flow. **Test from the simplest step first** — each step narrows the root cause:

#### Quick sanity checks (1–3)

1. **Port name changed** — Kernel/DRI enumeration can rename outputs after reboot or cable re-seat. Your config might reference `DP-3` while the monitor is now on `DP-2`. Run `swaymsg -t get_outputs` to see current names.

   **Prevent this** by using the monitor's make/model/serial tuple instead of the ephemeral DP-N name:
   ```
   output "Philips Consumer Electronics Company PHL BDM4350 0x000032DB" mode 3840x2160@60Hz position 1000 0 scale 1.0
   ```
   Get the tuple from `swaymsg -t get_outputs` (look for `make`, `model`, `serial` fields).

2. Check cable/adapter — 4K@60Hz needs DP 1.2+ capable cable
3. Try lower resolution/refresh rate: `swaymsg 'output DP-2 mode 1920x1080@60Hz'`

#### Diagnosis flow (4–7 — run in order)

4. **Check DPMS/power state** — Re-enable if the display was toggled:
   ```bash
   swaymsg 'output DP-<N> dpms on'
   ```
   Verify: `swaymsg -t get_outputs | grep -E '\"active\"|\"dpms\"|\"power\"'`

5. **Kernel-level connector check** — Confirm the kernel sees the display as connected:
   ```bash
   cat /sys/class/drm/card0-$(swaymsg -t get_outputs 2>/dev/null | grep -oP '\"name\": \"\K[^\"]+' | grep DP)/status
   cat /sys/class/drm/card0-$(swaymsg -t get_outputs 2>/dev/null | grep -oP '\"name\": \"\K[^\"]+' | grep DP)/edid | wc -c
   ```
   Should say `connected` and `>0` bytes (256 for 4K EDID). If the kernel says `connected` with a valid EDID, the GPU and cable are fine — the issue is on the compositor or driver configuration side.

6. **VT switch workaround** — Switch to another VT (`Ctrl+Alt+F2`) and back (`Ctrl+Alt+F1`). This triggers a DRM reinitialization that can kickstart the external display (GitHub swaywm/sway#8517).

7. **`WLR_DRM_NO_MODIFIERS=1` workaround** — On Intel iGPU, atomic modeset with buffer modifiers can fail for some displays (GitHub swaywm/sway#6167). The log shows `Atomic commit failed (modeset): Invalid argument`:

   Set in `~/.config/environment.d/*.conf`:
   ```bash
   echo 'WLR_DRM_NO_MODIFIERS=1' >> ~/.config/environment.d/im.conf
   ```

   ⚠ **TTY-launched sway won't inherit `environment.d/`** — The `~/.config/environment.d/` directory only affects processes started by the systemd user manager. If you launch sway from a TTY login shell (common pattern), set the env var in `~/.bash_profile` or `~/.profile` instead:
   ```bash
   echo 'export WLR_DRM_NO_MODIFIERS=1' >> ~/.bash_profile
   ```
   Then restart sway: `swaymsg exit; export WLR_DRM_NO_MODIFIERS=1; sway`

   If still black after this, move on to kernel parameter toggling.

#### Kernel parameter toggling (8 — requires reboot)

8. **`i915.enable_dp_mst` kernel parameter** — Trial-and-error on Kaby Lake iGPU + USB-C dock:

   - With `i915.enable_dp_mst=0`: Fixes some docks, breaks others.
   - With MST enabled (default, remove the parameter): Some docks need MST for 4K@60 DP link training. Others go black.
   - **Both states may fail** depending on kernel version. If neither works, move to step 11 (Live USB kernel test).

   Toggle:
   ```bash
   cat /proc/cmdline | grep enable_dp_mst
   # Add: sudo sed -i 's/quiet/quiet i915.enable_dp_mst=0/' /etc/default/grub
   # Remove: sudo sed -i 's/ i915.enable_dp_mst=0//' /etc/default/grub
   sudo update-grub && sudo reboot
   ```

#### Compositor isolation (9–10 — run from TTY, NOT inside sway)

9. **Direct DRM test (`modetest`)** — Install `libdrm-utils` then test the display directly via the kernel's DRM interface:

   ```bash
   sudo apt install -y libdrm-utils
   modetest -M i915 -c | grep connected
   ```

   The output shows lines like:
   ```
   118\t117\tconnected\tDP-2          \t950x540\t...
   ```
   The first number (118) is the **connector ID**. Force a kernel-level modeset:

   ```bash
   sudo modetest -M i915 -s 118:3840x2160-60
   ```
   - If the monitor **lights up** (shows a test pattern) → hardware/kernel are fine, issue is wlroots-specific
   - If it **stays black** even on modetest → issue is driver-level (i915 dock compatibility, kernel config, BIOS firmware)

   **Write this to a script** when debugging from TTY (no paste available):
   ```bash
   cat > ~/t.sh << 'EOF'
   #!/bin/bash
   sudo modetest -M i915 -s 118:3840x2160-60
   EOF
   chmod +x ~/t.sh
   sh ~/t.sh
   ```

10. **Alternative compositor test (KWin Wayland)** — Sway uses wlroots. Try KWin (KDE's own compositor, independent of wlroots) to isolate whether the issue is wlroots-specific:

    ```bash
    sudo apt install -y kwin-wayland
    ```

    From TTY1 (exit sway first):
    ```bash
    killall sway
    kwin_wayland foot   # starts compositor + foot terminal
    ```

    In foot, check detection and force re-enable:
    ```bash
    kscreen-doctor --outputs
    kscreen-doctor output.DP-2.disable
    sleep 2
    kscreen-doctor output.DP-2.enable
    ```

    If KWin lights it → wlroots bug. If KWin also stays black → kernel/driver issue.

    Exit: Ctrl+Alt+F2 → `killall kwin_wayland` → Ctrl+Alt+F1.

11. **Live USB kernel test** — If all compositors AND modetest fail, boot a Live USB (Ubuntu 24.04+, Debian 12+). If the monitor works there but not on your installed system, the i915 driver in your kernel has a regression for your GPU + dock combination. Solution: use a newer or older kernel (backports, liquorix, or downgrade to Debian 12s 6.1.x).

12. **i915 DP debugfs — force link retrain (no reboot needed)**

    ```bash
    sudo apt install -y intel-gpu-tools
    # Check capabilities
    sudo cat /sys/kernel/debug/dri/0/DP-2/i915_dp_max_lane_count  # "4" = HBR2
    sudo cat /sys/kernel/debug/dri/0/DP-2/i915_dp_max_link_rate   # "540000" = 5.4 Gbps
    # Force lanes + rate, then retrain
    echo 4 | sudo tee /sys/kernel/debug/dri/0/DP-2/i915_dp_force_lane_count
    echo 540000 | sudo tee /sys/kernel/debug/dri/0/DP-2/i915_dp_force_link_rate
    echo 1 | sudo tee /sys/kernel/debug/dri/0/DP-2/i915_dp_force_link_retrain
    ```

13. Switch the monitor's physical input source via OSD buttons.

14. Try a different port on the computer.

### Perceived 30Hz despite sway reporting 60Hz

If the external monitor is working (sway shows 4K@60Hz) but the cursor feels sluggish, laggy, or "like 30Hz":

**GPU overload** — Kaby Lake iGPU rendering 4K@60 alongside a high-DPI internal display (3000x2000@2x = 6000×4000 render buffer) is near the iGPU's fill rate limit. Sway shows 60Hz but frame delivery drops.

Diagnose — disable internal display:
```bash
swaymsg 'output eDP-1 disable'
```
If cursor smoothness improves, fix with:
- Lower internal display resolution or scale (e.g. `output eDP-1 scale 1.0`)
- Use external display alone for heavy work

**Set max_render_time** — Sway queues frames up to the VSync deadline. Tighter deadline reduces perceived lag:
```bash
swaymsg 'output DP-<N> max_render_time 1'
```

**Monitor input lag** — Some 4K displays (Philips BDM4350 etc.) have ~15-20ms inherent input lag at 4K@60. Compare mouse movement on the laptop screen — if laptop screen is instant but external has delay, it's the panel.

**VSync pipeline** — `allow_tearing=false` adds frame buffering. `allow_tearing true` can reduce latency:
```bash
swaymsg 'output DP-<N> allow_tearing true'
```

## Useful Tools

| Tool | Purpose |
|---|---|
| `wdisplays` | GUI display arranger (settings NOT saved across restarts) |
| `kanshi` | Automatic profile switching on plug/unplug |
| `wlr-randr` | CLI display control (like xrandr for Wayland, sway-native) |
| `bemenu` / `fuzzel` | Wayland-native app launcher — bemenu (PATH only), fuzzel (.desktop + icons) |
| `bemenu-run` | PATH-only launcher (from bemenu) — doesn't find Chrome PWAs or flatpaks |
| `kscreen-doctor` | CLI display control for KWin (from `apt install kscreen`) |
| `intel-gpu-tools` | Intel GPU debug tools, i915 debugfs access for DP link retrain |
| `swaymsg -t get_outputs` | List outputs and their status |
| `journalctl -f -o cat | grep dp` | Watch display hotplug events |
| Mutter DBus API | `references/mutter-dbus-display-config.md` — query/force-enable displays via the gnome-shell compositor interface |

## Sway Keybindings (default)

| Key | Action |
|---|---|
| Super+Enter | Open terminal (foot) |
| Super+D | App launcher (fuzzel for .desktop apps, or bemenu-run for PATH) |
| Super+Shift+Q | Close window |
| Super+arrows | Focus window direction |
| Super+Shift+C | Reload config |
| Super+number | Switch workspace |
| Super+Shift+number | Move window to workspace |

## Chinese Input Method (fcitx5)

Setup fcitx5 (Pinyin, Shuangpin, Wubi, etc.) on Sway/Wayland.

### Installation

```bash
# Chinese fonts — Noto CJK recommended (comprehensive: Sans + Serif, 4 weights,
# covers SC/TC/JP/KR). Alternative: fonts-wqy-microhei (lighter, WenQuanYi).
sudo apt install -y fonts-noto-cjk

# Core + Chinese engines + GUI config + all GTK/Qt frontends
# fcitx5-chinese-addons provides: pinyin (标准拼音), shuangpin (双拼),
# wubi (五笔), wubi-pinyin (五笔拼音), cangjie (仓颉), zhengma (郑码),
# erbi (二笔), quick (速成), and cloudpinyin (cloud candidates).
sudo apt install -y fcitx5 fcitx5-chinese-addons \
  fcitx5-config-qt fcitx5-frontend-all
```

**⚠ No separate `fcitx5-wayland` package exists on Debian.** fcitx5 works natively on Wayland through the compositor's `zwp_input_method` / `zwp_text_input` protocols — no extra Wayland IM module is needed. The core daemon handles Wayland integration directly. Native Wayland apps (foot, GTK4, Qt6) communicate via these protocols; XWayland apps use the `GTK_IM_MODULE` / `QT_IM_MODULE` env vars. If the user asks about "fcitx5-wayland", they likely mean this native support path.

This pulls in: pinyin via `fcitx5-chinese-addons` (on Debian 13 the `fcitx5-pinyin` package is not separate — pinyin engine comes from `fcitx5-chinese-addons`), `fcitx5-config-qt` (GUI config tool), and frontend IM modules for GTK3/4 + Qt5/6.

**Don't skip the font package.** Without a CJK font, Chinese text shows as empty squares (tofu) in terminals, browser, and UI. Rebuild the font cache after install: `fc-cache -fv`.

**Faster install (without config-qt GUI):**
```bash
sudo apt install -y fonts-noto-cjk fcitx5 fcitx5-chinese-addons \
  fcitx5-frontend-gtk3 fcitx5-frontend-gtk4 \
  fcitx5-frontend-qt5 fcitx5-frontend-qt6
```

### Environment variables

These tell GTK, Qt, XWayland, SDL, and GLFW apps to route text input through fcitx5.

**In `~/.config/environment.d/im.conf`** (recommended — Wayland-native, works system-wide):

```
GTK_IM_MODULE=fcitx
QT_IM_MODULE=fcitx
XMODIFIERS=@im=fcitx
SDL_IM_MODULE=fcitx
GLFW_IM_MODULE=fcitx
```

This is the proper Wayland-compatible approach via systemd user environment.

**In `~/.config/sway/config`** (only the launcher line is needed):

```
exec_always fcitx5 -d --replace 2>/dev/null
```

⚠ **DO NOT use `set` for env vars in Sway config.** `set` in Sway defines Sway internal variables only (e.g. `set $mod Mod4`) — it cannot set system environment variables. Doing `set GTK_IM_MODULE fcitx` causes `sway --validate` to error with `"variable must start with $"` and prevents Sway from loading the config. Use `~/.config/environment.d/` instead.

**System-wide via im-config:**

```bash
im-config -n fcitx5
```

### Basic usage

Reload Sway (`mod+Shift+C`) or start manually:

```bash
fcitx5 -d
```

- `Ctrl+Space` — toggle Chinese/English
- `Shift` — toggle Chinese/English punctuation in pinyin mode
- `+`/`-` or `[`/`]` — page through candidate words

**Adding Pinyin to the active input method list:**

Method A (GUI): `fcitx5-config-qt`, uncheck "Only Show Current Language" at bottom, find "Pinyin" in the left panel, select it, click `<<` to add to the right panel.

Method B (edit profile directly):

```bash
pkill fcitx5   # ⚠ MUST stop fcitx5 first!
```

Edit `~/.config/fcitx5/profile`:

```
[Groups/0/Items/0]
Name=keyboard-us
Layout=

[Groups/0/Items/1]
Name=pinyin
Layout=
```

Then start fcitx5 again:

```bash
fcitx5 -d
```

## 蓝牙

Setup Bluetooth on Sway/Wayland — pairing, tray management, and audio.

### Installation

```bash
# Core Bluetooth stack (includes bluetoothctl, bluetoothd, etc.)
sudo apt install -y bluez

# ⚠ bluez-utils is NOT a separate package on Debian 13+.
# It was merged into the base bluez package. Installing bluez alone
# gives you bluetoothctl, bluetoothd, hciconfig, rfkill, etc.

# Bluetooth tray manager — system tray icon for pairing/connecting
sudo apt install -y blueman

# Bluetooth audio for PipeWire — required for Bluetooth headphones/speakers
# Not needed if you only use Bluetooth keyboard/mouse.
sudo apt install -y libspa-0.2-bluetooth

# Optional: notification daemon — shows pairing requests, file transfer
# notifications from blueman. If you don't have any notification daemon
# (mako/dunst/notification-daemon), pairing still works via blueman-manager
# GUI but you won't get pop-up prompts.
#   sudo apt install -y mako
```

### Sway config

Add to `~/.config/sway/config`:

```
exec_always blueman-applet
```

After adding, reload sway: `swaymsg reload` (only works from inside a sway session).

### Usage

- System tray icon appears in swaybar (top/right by default)
- Click tray icon → scan, pair, connect/disconnect
- `blueman-manager` — full GUI management window
- `bluetoothctl` — CLI control (scan on, devices, pair, trust, connect)

### Service status

```bash
systemctl status bluetooth
# Active: active (running) — should be enabled by default
```

## Workspace Autostart & Session Persistence

Save / restore window layout and app placement after reboot.

### The core limitation

**Sway does NOT support `append_layout`** (i3 feature used for layout restoration from JSON). This is a long-standing limitation ([swaywm/sway#1005](https://github.com/swaywm/sway/issues/1005), open since 2016). There is no way to save the exact tiling geometry (split vs stack, split ratios) and replay it after restart.

### What can be done

Two approaches that work on pure Wayland (no X11):

#### Approach A: Static autostart (most reliable)

Define in `~/.config/sway/config` which workspace each app starts on:

```
workspace 1
exec foot

workspace 2
exec firefox

workspace 3
exec code

workspace 4
exec nautilus
workspace 4
exec foot
```

Sway creates the workspace on first reference, runs the `exec`, and the window appears on that workspace. Use `for_window` rules for layout hints (`splith`, `splitv`, `floating enable`).

**Pitfall**: apps that fork/background (most GUI apps) don't block — a second `exec` on the same workspace may appear before the first finishes. Use `sway-toolwait` for strict ordering (see below).

#### Approach B: Dynamic save/restore script

Save the workspace-to-app mapping from a live session, then replay at startup.

**Save script** (`~/.config/sway/save-session.sh`):

```bash
#!/bin/bash
mkdir -p ~/.sway-session
swaymsg -t get_tree > ~/.sway-session/layout.json

# Extract app_id per workspace
for ws in $(swaymsg -t get_workspaces --raw | jq -r '.[].name'); do
  swaymsg -t get_tree --raw | jq -r "
    .. | select(.type? == \"con\" and .app_id? != null) |
    select(.workspace? // (.window_properties?.workspace? // .name) == \"$ws\") |
    .app_id
  " > \"/tmp/sway-session-ws-$ws.txt\"
done
```

**Restore script**: add `exec ~/.config/sway/restore-session.sh` to sway config. The restore script reads saved app_id lists and launches them on the correct workspaces. See `references/sway-workspace-restore-research.md` and `templates/sway-session.py` for a complete reference implementation with cmdline-based launch command recovery, dynamic SWAYSOCK detection, and a 5-minute daemon loop.

### Combined save-restore-daemon script (Python, recommended)

For users who want a unified script that: (a) restores the last saved session on sway start, (b) automatically saves the current layout every 5 minutes as a background daemon, and (c) de-duplicates launch commands across workspaces:

Reference implementation: `templates/sway-session.py`

Key design decisions in the reference implementation:
1. **Single entry point** — no args = restore → daemonize; `--save`, `--restore`, `--daemon` for manual use
2. **Cmdline-based dedup** — tracks launched commands by their shortened form (not PID, which changes between boots). Same cmdline on two workspaces only executes once.
3. **Dynamic SWAYSOCK** — finds the current socket via glob each call, sidestepping stale env vars after sway restart (see "Stale SWAYSOCK" below)
4. **Persistent save file** — MUST NOT use `/tmp` (wiped on reboot). Save to `~/.config/sway/sway-session.json`
5. **Chrome PWA handling** — `shorten_cmd()` preserves `--app-id=`, `--user-data-dir=`, `--remote-debugging-port=`, `--ozone-platform=wayland` flags. Chrome tabs within the same instance restore themselves via Chrome's own session restore.
6. **Fullscreen restoration** — re-applies `fullscreen enable` per workspace if the original was fullscreen
7. **5-minute daemon** — saves immediately on start, then every 300s in a while loop

Restore limitations (same for all sway session tools):
- **No `append_layout`** — exact split ratios and container nesting are not recoverable. Startup order across workspace-switch boundaries determines layout, sway auto-splits.
- **Second PWA windows in the same Chrome profile** (e.g. NotebookLM alongside Hermes WebUI) share the underlying PID and cmdline. The script launches each unique cmdline once. Chrome's own session restore may or may not recover the secondary PWA.
- **Save file must be persistent** — Not `/tmp` (cleared on reboot). Location: `~/.config/sway/sway-session.json` (alongside sway config).

Sway config integration:
```
exec ~/Scripts/sway-session.py
```

### Existing tools (research results)

| Tool | Status | Capability | Sway on Wayland? |
|---|---|---|---|
| **i3-resurrect** (Python, ~600 stars) | X11 only | Save/restore layout + process launch cmd | **No** — uses xdotool + i3's `append_layout`, neither exists in sway |
| **swayrst** (Rust, AUR) | Available | Save workspace↔monitor mapping, move open windows | **Partial** — doesn't launch apps, only moves them |
| **sway-toolwait** (Rust, AUR/cargo) | Available | Launch an app and wait for its window on a specific workspace | **Yes** — useful for startup ordering alongside static autostart |
| **swayr** (Rust, cargo) | Available | Window switcher with `record-window-layout` / `restore-window-layout` | **Partial** — restore creates empty placeholder windows, doesn't relaunch apps |

**Reference**: `references/sway-workspace-restore-research.md` for the full research survey, tool readme excerpts, and a real-world layout case study.

### Stale SWAYSOCK after sway restart

When sway restarts (e.g. after crash, config reload, or explicit `swaymsg exit`), the shell's `$SWAYSOCK` environment variable still points to the old socket. The new sway process creates a new socket with a different PID suffix:

```
/run/user/1000/sway-ipc.1000.1552.sock  (old — stale)
/run/user/1000/sway-ipc.1000.294966.sock (new — current)
```

Fix — find the current socket dynamically:
```bash
export SWAYSOCK=$(ls -t /run/user/1000/sway-ipc.*.sock | head -1)
```

Or in Python:
```python
import glob
socks = sorted(glob.glob("/run/user/*/sway-ipc.*.sock"))
if socks:
    os.environ["SWAYSOCK"] = socks[-1]
```

### Launch command extraction for save scripts

When saving session state, capturing the app_id alone is insufficient for Chrome PWAs — they share the same app_id ("google-chrome") but have different launch flags:

| App | app_id | Launch flag | PID |
|---|---|---|---|
| Chrome (main) | google-chrome | (no flags) | 295749 |
| Hermes PWA | chrome-ggodlfkjnmplcjoknpmbaadcecnfflfd-Default | `--app-id=ggod...` | 295114 |
| CDP Chrome | google-chrome | `--remote-debugging-port=9222` | 360601 |

To recover the exact launch command, read `/proc/PID/cmdline`:

```bash
tr '\0' ' ' < /proc/PID/cmdline
```

Store both the app_id and the launch command in the session save file so the restore script can reproduce the exact invocation.

**Critical pitfall**: The same PID can host multiple PWA windows with different `app_id` values (e.g. Hermes WebUI AND NotebookLM both in PID 295114). Both share the same `/proc/PID/cmdline`. Dedup must happen at the cmdline level — the second PWA window won't auto-recover unless Chrome's own session restore handles it.

### Python-based tree parsing (no jq)

On systems where `jq` is not installed, parse `swaymsg -t get_tree --raw` output with Python's stdlib. A complete re-runnable tree parser is in `scripts/sway-tree-parser.py` under this skill.

### Script location, fuzzel integration, and autostart

**Where to put session scripts** — user preference for `~/Scripts/`:

```
~/Scripts/
├── sway-session.py           # Combined save/restore/daemon
```

**Make scripts searchable in fuzzel** — add a `.desktop` file:

```ini
# ~/.local/share/applications/restore-sway-session.desktop
[Desktop Entry]
Name=恢复 Sway 会话
Exec=/home/dr/Scripts/sway-restore-session.sh
Type=Application
Terminal=false
```

fuzzel automatically indexes `~/.local/share/applications/` — `$mod+d` → type "恢复" to find it.

**Autostart with sway** — add to `~/.config/sway/config`:

```
exec ~/Scripts/sway-session.py
```

Use `exec` (fires once per sway start), not `exec_always` (fires on every config reload). Note: `swaymsg reload` does NOT re-run `exec` commands — only a full sway restart does.

**Keybinding shortcut** — bind a key for manual restore:

```
bindsym $mod+Shift+R exec ~/Scripts/sway-restore-session.sh
```

**swaybar limitation**: swaybar is a pure status display, NOT a clickable dock/panel. It cannot have clickable buttons to launch scripts. If you want clickable launchers, use waybar (supports clickable custom modules) or continue using fuzzel.

### sway-toolwait (startup ordering helper)

Install: `cargo install sway-toolwait` or check AUR if on Arch. Not packaged for Debian — build from source.

Usage in sway config:
```
exec sway-toolwait --workspace 1 foot
exec sway-toolwait --workspace 2 firefox
exec sway-toolwait --workspace 3 code
```

Each `sway-toolwait` waits for a new window to appear on the specified workspace before returning. This guarantees apps start in order even if some launch quickly and others are slow. Without it, concurrent `exec` calls on the same workspace may appear in unpredictable order.

## Idle Management & Power (swayidle)

swayidle is the **trigger** for auto screen lock, blanking, and sleep on
sway. It does NOT execute suspend/hibernate itself — that goes through
systemd-logind. Install: `sudo apt install -y swayidle swaylock`.

Full event reference, key parsing pitfalls, tiered config template, and
Linux-vs-Windows power-state mapping:
**`references/swayidle-power-management.md`**

### Critical pitfalls (read before writing your config)

1. **`parse_command` keeps only the first token.** Inline `sh -c "..."` and
   `swaylock -f -c 000000` get truncated to just `sh` / `swaylock` — arguments
   are silently dropped. **Wrap anything with arguments in a script.**

2. **Config is parsed line-by-line.** Bash-style `\` line continuation does
   NOT work. `timeout N cmd` and `resume cmd` must be on the same line.

3. **`wordexp` and `$XDG_RUNTIME_DIR`**: variable expansion can fail inside
   the truncated first token. Use absolute paths in helper scripts.

Verify with: `timeout 2 swayidle -C ~/.config/swayidle/config -d 2>&1 | grep Command`
— every event should show `Command: /full/path/to/script.sh`, never bare
`sh` or `swaylock`.

### Bridge pattern: swayidle ↔ other long-running tools

When another daemon (e.g. sway-session.py, media auto-pause) needs to know
"is the user idle?", use a **marker file in `$XDG_RUNTIME_DIR/`** as the
bridge — simpler than DBus/wayland IPC:

```sh
# swayidle triggers on idle/resume
timeout 60  ~/Scripts/sway-idle-on.sh  resume ~/Scripts/sway-idle-off.sh

# sway-idle-on.sh
: > "$XDG_RUNTIME_DIR/sway-user-idle"

# sway-idle-off.sh
rm -f "$XDG_RUNTIME_DIR/sway-user-idle"

# in any Python/other daemon: skip work if marker exists
import os
if os.path.exists(f"{os.environ['XDG_RUNTIME_DIR']}/sway-user-idle"):
    continue
```

`XDG_RUNTIME_DIR` is per-user, wiped on reboot — correct semantics for
"current session idle state", and survives one of the two processes crashing.

### Recommended tiered config

```ini
# ~/.config/swayidle/config
timeout 60  ~/Scripts/sway-idle-on.sh resume ~/Scripts/sway-idle-off.sh
timeout 300 ~/Scripts/sway-lock.sh
timeout 600 ~/Scripts/sway-screen-off.sh resume ~/Scripts/sway-screen-on.sh
timeout 1800 ~/Scripts/sway-suspend.sh
before-sleep ~/Scripts/sway-lock.sh
after-resume  ~/Scripts/sway-screen-on.sh
idlehint 300
```

Add `exec swayidle -w` to `~/.config/sway/config` (the `-w` blocks until
each command finishes — critical for `before-sleep` so swaylock is up
before the system actually sleeps).

### `dpms off` is NOT sleep

`output * dpms off` only turns off the panel signal — CPU keeps running,
Chrome keeps mining, downloads continue. To actually save power use
`systemctl suspend` (S3) or `systemctl hibernate` (S4). See
`man 5 logind.conf` for `HandleLidSwitch`, `IdleAction=`,
`IdleActionSec=`.

## Swaybar — Configuring the Status Bar

The default swaybar (`status_command while date +'%Y-%m-%d %X'; do sleep 1; done`) shows only date/time. Replace it with a custom script for CPU, memory, IP, etc.

### Custom status script

Write `~/.config/sway/status.sh`:

```bash
#!/bin/bash
# Shows date (24h, no tz), CPU load averages, memory usage
while true; do
    date=$(date '+%Y-%m-%d %H:%M')
    cpu=$(uptime | awk -F'load average:' '{print $2}' | cut -d, -f1 | xargs)
    mem=$(free -h | grep Mem | awk '{print $3 "/" $2}')
    echo "$date | CPU: $cpu | MEM: $mem"
    sleep 5
done
```

Override the default bar in `/etc/sway/config`:
```bash
sudo sed -i 's|status_command while date.*|status_command exec ~/.config/sway/status.sh|' /etc/sway/config
```

> Defining a separate `bar { }` block in `~/.config/sway/config` creates a **second** bar alongside the one from `/etc/sway/config`. Either override via `sed`, or comment out the `include /etc/sway/config` and define your own full bar block.

A ready-to-use copy lives at `templates/status.sh` under this skill.

What else you can show in status:

| Info | Command snippet |
|---|---|
| CPU load | `uptime \| awk -F'load average:' '{print $2}'` |
| Memory | `free -h \| grep Mem \| awk '{print $3"/"$2}'` |
| Tailscale IP | `ip addr show tailscale0 2>/dev/null \| grep inet \| awk '{print $2}'` |
| Volume | `wpctl get-volume @DEFAULT_AUDIO_SINK@ \| awk '{print $2*100}'` |
| Disk | `df -h / \| tail -1 \| awk '{print $4}'` |

**Limitation:** swaybar status text is display-only — no click events on individual items.

## Mouse Bindings for Titlebar

Bind mouse buttons to titlebar actions:

```
# Button2 = middle click, Button3 = right click
bindsym Button2 kill                    # titlebar only (default)
bindsym --whole-window Button2 kill     # titlebar + borders + content
```

- **Without `--whole-window`**: fires on **titlebar only** (correct for close-on-click).
- **With `--whole-window`**: fires anywhere on window — confusing when you just want titlebar.

Example — middle-click titlebar to close:
```bash
bindsym Button2 kill
```

Common bindings:
```bash
bindsym Button3 kill                    # right-click titlebar → close
bindsym Button2 floating toggle         # middle-click → toggle floating
```

## Pitfalls

- **JSON config syntax errors**: Manually editing `config-top` (or any JSON config) can introduce missing commas or trailing commas. Tools like `waybar-pwa-gen.py` that read → modify → write the JSON will crash with `json.decoder.JSONDecodeError`. Fix: `python3 -c "import json; json.load(open('/path/to/config.json'))"` to validate before restarting the tool.
- **Include order**: `include /etc/sway/config` must come **before** any use of `$mod`, `$term`, etc.
- **No `--overwrite`**: Sway doesn't have an `--overwrite` flag for `bindsym`. Use `unbindsym` first, then `bindsym`.
- **Duplicate binding warnings**: Use `--no-warn` flag only if you want to suppress the warning. Cleaner: `unbindsym` + `bindsym`.
- **Compositor can't start on SSH**: Sway needs a TTY (real display). Run from TTY, not SSH.
- **Session save file location**: MUST NOT use `/tmp` — it's wiped on reboot. Use `~/.config/sway/sway-session.json` or another persistent path.
- **`exec` vs `exec_always`**: `exec` runs only on fresh sway start. `swaymsg reload` does NOT re-run `exec`. `exec_always` runs on every config reload.
- **Chrome PWA dedup pitfall**: Same PID = same `/proc/PID/cmdline`, but the process can host multiple PWA windows with different `app_id` values. Dedup by cmdline means secondary PWAs won't auto-launch unless Chrome's session restore handles them.
- **Kanshi port names go stale**: Output names like `DP-2` vs `DP-3` can fluctuate across reboots, cable re-seats, or driver updates. If the monitor stops working suddenly, `swaymsg -t get_outputs` to check the current name, then update your kanshi config.
- **fcitx5**: After install, Pinyin may not be in the active input method list. Run `fcitx5-config-qt` and explicitly add it, or edit `~/.config/fcitx5/profile` directly (see above). If switching languages doesn't work, check that `fcitx5` is actually running via `ps aux | grep fcitx`.
- **fcitx5 hot-reload overwrites config edits**: If you edit `~/.config/fcitx5/profile` while fcitx5 is running and then hot-reload with `fcitx5 -rd`, fcitx5 writes its in-memory state back to disk — **overwriting** your edits. Always `pkill fcitx5` first, edit the file, then start fcitx5 fresh with `fcitx5 -d`.
- **`.bash_profile` / `.profile` are user-owned config files** — do NOT write to them automatically or append content without explicit user direction or opt-in. These files control login shell behavior and auto-start logic; modifications can break the user's workflow. If a config change requires environment.d/ or bash_profile (e.g. TTY-launched sway needing `WLR_DRM_NO_MODIFIERS`), suggest the edited lines and let the user decide where to place them.
- **TTY install pattern**: When in TTY (no GUI, sway not running), write complex install scripts to `~/t.sh` using `write_file` rather than running `curl | bash` or multi-line terminal commands. The user reviews the script, then runs `bash ~/t.sh`.
- **`--whole-window` on mouse bindings**: Using `--whole-window` makes a mouse binding fire on the entire window (titlebar + borders + content area), not just the titlebar. For "click titlebar to close", use plain `bindsym Button2 kill` without `--whole-window` — otherwise clicking anywhere on the window triggers the action, which is confusing.
