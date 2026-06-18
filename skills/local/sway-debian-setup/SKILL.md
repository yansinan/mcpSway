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


## Browsers under Wayland

Sway is a Wayland compositor. Browsers running under XWayland (the default for most) work but miss features like proper touchscreen support, smooth pinch-to-zoom, and correct screen sharing. Configure them to run natively on Wayland.

### Chromium / Google Chrome

```bash
sudo apt install -y chromium chromium-l10n
```

Chrome/Chromium detect Wayland automatically in recent versions, but to force native Wayland:

```bash
# Per-run
chromium --ozone-platform-hint=auto

# Permanent (system-wide) — Debian's standard hook
sudo tee /etc/chromium.d/wayland > /dev/null << 'EOF'
# Enable Wayland native support for Chromium under Sway
export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --ozone-platform-hint=auto"
EOF
```

`--ozone-platform-hint=auto` is preferred over the older `--ozone-platform=wayland` — it auto-detects Wayland vs X11, falling back gracefully when not on Wayland.

Once running natively, sway sees its `app_id` as `"chromium-browser"` — useful for `for_window` rules. PWAs spawned from Chromium use `"^chromium-"` prefix.

**Sway config pattern** (keyboard shortcut + no title bar):

```
# ── Chromium ──
bindsym $mod+Shift+w exec chromium
for_window [app_id="chromium-browser"] border pixel 1
for_window [app_id="^chromium"] border pixel 1    # covers PWAs too
```

Video Acceleration (VA-API):

Chromium ships its own ffmpeg codecs; the key optimization is hardware-accelerated decoding.

Install system video packages:

```bash
sudo apt install -y gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-vaapi vainfo
```

Enable in CHROMIUM_FLAGS (`/etc/chromium.d/wayland`):

```bash
export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --enable-features=VaapiVideoDecoder,VaapiVideoEncoder"
```

VA-API driver selection by GPU generation:

| GPU Generation | Driver Package | Verify With |
|---|---|---|---|
| Ivy Bridge (Gen7) / Bay Trail / older | `i965-va-driver` | `vainfo` → "Intel i965 driver for Intel(R) Ivybridge" |
| Broadwell (Gen8) / Skylake (Gen9) / Kaby Lake (Gen9.5) | `intel-media-va-driver` | `vainfo` → "Intel iHD driver" |
| Tiger Lake (Gen12) and newer | `intel-media-va-driver` | `vainfo` → "Intel iHD driver" |

Run `vainfo` (no display needed) to confirm hardware support:

```bash
vainfo 2>&1 | grep -E 'Driver version|VAProfile'
```

Supported profiles on Ivy Bridge HD 4000 (i965 driver): H.264 (BP/MP/HP/Stereo), MPEG2, VC1, JPEG — **no** HEVC/H.265, VP8, VP9 (software fallback).

Supported profiles on Kaby Lake UHD620 (iHD driver): adds VP8/VP9/HEVC hardware decode. **But Chromium 116+ can't use the i965 driver** — see the pitfall below.

**Quick VA-API compatibility check**: run `scripts/check-vaapi-compatibility.sh` (bundled with this skill) — detects whether VaapiVideoDecoder will work or cause black screen. Exits 0 (compatible) or 1 (incompatible, with suggested fix).

**Verification**: open `chrome://gpu` and check "Graphics Feature Status" → "Video Decode" should be "Hardware Accelerated", or look for command line flags at `chrome://version`.

**CRITICAL PITFALL — VaapiVideoDecoder + VP9 = YouTube black screen**

Enabling `VaapiVideoDecoder` on a GPU that doesn't support VP9 hardware decode (Ivy Bridge, or any pre-Broadwell GPUs) causes YouTube to black screen. The chain:

1. YouTube defaults to VP9 video stream (best quality/bandwidth trade-off)
2. Chromium sees `VaapiVideoDecoder` enabled → tries VA-API hardware decode for VP9
3. VA-API driver reports VP9 unsupported
4. Chromium 116+ **dropped i965 driver support entirely**. Even for H.264, Chromium now only tries the iHD driver (`intel-media-va-driver`), which only supports Broadwell (Gen8) and newer GPUs.
5. Result: **no VA-API backend at all** — iHD can't init (GPU too old), i965 is no longer supported by Chromium
6. Chromium's Wayland VA-API path **fails silently** instead of falling back to software decode
7. Result: black video, no playback

**Verification — confirm VaapiVideoDecoder is the cause:**

```bash
# 1. Check actual GPU (lspci, not memory)
lspci -nn | grep VGA
cat /proc/cpuinfo | grep "model name" | head -1

# 2. Check VA-API driver state
vainfo 2>&1 | grep -E 'Driver version|init failed|VAProfile'

# 3. Check which driver Chromium is actually using
# iHD init failed + i965 works → Chromium 116+ can't use i965 → VA-API broken
# iHD init OK → VA-API should work

# 4. Launch Chromium WITHOUT VaapiVideoDecoder to isolate test
chromium --disable-accelerated-video-decode
# → If videos play, VaapiVideoDecoder is the root cause
```

**Root cause at a glance** — two independent failures that compound:

| Factor | Why it fails |
|--------|-------------|
| Chromium 116+ drops i965 entirely | Chromium now exclusively uses the iHD driver (intel-media-va-driver). iHD only supports Broadwell (Gen8) and newer. On Ivy Bridge (Gen7) or older GPUs, iHD can't init → **no VA-API backend at all**, not even for H.264. |
| VaapiVideoDecoder enabled | Chromium attempts VA-API video decode → fails (no backend) → instead of software fallback, the video pipeline blackscreens. |
| YouTube uses VP9 | Even if the i965 driver were available, HD 4000 can't VP9-hardware-decode. But the real blocker is the first factor — even H.264 VA-API is gone. |

**The CDP browser paradox**: The Hermes CDP browser (launched with `--ozone-platform=wayland` from a non-sway session) may play YouTube fine even though the user's `$mod+Shift+W` browser doesn't. This is because the CDP browser **didn't get `VaapiVideoDecoder`** from `/etc/chromium.d/wayland` (launched via a different shell context), while the user's browser did. Always check `chrome://version` → command line to confirm which flags are actually active.

**Fix options (choose one):**

A. **h264ify extension** — forces YouTube to stream H.264 instead of VP9. Install via `--load-extension`:
   ```bash
   # Download from GitHub
   cd /tmp && curl -sLO "https://github.com/erkserkserks/h264ify/archive/refs/heads/master.zip"
   python3 -c "import zipfile; zipfile.ZipFile('/tmp/master.zip').extractall('/tmp/h264ify_src')"
   mkdir -p ~/.hermes/extensions/
   cp -r /tmp/h264ify_src/h264ify-master ~/.hermes/extensions/h264ify

   # IMPORTANT: patch the service worker for --load-extension compatibility
   # Extensions loaded via --load-extension don't reliably fire onInstalled.
   # Add an onStartup listener:
   ```

   The service worker fix (`src/service_worker.js`):
   ```javascript
   async function registerScripts() { /* ... existing code ... */ }
   chrome.runtime.onInstalled.addListener(registerScripts);
   chrome.runtime.onStartup.addListener(registerScripts);  // ← ADD THIS
   ```

   Then update the sway binding:
   ```
   bindsym $mod+Shift+w exec chromium --load-extension=/home/dr/.hermes/extensions/h264ify
   ```

   **Must fully kill Chromium** before testing — background processes survive window close:
   ```bash
   pkill -9 chromium
   # Then relaunch
   ```

   Verify in `chrome://extensions` → h264ify should be listed.

   *Note*: Even with h264ify, if VaapiVideoDecode is busted for ALL codecs (i965 dropped, iHD won't init), H.264 will fallback to software decode anyway. The CPU handles 1080p soft decode fine.

   **Service worker pitfall for `--load-extension`**: h264ify uses `chrome.runtime.onInstalled` to register its content script (inject.js) via `chrome.scripting.registerContentScripts`. When loaded via `--load-extension`, `onInstalled` may not fire reliably. The naive fix — adding `chrome.runtime.onStartup.addListener(registerScripts)` — **crashes the extension** because `onStartup` requires the `"background"` permission in the manifest, which h264ify doesn't declare. If the extension becomes "不可用" (grayed out) after clicking Refresh on chrome://extensions, this is why. Fix: remove the `onStartup` line, remove and re-add the extension.

B. **Disable accelerated video decode entirely** (simplest, always works):
   ```bash
   # Add to /etc/chromium.d/wayland:
   export CHROMIUM_FLAGS="$CHROMIUM_FLAGS --disable-accelerated-video-decode"
   ```

   After disabling, clean up unused VA-API packages:
   ```bash
   sudo apt remove -y i965-va-driver intel-media-va-driver gstreamer1.0-vaapi
   ```
   These packages exist only for GPU hardware decode. With `--disable-accelerated-video-decode`, they're dead weight.

C. **Remove VaapiVideoDecoder from flags** (same effect as B — video plays via software)

D. **Install Google Chrome** (not Chromium) — Chrome's VA-API integration handles unsupported codecs properly with graceful fallback. Also bundles Widevine DRM out of the box.

**Troubleshooting: "video plays in CDP browser but not in my sway Chromium"**

This is the key diagnostic pattern:

```bash
# 1. Compare launch flags — look for VaapiVideoDecoder
# CDP browser (usually works):
chromium ... --ozone-platform=wayland    # NO VaapiVideoDecoder flag
# User's sway browser (black screen):
chromium                                 # Gets VaapiVideoDecoder from /etc/chromium.d/wayland

# 2. Check video state in CDP browser (to confirm codec):
browser_console(expression='document.querySelector("video").paused')
# If paused=true, click play button

# 3. Root cause test — launch sway Chromium without VaapiVideoDecoder:
chromium --disable-accelerated-video-decode
# If videos now play, VaapiVideoDecoder is the culprit
```

**Diagnostic minimum**: always check two things:
- `chrome://version` → command line flags (is `VaapiVideoDecoder` there?)
- GPU generation via `vainfo` → does it support VP9 hardware decode?

### CDP Remote Debugging Mode

When Hermes Agent uses the browser toolset (navigate/click/snapshot), it connects to a CDP endpoint at `browser.cdp_url`. For local usage on Sway:

1. Create a dedicated profile at `~/.hermes/cdp-chrome/` — separate from your daily browser, avoids session conflicts.
2. Set a custom new-tab background color (e.g. `#1a73e8`) for visual distinction.
3. Launch from the Hermes session with explicit Wayland env vars (non-GUI session won't inherit them):
   ```bash
   XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-1 \
   XDG_SESSION_TYPE=wayland chromium \
     --remote-debugging-port=9222 \
     --user-data-dir=~/.hermes/cdp-chrome \
     --no-first-run --no-default-browser-check --ozone-platform=wayland
   ```
4. Update `browser.cdp_url` via `hermes config set`.
5. Clean up port 9222 conflicts (SSH tunnels to remote hosts, old headless Playwright instances) before launching.

See [cdp-browser-config.md](references/cdp-browser-config.md) for the full workflow, including troubleshooting SSH tunnel conflicts and YouTube playback verification.

### Firefox / Firefox ESR

```bash
sudo apt install -y firefox-esr firefox-esr-l10n-zh-cn
```

Firefox needs an environment variable to enable native Wayland:

```bash
# In sway config:
exec_always systemctl --user import-environment MOZ_ENABLE_WAYLAND=1

# Or in shell profile:
export MOZ_ENABLE_WAYLAND=1
```

**Note**: Firefox defaults to XWayland even on Wayland sessions unless `MOZ_ENABLE_WAYLAND=1` is set. Without it, sway sees `app_id="firefox"` under XWayland with `class~="[Ff]irefox"`; with Wayland enabled, `app_id="firefox"` (native, different window properties).

**Verification**: `about:support` → "Window Protocol" should say "wayland" (not "xwayland").

### Matching browser windows in sway

```bash
# Chromium native Wayland
for_window [app_id="chromium-browser"] border pixel 1
for_window [app_id="^chromium-"] border pixel 1   # PWAs spawned from Chromium

# Firefox native Wayland
for_window [app_id="firefox" title="^Picture-in-Picture"] floating enable

# Generic fallback (XWayland)
for_window [class~="(?i)(firefox|chromium-browser|google-chrome)"] border pixel 1
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


## TTY & DRM management

### Switching between TTYs from SSH

You can control which TTY a program runs on remotely via `openvt` and `chvt`:

```bash
# Start a program on TTY2 (skip getty conflict)
sudo openvt -c 2 -f -- <command>

# Switch active VT to TTY2 (needs physical display)
chvt 2
```

### DRM exclusivity — one compositor at a time

Programs that use DRM/KMS directly (sway, bcon, Weston, KDE's KWin) **cannot run simultaneously**. They each need exclusive access to the display hardware.

```bash
# bcon — a GPU-accelerated terminal that runs directly on the TTY,
# not inside a Wayland window. It takes over DRM just like sway.
# Running bcon while sway is active → "Failed to create backend"
```

**Correct workflow** to switch between them:
1. Exit sway (`$mod+Shift+e`)
2. Switch to another TTY (`Ctrl+Alt+F2`)
3. Run `bcon` there
4. Switch back to TTY1 (`Ctrl+Alt+F1`) to restart sway


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


## Network Management

Debian 13 ships with `wpa_supplicant` + `dhcpcd` by default (no GUI). For a sway desktop, install **NetworkManager** which provides CLI, TUI, and GUI management.

### Installation

```bash
sudo apt install -y network-manager network-manager-gnome
```

This provides `nmcli` (CLI), `nmtui` (TUI/foot), `nm-applet` (tray), and `nm-connection-editor` (GUI).

### Migration from wpa_supplicant + dhcpcd

After installing NM, Wi-Fi may show as `未托管` (unmanaged) because the standalone wpa_supplicant process still controls the interface. Fix:

```bash
sudo killall wpa_supplicant
sudo systemctl restart NetworkManager
```

NM starts its own wpa_supplicant D-Bus instance internally. Scan and connect:

```bash
nmcli device wifi list
nmcli device wifi connect "SSID" password "password"
```

### Sway Config

```conf
exec_always bash -c 'pkill -x nm-applet 2>/dev/null; sleep 0.3; exec nm-applet'
bindsym $mod+n exec nm-connection-editor
bindsym $mod+Shift+n exec foot nmtui
```

### Pitfalls

- **wpa_supplicant conflict** — if Wi-Fi shows as `未托管`, kill standalone wpa_supplicant and restart NM.
- **No tray on swaybar** — nm-applet needs waybar tray to show icon; runs silently otherwise.


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


## Input Device Configuration

Sway groups input devices by three `type:` classifiers — no need to know specific device names. All three should be configured for a laptop/tablet setup.

### Touchpad (touchpad)

```conf
input type:touchpad {
    tap enabled               # 轻触=点击
    natural_scroll enabled    # 双指滚动方向=内容方向
    click_method button_areas # 触控板左下=右键，下中=中键
    middle_emulation enabled  # 三指同时点击=中键
    dwt enabled               # 打字时禁用触摸板
    scroll_factor 0.5         # 滚动速度减半（高分辨屏适配）
}
```

| Setting | Values | Purpose |
|---------|--------|---------|
| `tap` | `enabled`/`disabled` | 单指轻触模拟左键点击 |
| `natural_scroll` | `enabled`/`disabled` | 双指上滑=内容上滚（触控板默认） |
| `click_method` | `button_areas`/`clickfinger`/`none` | 区域分左右键 / 多指分左右键 |
| `middle_emulation` | `enabled`/`disabled` | 三指同时点击 = 中键粘贴 |
| `dwt` (disable-while-typing) | `enabled`/`disabled` | 敲键盘时暂停触摸板，防误触 |
| `scroll_factor` | float (0.1–10) | 滚动距离乘数，高分屏调低 |

### Touchscreen (touch)

```conf
input type:touch {
    tap enabled               # 触摸屏点击即触发
    natural_scroll enabled
    scroll_factor 0.5
}
```

### Pointer/Mouse (pointer)

```conf
input type:pointer {
    natural_scroll disabled   # 传统滚轮方向（上滚=页面上移）
    accel_profile adaptive    # 自适应加速度：慢移精细，快移快速
    pointer_accel 0.0         # 加速度基数
}
```

| Setting | Values | Purpose |
|---------|--------|---------|
| `natural_scroll` | `enabled`/`disabled` | true mouse users want this OFF |
| `accel_profile` | `adaptive`/`flat`/`none` | adaptive = 速度越快指针移动越大 |
| `pointer_accel` | float (-1 to 1) | 基础加速量 |

### Device-specific (when `type:` isn't enough)

```bash
swaymsg -t get_inputs     # → find "identifier" field
```

```conf
input "2:14:SynPS/2_Synaptics_TouchPad" {
    tap enabled
}
```

Prefer `type:` for portability; use identifier only when you need per-device differentiation.

### Pitfalls

- **`type:pointer` catches ALL pointing devices** — touchpad, TrackPoint, and external mice. Apply touchpad-specific settings AFTER pointer block so later blocks override.
- **`scroll_factor < 1`** = slower scrolling (good for high-DPI touchpads). **`> 1`** = faster (trackball without scroll ring).
- **`click_method button_areas` on small touchpads** may leave no area for middle click. Switch to `clickfinger` (2 fingers=right, 3=middle) instead.
- **No xinput/synclient** on Wayland — all input config goes through sway.
- **`type:` rules auto-match hotplugged devices** — no restart needed when plugging a mouse.


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


### Custom status script template

Use the template at `templates/status-bar.sh` — copy to `~/.config/sway/status.sh`, `chmod +x`, then reference from bar config. The template is shellcheck-clean and uses proper i3bar JSON protocol.

### i3bar protocol — why `{"version":1}` is required

swaybar distinguishes JSON from plain text by checking the **first byte** of the status_command output:
- Starts with `{` → i3bar protocol (JSON blocks), enables per-block colors
- Starts with anything else → plain text (raw string displayed literally)

This means `[{"full_text":"..."}]` **without the header is displayed as raw JSON text**, not parsed. Correct output format:

```
{"version:1}         # ← required first line
[                    # ← outer array (never closes in infinite mode)
[{"full_text":"..."}]  # first data line
,[{"full_text":"..."}] # subsequent lines with leading comma
```

### Multiple bars (default + user)

Including `/etc/sway/config` pulls in the **default bar** block (which shows date/time). Adding a second `bar {}` in the user config creates a **second bar** — both visible at the same position, overlapping. Fix: hide the default bar after include, and use an absolute path in `status_command`:

```conf
include /etc/sway/config

exec_always swaymsg bar bar-0 mode invisible

bar {
    id bar-1
    status_command /home/dr/.config/sway/status.sh
    position top
    colors {
        statusline #ffffff
        background #2e2e2e
        inactive_workspace #32323200 #32323200 #5c5c5c
    }
}
```

Key details:
- Use absolute path in `status_command` — `~` expansion isn't reliable
- `exec_always swaymsg bar bar-0 mode invisible` — hides the inherited default bar
- List bar IDs with `swaymsg -t get_bar_config` to find the right ID to hide

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


### Where bindings fire (area flags)

Mouse binds can be scoped to a region of the window. **By default (no flag), the binding only activates when the pointer is over the title bar.**

| Flag | Area | Use case |
|---|---|---|
| *(none)* | Title bar only | Middle-click to close, title bar actions |
| `--whole-window` | Border + title bar + content | Actions that work anywhere on a window |
| `--border` | Window border only | Border-specific actions |
| `--exclude-titlebar` | Border + content, but NOT title bar | Window content actions without catching title bar |

**There is no `--titlebar` flag.** To target the title bar explicitly, omit area flags (the default scope is titlebar-only).



## Swaynag Error Debugging

When sway displays a popup bar saying *"There are errors in your config file"* (spawned via `swaynag --type error --message ...`), use **binary search** to isolate the problematic lines:

1. **Kill stale swaynag** — it may persist across failed reloads:
   ```bash
   pkill swaynag
   ```

2. **Start with a minimal config** — just the include line:
   ```bash
   cat > ~/.config/sway/config << 'EOF'
   include /etc/sway/config
   EOF
   ```
   Reload: `swaymsg reload`. If no swaynag appears, the error is in your custom lines.

3. **Binary search** — comment out half the custom lines, reload, check swaynag:
   ```bash
   sed -i 'N,Ms/^/#/' ~/.config/sway/config   # comment lines N-M
   swaymsg reload
   pgrep swaynag    # if found → error is in a different half
   ```
   Restore from backup (`cp ~/.config/sway/config.bak ~/.config/sway/config`), then narrow the range by halving.

4. **Restore cleanly between iterations** — multiple sed operations on the same file leave it in a corrupted state. Always restore from a clean backup:
   ```bash
   cp ~/.config/sway/config.bak ~/.config/sway/config
   ```
   Then apply ONE sed change at a time.

### Common config errors (not syntax, but runtime)

| Symptom | Root cause | Fix |
|---|---|---|
| swaynag on reload: "errors in your config" | Duplicate keybinding (`bindsym` same key twice) | Add `unbindsym <key>` before the replacement `bindsym` |
| swaynag on reload: "errors in your config" | Config section with color vars assigned but unused (e.g. `MCOL=$CLR_WARN` but printf uses `$CLR_DEF`) | Consume the color variable in printf or remove it |
| swaynag on reload: "errors in your config" | A `for_window` pattern that never matches (e.g. wrong operator) | Change `app_id="^X"` → `app_id~="^X"` (see for_window criteria) |

### for_window criteria: `=` vs `~=`

Sway's `for_window` (and other criteria-based commands) uses two matching operators:

| Operator | Semantics | Example |
|---|---|---|
| `=` | **Exact string match** — the value must match the property exactly | `[app_id="chromium-browser"]` only matches app_id literally equal to `chromium-browser` |
| `~=` | **Regex match** — the value is an ERE (extended regex) pattern | `[app_id~="^chromium"]` matches any app_id starting with `chromium` (covers PWAs: `chromium-browser`, `chromium-PWA-calculator`, etc.) |

**Never** use regex syntax (`^`, `$`, `(?i)`) with `=` — it treats them as literal characters. A pattern like `app_id="^chromium"` looks for a window with app_id literally equal to ``^chromium`` (six chars), which no real app will ever have.


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
- **`exec_always` accumulates long-lived processes on reload**: Unlike `exec` (runs once per sway login), `exec_always` re-runs every `swaymsg reload`. For daemons like uxplay, nm-applet, blueman-applet, this spawns a new instance without killing the old one. Only the first binds the port/socket; the rest sit idle consuming ~100 MB RSS each.

  **Two solutions**:
  1. `exec` (no restart on reload) — safe, no zombies.
  2. `exec_always bash -c 'pkill -x <name> 2>/dev/null; sleep 0.5; exec <name> <args>'` — kills before starting.
- **Monitor "detected but no signal"**: Usually a cable/adapter hardware issue, not a config problem.
- **Compositor can't start on SSH**: Sway needs a TTY (real display). Run from TTY, not SSH.
- **killall kanshi fails silently**: Requires `psmisc` (provides `killall`). If not installed, `killall` errors silently.
