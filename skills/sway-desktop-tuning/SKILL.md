---
name: sway-desktop-tuning
source:
  - https://raw.githubusercontent.com/swaywm/sway/master/sway/sway.5.scd
  - https://wiki.archlinux.org/title/Sway
  - https://wiki.archlinux.org/title/PipeWire
description: "Configure a working sway (Wayland compositor) desktop for automated behavior — swayidle event handling, session save/restore daemons, idle detection, per-monitor DPMS control, inter-process patterns between long-running daemons and event triggers."
tags: [sway, wayland, waybar, swayidle, s0ix, pipewire, tuning]
---

## Sway Desktop Tuning

Patterns for turning a working sway install into a self-managing workstation. The focus is on the runtime configuration patterns that aren't obvious from man pages and that bite everyone the first time.

## Critical: for_window criteria regex syntax (sway vs i3 gotcha)

This is the #1 pitfall for anyone reading online sway examples or migrating from i3.

**sway syntax**: `[app_id="^chrome-"]` — use `=` and the value IS the regex for attributes that support PCRE2. Source: sway.5.scd CRITERIA section.

**i3 syntax**: `[class~"^Chromium"]` — use `~` tilde operator to indicate a regex.

The two are INCOMPATIBLE. Online examples and old forum posts frequently show the i3 `~` syntax, which sway's config parser rejects with `"需要 Token 'app_id' 有值"` or similar parse errors.

**Attributes that accept regex in sway**: `app_id`, `class`, `con_mark`, `instance`, `shell`, `title`, `window_role`, `workspace`, `sandbox_engine`, `sandbox_app_id`, `sandbox_instance_id`. All use plain `=` — the string value is treated as a PCRE2 regular expression.

### Common pattern: match all Chrome PWA windows

Chrome PWA windows have `app_id` values like `chrome-<24char-hash>-Default`. To match all of them:
```
for_window [app_id="^chrome-"] border pixel 1
```

Note: each PWA has a unique hash, so exact-match rules like `[app_id="google-chrome"]` won't catch PWAs. The regex `^chrome-` is the right approach.

### Finding app_id / class values

```
swaymsg -t get_tree | python3 -c "
import json,sys
def walk(n):
    if n.get('app_id'): print(f'app_id={n[\"app_id\"]}  name={n.get(\"name\",\"\")}')
    wp = n.get('window_properties') or {}
    if wp.get('class'): print(f'class={wp[\"class\"]}  title={wp.get(\"title\",\"\")}')
    for c in n.get('nodes',[]) + n.get('floating_nodes',[]): walk(c)
walk(json.load(sys.stdin))
"
```

### Pitfall: stale SWAYSOCK

sway creates a new socket file on each restart. `$SWAYSOCK` may point to a stale socket from a previous session. When the above commands fail with "Unable to connect to ... sock", find the live socket:
```
ls -la /run/user/$UID/sway-ipc.*.sock
export SWAYSOCK=$(ls /run/user/$UID/sway-ipc.*.sock | tail -1)
```

### for_window only applies to NEW windows

`for_window` rules fire only when a window is created/mapped. Already-open windows keep their current border mode. After adding a rule, close and reopen the app (or use `swaymsg '[criteria] border pixel 1'` on existing windows).

### Official reference

The authoritative source is the sway man page source at:
https://raw.githubusercontent.com/swaywm/sway/master/sway/sway.5.scd

Search for the `# CRITERIA` section (around line 977). Read it with:
```
curl -sL https://raw.githubusercontent.com/swaywm/sway/master/sway/sway.5.scd | sed -n '/^# CRITERIA/,/^# /p'
```

Do NOT rely on third-party forum posts or blog articles for sway syntax — they carry stale i3 conventions.

## Triggers


## Triggers

- Writing or debugging `~/.config/swayidle/config`
- Building a session save/restore daemon
- Detecting "user is at keyboard" without polling
- Per-output DPMS control (e.g. one screen off, one on)
- Bridging a long-running daemon with swayidle / udev / dbus events
- Diagnosing or configuring PipeWire audio (no sound, wrong output device, volume issues)
- Setting up AirPlay mirroring (UxPlay) on sway

## CRITICAL: swayidle config gotchas (read this first)

Two non-obvious quirks bite everyone the first time. Both live in `parse_command` and `load_config` in swayidle's main.c.

### Gotcha 1: `parse_command` takes ONLY the first token

```c
// from swayidle main.c, ~line 670
static char *parse_command(int argc, char **argv) {
    if (argc < 1) { ... }
    swayidle_log(LOG_DEBUG, "Command: %s", argv[0]);
    return strdup(argv[0]);
}
```

Swayidle then runs the result as `sh -c <param>`. So if your config has:

```
timeout 60 sh -c "touch $XDG_RUNTIME_DIR/marker"
```

wordexp tokenizes into `timeout`, `60`, `sh`, `-c`, `touch /run/user/1000/marker` — but `parse_command` only stores `sh`. The actual execution becomes `sh -c "sh"` (an interactive subshell that hangs).

**Workaround**: Every event command must be a single-token path to a script file. Put all logic inside the script.

```
timeout 60 ~/Scripts/your-action.sh
```

### Gotcha 2: config is line-by-line, NO multi-line continuation

The shell-style `\` continuation that works on the command line does NOT work in config files. Each line is parsed independently with wordexp. A line starting with `resume` (even indented) is "Unsupported command 'resume'".

**Workaround**: Put `timeout` and its `resume` on the SAME line:

```
timeout 60 ~/Scripts/off.sh resume ~/Scripts/on.sh
```

### Verifying a config (without entering the idle loop)

```bash
timeout 2 swayidle -C ~/.config/swayidle/config -d 2>&1 | grep -E "Command|Loaded|error|Unsupported" -i
```

You should see one `Command: <full-script-path>` per event and a `Loaded config at ...` line. If you see "Too few parameters" or "Unsupported command 'X'", you hit Gotcha 1 or 2.

The `scripts/verify-swayidle-config.sh` support file wraps this with pass/fail reporting.

## Monitor identification: never use DP-N

DP connector names (`DP-1`, `DP-2`, ...) change on every boot when using USB-C docks. Always use the make/model/serial triple in BOTH the sway config and swaymsg calls:

```
output "Philips Consumer Electronics Company PHL BDM4350 0x000032DB" mode 3840x2160@60Hz ...
```

```bash
swaymsg 'output "Philips Consumer Electronics Company PHL BDM4350 0x000032DB" dpms off'
```

To get the exact triple for your monitors:

```bash
swaymsg -t get_outputs | jq '.[] | select(.type=="output") | {name, make, model, serial}'
```

The `name` field will be `DP-5` (or whatever number was assigned this boot — useless long-term). The `make + model + serial` triple is stable.

## Inter-process pattern: marker file in XDG_RUNTIME_DIR

For a long-running daemon that needs to react to swayidle events, the simplest IPC is a marker file in `$XDG_RUNTIME_DIR`:

- swayidle timeout event → create file (`touch $XDG_RUNTIME_DIR/sway-user-idle`)
- swayidle resume event  → remove file (`rm -f ...`)
- Daemon tick            → check `Path(marker).exists()`

This beats the alternatives for typical cases:
- Unix socket: overkill for a single boolean signal
- dbus: requires a service file, dbus-send invocation, and name registration
- Polling sway IPC: sway doesn't expose "is user idle" — that's a wayland-protocol concept (`ext-idle-notify-v1`), only swayidle itself sees it

The marker file vanishes on reboot, which is correct — the next boot's daemon starts fresh and user is presumed active.

## Session save/restore: avoid /tmp

Save session JSON to `~/.config/sway/sway-session.json` (persistent, alongside config). `/tmp` is wiped on reboot — losing your workspace layout because you didn't unmount cleanly is exactly the case when you most want to recover it.

Recommended cadence: 5 minutes. Long enough to not be noisy, short enough that a crash loses < 5 min of layout state.

## User preference: unified entry point

This user strongly prefers consolidating scattered helper scripts into ONE script that accepts subcommands. Example shape for a unified sway-session script:

```
sway-session                # default: restore session + start daemon
sway-session --save         # manual save
sway-session --restore      # manual restore
sway-session --daemon       # just daemon (no restore)
sway-session --mark-idle    # swayidle 60s timeout → create idle marker
sway-session --mark-active  # swayidle 60s resume → delete marker
sway-session --screen-off   # swayidle 3600s timeout → dpms off external
sway-session --screen-on    # swayidle 3600s resume → dpms on external
```

Why this user prefers it:
- One file to audit (vs grepping across N scripts)
- One shebang, one place to add a new subcommand
- One place to find a bug
- subcommand dispatch is ~15 lines of code

Tradeoff: the file gets long (~300 lines). Keep sections clearly demarcated with header comments. A symlink to a `.py` is fine (`sway-session → sway-session.py`) — swayidle configs can use the unsuffixed name.

When adding NEW scripts to this user's system, default to extending an existing unified script over creating a new file. Only create a new script if the new function is genuinely orthogonal.

## Resume auto-wake: pair your timeouts

If a timeout turns something off (screen, lock, suspend), pair it with a `resume` action to turn it back on. Otherwise users have to manually recover when they return.

```
timeout 3600 off.sh resume on.sh
```

This is the default and expected behavior. Only skip the `resume` if you genuinely want the off state to persist past user activity (rare — and if you do, confirm with the user, because the alternative "screen stays black forever after 60 min" is a common footgun).

## Finding the sway IPC socket

sway creates its socket at `/run/user/$UID/sway-ipc.$UID.$PID.sock`. The PID changes on every sway restart, so scripts that call `swaymsg` need to find the right socket dynamically:

```python
import glob
socks = sorted(glob.glob("/run/user/*/sway-ipc.*.sock"))
if socks:
    os.environ["SWAYSOCK"] = socks[-1]
```

`swaymsg` itself, when `$SWAYSOCK` is unset, picks the most recently modified socket — but this can race during a sway restart. Setting `SWAYSOCK` explicitly via glob is more reliable.

## Force-firing swayidle from the command line

`pkill -USR1 swayidle` triggers SIGUSR1, which swayidle's `handle_signal` maps to "enter idle state immediately" (the timeout events fire without waiting). Useful for testing your config without sitting idle for the real threshold.

`pkill -TERM swayidle` triggers SIGTERM/SIGINT, which runs all pending resume commands before exiting. Useful for testing your resume events.

## Modern Standby (S0ix) power management

Most laptops made since 2018 (Intel Kaby Lake-R / 8th gen onward, AMD Renoir+) ship with **Modern Standby (S0ix)** instead of traditional S3 deep sleep. This changes what swayidle can and cannot do, and what "sleep" actually means. See `references/modern-standby-s0ix.md` for the full S3/S4/hybrid-s2idle comparison, the SSH-over-s2idle reality, and the WOL limitations.

**Quick detection — is this machine S0ix-only or S3-capable?**

```bash
cat /sys/power/mem_sleep
# Output: [s2idle]              → S0ix only (Modern Standby device)
# Output: [s2idle] deep        → both modes available
# Output: s2idle [deep]        → currently using deep, s2idle also available
# (no s2idle, only [deep])     → legacy S3 device, no Modern Standby
```

If only `s2idle` is listed, `systemctl suspend` on that machine walks the s2idle path, NOT a deep S3. Confirm with:

```bash
echo deep | sudo tee /sys/power/mem_sleep
# "Invalid argument" → kernel does not support S3 deep → confirmed s2idle-only
```

**Mapping the user's mental model to reality:**

- "I closed the lid and the laptop is in sleep" → on S0ix, that is s2idle, NOT S3. RAM is technically still "alive" (CPU is in deep C-state, OS framework partially suspended), but the wake latency is sub-second and the power draw is 0.5-2W. Power consumption is higher than S3, but the user experience is closer to Windows Modern Standby than to a 1-3s S3 wake.
- "systemctl hibernate will work because I have swap" → only if `swap ≥ RAM`. Default `image_size` is 2/5 of RAM, but actual modified-pages can exceed that. Test with `sudo rtcwake -m disk -s 10` before trusting it for real. On a 15 GiB RAM machine, 12 GiB swap is borderline.
- "I can SSH into the sleeping laptop" → NO, not while it's in s2idle. The network card is runtime-suspended; the OS isn't processing packets. After physical wake (lid, power button, USB), you have a 5-30s re-association chain (Wi-Fi resume → DHCP/Tailscale re-handshake → sshd reachable). Wireless WoL is essentially nonexistent; wired WoL on a S0ix-only machine rarely works because the ACPI wakeup table typically lists LAN devices under S4, which the kernel can't bridge to s2idle.

**logind power button mapping:**

```bash
sudo sed -i 's/^#HandlePowerKey=poweroff$/HandlePowerKey=suspend/' /etc/systemd/logind.conf
# then either: reboot (no session disruption)
# or:          sudo systemctl restart systemd-logind  (will end your sway session)
```

`HandlePowerKey=suspend` walks `mem_sleep` (s2idle on a Modern Standby device). `HandleLidSwitch=suspend` is the default on Debian and already works. Long-press is `HandlePowerKeyLongPress=` (defaults to `poweroff` — leave it there so holding the button still force-powers-off, overriding an accidental short press).

**Wire swayidle into hibernate via the same `~/Scripts/sway-session` entry point:**

```bash
# 1. Add a script-only subcommand to your unified entry point:
sway-session --hibernate   # systemctl hibernate, requires swap ≥ RAM

# 2. Add a swayidle timeout:
#    timeout 7200 ~/Scripts/sway-session --hibernate
# (NOT paired with resume — hibernate writes to swap, machine is off, no resume event fires)
```

The reason `sway-session --hibernate` is a separate subcommand rather than inline: `systemctl hibernate` takes no arguments, so this one could in theory be inline — but keeping it as a subcommand preserves the "everything goes through one entry point" rule and gives you a place to add pre-hibernate work (saving sway session, sync'ing btrfs, etc.) without touching swayidle config.

## Verification recipes

```bash
# 1. Config syntax check (exits after 2s, no idle actually fires)
timeout 2 swayidle -C ~/.config/swayidle/config -d 2>&1

# 2. List current outputs and their dpms state
swaymsg -t get_outputs | jq '.[] | select(.type=="output") | {name, make, model, dpms}'

# 3. Manually trigger a save or restore
~/Scripts/sway-session --save
~/Scripts/sway-session --restore

# 4. Force swayidle into idle now (runs all timeout commands)
pkill -USR1 swayidle

# 5. Live s2idle/SSH/CPU/NIC monitor (run for 2-5 min before claiming "s2idle blocks SSH")
bash ~/.hermes/skills/devops/sway-desktop-tuning/scripts/s2idle-monitor.sh 300
# or once installed in the user's scripts dir:
~/Scripts/s2idle-monitor.sh 300
# Then trigger SSH from another machine, look for the "*** 新 SSH 连接到达! ***"
# marker in the log, and check what cpu0 frequency was at that moment.

# 6. Force a 5-second s2idle + auto-wake to verify the path works on this hardware
sudo rtcwake -m mem -s 5
# Screen goes black, wakes 5 s later. journalctl -k shows PM: suspend entry/exit.

# 7. Confirm a successful s2idle actually happened
cat /sys/power/suspend_stats/success
# 0 = never suspended, just CPU-idle. 1+ = walked the suspend path.
```

## Audio management on sway (PipeWire + WirePlumber)

sway doesn't ship its own audio stack — the standard choice on Debian 13 is **PipeWire + WirePlumber** (both enabled by default on modern Debian). WirePlumber is the session manager that auto-discovers ALSA devices and creates PipeWire nodes.

### Checking audio state

```bash
# Quick overview (sinks, sources, volumes, default)
wpctl status

# Detailed node dump
pw-dump | python3 -c '
import json,sys
for obj in json.load(sys.stdin):
    if obj["type"] != "PipeWire:Interface:Node": continue
    p = obj["info"]["props"]
    if "node.name" not in p: continue
    print(f'{p.get(\"node.name\",\"\"):60s}  {p.get(\"node.description\",\"\")}')'

# Current link graph (who's connected to what)
pw-link -o
pw-link -i
```

### Adjusting volume and default sink (WirePlumber)

WirePlumber saves volume/mute/default-sink state on exit and restores it automatically. Use `wpctl` — it persists across reboots:

```bash
# List sinks with IDs
wpctl status
# Output: Audio → Sinks → ID.name [vol: 0.85]

# Set volume (0.0-1.0)
wpctl set-volume <ID> 0.75

# Toggle mute
wpctl set-mute <ID> toggle

# Set default sink (for new audio streams)
wpctl set-default <ID>
```

Pitfall: the default PipeWire volume in `wpctl` is **1.0 = 100%**. The old PulseAudio 153% trick doesn't apply here. 0.40 is genuinely quiet. If the user complains of no sound, check `wpctl get-volume` on each sink — ALSA hardware muting (`amixer`) is a separate layer and rarely the culprit on modern PipeWire.

### ALSA hardware level (when PipeWire says it's fine but there's still no sound)

```bash
# List all ALSA cards
aplay -l

# Check per-card mixer controls
amixer -c <card>
```

Common issues:
- **HDMI/DP audio muted**: `IEC958` controls on the Intel HDA card (`card 0`) are `[off]` by default on some chipsets. Enable with `amixer -c 0 sset "IEC958",0 on`. The indexed comma form (IEC958,0 / IEC958,1 / IEC958,2) controls individual HDMI/DP outputs. After unmuting, restart the audio stream (not the whole pipewire daemon).
- **Headphone/speaker switch**: `Auto-Mute Mode` automatically mutes speakers when headphones are plugged. Set to `Disabled` if you want both active.

### HDMI/DP audio pin diagnosis (when audio is sent but nothing comes out)

Some USB-C docks don't properly pass EDID audio capability, causing the Intel HDA HDMI driver to disable the physical pin even though the audio device exists in ALSA. `aplay -D plughw:0,N` succeeds but no sound reaches the monitor.

**Install debugging tools:**

```bash
sudo apt install alsa-utils alsa-tools edid-decode
# alsa-utils → amixer, aplay, speaker-test
# alsa-tools → hda-verb, hdajackretask
# edid-decode → EDID binary analysis
```

**1. Identify DRM connectors and HDMI codec:**

```bash
# Which DRM connectors are connected? (e.g. card0-DP-5, card0-eDP-1)
for c in /sys/class/drm/card0-*; do
    [ -d "$c" ] || continue
    status=$(cat "$c/status" 2>/dev/null)
    [ "$status" = "connected" ] && basename "$c"
done

# Read the EDID from the external monitor's connector
sudo cat /sys/class/drm/card0-DP-5/edid > /tmp/monitor-edid.bin

# Decode it — check for Audio Data Block
edid-decode /tmp/monitor-edid.bin
```

Look for `Audio Data Block:` in the output. If it shows `Linear PCM` with channel/sample support, the EDID itself is correct — the monitor IS reporting audio capability.

**2. Check whether the ELD (kernel's EDID-derived audio report) exists:**

```bash
# ELD lives in /proc/asound or /sys, NOT /sys/class/drm/
find /sys/devices/ -name "eld*" 2>/dev/null | while read f; do echo "--- $f ---"; cat "$f"; done
```

If the EDID has Audio Data Block but the ELD file does NOT exist in the HDA device tree, the i915→snd_hda_intel audio component handshake failed. The kernel created the DRM connector (video works) but never told the HDA driver about the monitor's audio capabilities. This is a DRM driver-level bug, NOT an EDID issue — an EDID firmware override (`drm.edid_firmware=`) changes the content passed to the DRM layer but doesn't fix the i915→HDA communication path.

**3. Identify HDMI codec:**

```bash
ls /proc/asound/card0/codec*
cat /proc/asound/card0/codec#2    # Intel Kabylake HDMI on Kaby Lake
```

Look for "Intel * HDMI" codec — this is the HDA audio controller for the GPU's display outputs. Check the `Pin-ctls` for each HDMI pin complex.

**4. Check pin complex states:**

```bash
# Pin Widget Control (0xf07) — 0x40 = PIN_OUT enabled, 0x00 = disabled
sudo hda-verb /dev/snd/hwC0D2 0x05 0xf07 0
sudo hda-verb /dev/snd/hwC0D2 0x06 0xf07 0
sudo hda-verb /dev/snd/hwC0D2 0x07 0xf07 0

# Pin Sense (0xf09) — bit 31 (0x80000000) = display connected
sudo hda-verb /dev/snd/hwC0D2 0x05 0xf09 0
sudo hda-verb /dev/snd/hwC0D2 0x06 0xf09 0
sudo hda-verb /dev/snd/hwC0D2 0x07 0xf09 0
```

Where:
- `hwC0D2` = card 0, codec #2 (the Intel HDMI codec — codec index varies by hardware; check `ls /proc/asound/card0/codec*`)
- NID 0x05, 0x06, 0x07 = the three HDMI/DP pin complexes on Kaby Lake
- `0xf07` = GET_PIN_WIDGET_CONTROL (returns 0x00=disabled, 0x40=output enabled)
- `0xf09` = GET_PIN_SENSE (returns 0x80000000 if a display is physically connected)

**5. Interpret the results — decision tree:**

```
ELD exists?    Pin-sense 0x80000000?    → Diagnosis
────────────   ──────────────────────   ─────────
YES            YES on matching pin      → Normal. Audio should work. Check volume/mute/sway routing.
YES            NO on all pins           → Display reports audio but isn't connected to HDMI audio. Try a different cable/port.
NO             YES on one pin           → 🔴 DRIVER BUG: EDID has audio, display is connected, but i915 didn't tell HDA. Pin may be locked.
NO             NO on all pins           → Display not on HDMI audio at all (USB-C dock routes video-only, audio handled separately).
```

In the 🔴 case:
- The pin-ctls will read 0x00 (disabled) even though a display is connected on that pin
- `aplay -D plughw:0,N` will succeed but produce no sound (hardware doesn't drive the DP audio channel)
- Attempting `hda-verb` SET_PIN_WIDGET_CONTROL will be silently ignored (driver/GPU locked)

**6. Force-enable attempt:**

```bash
# SET_PIN_WIDGET_CONTROL = 0x707, PIN_OUT = 0x40
sudo hda-verb /dev/snd/hwC0D2 0x06 0x707 0x40   # target the pin with display connected
# Read back to check if it actually changed
sudo hda-verb /dev/snd/hwC0D2 0x06 0xf07 0
```

If the value remains 0x00, the pin is locked by the kernel — hda-verb won't override it.

**7. HDA NID ↔ ALSA device mapping (when the pin-sense doesn't match `aplay -l` labels):**

The `aplay -l` device numbering doesn't match HDA NID order. On Kaby Lake with one external display (Philips BDM4350 via USB-C dock):

```bash
card 0: device 3: HDMI 0 [PHL BDM4350]  ← LABEL says Philips, but may map to NID 0x06 or 0x07
card 0: device 7: HDMI 1 [HDMI 1]
card 0: device 8: HDMI 2 [HDMI 2]
```

Pin-sense shows the display on NID 0x06, NOT 0x05. So ALSA device 3 (labeled "PHL BDM4350") maps to a DIFFERENT pin than the one with the display. The correct device is the one whose NID has pin-sense == 0x80000000.

Test each device individually with a distinct sound:

```bash
timeout 1.5 aplay -D plughw:0,3 -c 2 /usr/share/sounds/alsa/Noise.wav
sleep 3
timeout 1.5 aplay -D plughw:0,7 -c 2 /usr/share/sounds/alsa/Front_Left.wav
sleep 3
timeout 1.5 aplay -D plughw:0,8 -c 2 /usr/share/sounds/alsa/Front_Right.wav
```

Ask the user which device produced sound from the monitor speakers.

**8. Workarounds when HDMI pin cannot be unlocked:**

If EDID has Audio Data Block, pin-sense shows display connected, but pin-ctls stays 0x00 and ELD is missing — this is a **driver-internal i915→snd_hda_intel handshake failure**. No amount of hda-verb, module parameter fiddling, or EDID firmware override will fix it (the parallel case on Fedora's HP Elitedesk was eventually traced to BIOS-level pin routing on that hardware; no generic software fix exists).

Practical workarounds, in order of reliability:

1. **Physical 3.5mm cable** (most reliable) — most monitors have a 3.5mm audio input. Connect dock's headphone jack to monitor's audio-in. After connecting, set WirePlumber default sink to the dock's USB audio device:
   ```bash
   wpctl set-default <ID_OF_DOCK_USB_SINK>
   ```

2. **Try the dock's HDMI port instead of DP** — if the dock has an HDMI port alongside DP, HDMI's native audio embedding sometimes works where DP's separate audio channel fails. This is hardware-dock specific.

3. **Reload snd-hda-intel** — sometimes unplugging and replugging the USB-C cable after boot forces EDID retraining:
   ```bash
   sudo modprobe -r snd_hda_intel && sudo modprobe snd_hda_intel
   ```
   (This restarts ALL HDA audio; save work first, as it may kill audio for a moment.)

4. **Check for BIOS "DP Audio" or "Flex IO" settings** — some HP/Lenovo laptops have BIOS options that affect whether USB-C DP ports expose audio. On Lenovo X1 Tablets this option typically does not exist.

### Testing audio output to a specific device

```bash
# Through PipeWire (preferred — uses WirePlumber routing)
pw-play --target=alsa_output.pci-0000_00_1f.3.analog-stereo /usr/share/sounds/alsa/Front_Center.wav

# Through ALSA directly (bypasses PipeWire — for hardware testing)
timeout 2 aplay -D plughw:0,N -c 2 /usr/share/sounds/alsa/Front_Center.wav

# With volume boost (for quiet monitors)
timeout 2 pw-play --volume=1.5 /usr/share/sounds/alsa/Front_Center.wav
```

Available test sounds: `Front_Center.wav`, `Front_Left.wav`, `Front_Right.wav`, `Noise.wav`.

The `pw-play --target=` name can be found from `wpctl status` (look for the sink's node.name format) or `pw-link -o`.

### Audio routing GUI tools (Wayland-native)

| Tool | Description | Install |
|------|-------------|---------|
| **qpwgraph** | PipeWire audio graph — drag connections between nodes, per-stream volumes, save/load routing sessions. Qt6 Wayland-native. | `apt install qpwgraph` |
| **Helvum** | GTK4 PipeWire patchbay, inspired by Catia. Lighter, simpler. | `apt install helvum` |
| **Waybar pulseaudio module** | Bar-integrated volume slider (scroll to change, click to mute). Requires Waybar (not swaybar). | `apt install waybar` |

All three are Wayland-native (no XWayland dependency). The user can install all three — they serve different use cases:
- **Waybar module** → daily quick volume control
- **qpwgraph** → routing changes, debugging stream connections
- **Helvum** → lightweight graph viewer

### Waybar pulseaudio module config

```json
// ~/.config/waybar/config (relevant section)
"modules-right": ["pulseaudio", "clock"],
"pulseaudio": {
    "format": "{icon} {volume}%",
    "format-muted": "♫",
    "on-click": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
    "scroll-step": 5
}
```

Replace `bar {}` in sway config with `exec_always waybar`.

### Waybar: dual-bar config (macOS Sequoia style)

Waybar supports **multiple independent bar instances** by writing a JSON array instead of a single object. Each `{}` in the array is one bar. This creates a macOS-style top menu bar + bottom dock.

#### JSONC comment support

Waybar v0.12.0+ supports `//` and `/* */` comments in its config (uses jsoncpp). Unlike Python's `json.loads`, waybar parses them without issues — confirmed working on Debian 13's waybar 0.12.0 package. Comments help document the large dual-bar config.

#### Icons rendering: Nerd Font requirement

Waybar `custom/*` modules commonly use Unicode Private Use Area characters for icons (e.g. ``, ``, `󰉋`, ``, ``, ``, ``). These are from the **Nerd Fonts** patched sets. Without a Nerd Font installed, all icons render as empty boxes.

Debian does not ship Nerd Fonts in its repositories. Install the **Symbols Only** variant for minimal size (~2.6 MB vs 50+ MB for a full patched font):

```bash
mkdir -p ~/.local/share/fonts
curl -fL --max-time 30 -o /tmp/NerdFontsSymbolsOnly.zip \
  https://github.com/ryanoasis/nerd-fonts/releases/download/v3.3.0/NerdFontsSymbolsOnly.zip
cd /tmp && unzip NerdFontsSymbolsOnly.zip -d ~/.local/share/fonts/NerdFontsSymbols
fc-cache -fv
```

Then reference the font in CSS:

```css
font-family: "Symbols Nerd Font", "Noto Sans CJK SC", "Noto Sans", sans-serif;
```

The `Symbols` variant covers all Nerd Icons (devicons, fa-brands, oct-icons, material, powerline, etc.) without changing the main monospace font. Place it FIRST in the font stack so icons resolve before any CJK/Sans fallback. CJK characters fall through to `Noto Sans CJK SC`.

### Disabling swaybar when using Waybar

The `include /etc/sway/config` line in the user's `~/.config/sway/config` imports the system default config which **starts swaybar via its own `bar {}` block**. Waybar and swaybar cannot both run — they fight for the same screen position.

**Wrong approaches** (do not work):
- `bar {}` or `bar { status_command none }` — creates a second bar but does not disable the system one (sway treats each `bar {}` block as an independent bar)
- `exec_always killall swaybar` — race condition; sway respawns swaybar immediately on reload

**Correct approach**: Remove `include /etc/sway/config` from the user config entirely, then copy the useful parts (key bindings, mode definitions, multimedia keys) directly into the user config — **but skip the `bar {}` section**. This is the only reliable way to prevent swaybar from starting.

Essential sections to keep from `/etc/sway/config`:
1. Variables (`$mod`, `$term`, direction keys) — already defined in user config
2. Standard key bindings (workspace switching, focus movement, window management, fullscreen, floating, layout modes, scratchpad, resize mode, multimedia keys, screenshot) — must be manually duplicated since `include` is removed (expect ~60 `bindsym` lines)
3. `include /etc/sway/config.d/*` — keep this at the bottom for systemd integration
4. DO NOT copy the `bar {}` section

Tradeoff: the user config becomes longer (~60 binding lines vs the previous 1-line include). But this gives full control over which system defaults apply and guarantees no swaybar.

**Critical: `$mod` must be defined before any `bindsym` referencing it.** Sway parses config line-by-line. If `bindsym $mod+d exec something` appears before `set $mod Mod4`, sway silently ignores that binding at runtime. The user sees "Mod4+4 找不到绑定" or similar when pressing the key. Fix: move all `set $...` lines to the very top of the config file, before any `bindsym` or `unbindsym` that references them. The correct placement pattern:

```bash
# Line 1: variable definitions (must be first)
set $mod Mod4
set $term foot
...

# Then bindsym referencing the variables
bindsym $mod+Return exec $term
```

**Pattern**: `~/.config/waybar/config` is a JSON array of bar objects:

```json
[
  // ── Top bar (menubar style) ──
  {
    "layer": "top",
    "position": "top",
    "exclusive": true,
    "height": 24,
    "modules-left": ["sway/workspaces"],
    "modules-center": ["sway/window", "custom/term", "custom/chrome"],
    "modules-right": ["pulseaudio", "bluetooth", "network", "cpu", "memory", "clock"]
  },
  // ── Bottom bar (Dock style) ──
  {
    "layer": "top",
    "position": "bottom",
    "exclusive": false,
    "height": 48,
    "modules-left": ["custom/launcher"],
    "modules-center": ["wlr/taskbar"]
  }
]
```

CSS targets each bar independently: the top bar matches `window#waybar` (first instance). The bottom bar is `window#waybar:last-child` or `window#waybar:nth-child(2)`.

Full config and CSS for a single-monitor dual-bar setup: `references/waybar-macos-sequoia-dual-bar.md`.

For rich tooltips (multi-line Pango, Tailscale peer list with three-state colors, sway memory breakdown, fan RPM, etc.) backed by a single Python entry point, see `references/waybar-rich-tooltip-pattern.md` and the `templates/waybar-status.py` starter.

### Waybar `wlr/taskbar` module (app dock)

The `wlr/taskbar` module shows **open application windows** as clickable icons, like macOS Dock or Windows taskbar. It's a wlroots-native module, supported on sway and Hyprland.

```json
"wlr/taskbar": {
    "format": "{icon}",        // icon only, or "{icon} {title:.17}"
    "icon-size": 36,           // 28-36 for bottom dock, 16-20 for top bar
    "spacing": 4,
    "on-click": "activate",     // left-click: bring window to front
    "on-click-middle": "close", // middle-click: close the app
    "tooltip-format": "{title}" // hover shows window title
}
```

CSS for the dock-style taskbar buttons:

```css
#taskbar button {
    padding: 0 4px;
    background: transparent;
    border-bottom: 2px solid transparent;
}
#taskbar button.active {
    border-bottom: 2px solid #5294e2;
}
#taskbar button:hover {
    background: rgba(255,255,255,0.1);
}
```

### Quick-launch buttons (`custom/xxx` with `on-click`)

Waybar's `custom/<name>` module can be used as a pure clickable button with `format` + `on-click`:

```json
"custom/term": {
    "format": "  ",
    "on-click": "foot",
    "tooltip": false
},
"custom/launcher": {
    "format": "  ",
    "on-click": "fuzzel",
    "tooltip": false
}
```

CSS hover feedback:

```css
#custom-term, #custom-chrome {
    padding: 0 8px;
    color: #ccc;
}
#custom-term:hover, #custom-chrome:hover {
    background: rgba(255,255,255,0.1);
}
```

### `sway/window` rewrite (empty workspace fallback)

To show a fallback name when no window is focused (empty workspace), use the `rewrite` config option with a regex that matches empty/blank window titles:

```json
"sway/window": {
    "max-length": 50,
    "rewrite": {
        "^(?!.*\\\\S).*": "浏览器"
    }
}
```

The regex `^(?!.*\\S).*` matches any string with no non-whitespace characters (empty or blank). The replacement text appears instead. Common fallback names: "Desktop", "Finder", "浏览器", "IDLE".

### Auto-hide limitation

Waybar **does not support native auto-hide** (no `mode hide` like swaybar). Solutions ranked by reliability:

1. **Floating dock** (`"exclusive": false`) — the bar floats on top of windows. When an app goes fullscreen, the bar is covered. This is the closest to auto-hide without extra tools. ✓ No extra packages.
2. **Toggle script** — use swayidle or a bindsym to `killall -STOP waybar` / `killall -CONT waybar`. Side effect: stops ALL waybar instances (both top and bottom), not one bar at a time.
3. **External tools** like `waybar-auto-hide` (third-party, package-manager availability varies).

### Waybar bluetooth + network modules

These modules are compiled into Waybar v0.12.0+ and available in the Debian package:

```json
"bluetooth": {
    "format": " {status}",
    "format-connected": "",
    "on-click": "blueman-manager"
},
"network": {
    "format-wifi": "{essid}",
    "format-ethernet": " {ifname}",
    "format-disconnected": "󰖪",
    "tooltip-format": "{ifname}\n{ipaddr}"
}
```

**Pitfall — bluetooth module crashes on v0.12.0:** The bluetooth module crashes with `unhandled exception: argument not found` when `tooltip-format` contains placeholders like `{controller_alias}` or `{num_connections}`, or when `format-connected` uses `{device_count}`. Safe configuration on v0.12.0: `format` with `{status}`, `format-connected` with static text only, `on-click`. Avoid `tooltip-format` entirely for the bluetooth module on this version. This was fixed in later releases.

Pitfall: the `bluetooth` module shows controller status (on/off/connected) but does NOT show paired device names in the bar. For device management, the `on-click` launcher (`blueman-manager`) is essential. `format-connected` shows a device count, not individual device names — that's a Waybar design limitation.

### PWA .desktop management (taskbar icon fix)

Chrome PWA windows in sway have `app_id = chrome-<24char-extension-id>-Default` (e.g. `chrome-gaclnekabaleococgnghmjhcdfipepjj-Default`). The `wlr/taskbar` shows the window icon, which falls back to Chrome's generic icon unless the `.desktop` file has a matching `StartupWMClass`.

**Fix**: add `StartupWMClass=chrome-<appid>-Default` to each PWA `.desktop` file. After adding it, the taskbar shows the PWA's actual icon from `~/.local/share/icons/hicolor/`, not Chrome's icon.

**Dedup workflow**:
1. `ls ~/.local/share/applications/chrome-*.desktop` — list all PWA files
2. `grep "^Name=" *` — check for duplicates (same Name, different app-id)
3. Delete the unwanted one, rename the kept one to human-readable
4. Renamed files persist across Chrome updates (Chrome only re-creates auto-named files)
5. Add `StartupWMClass=chrome-<appid>-Default` for all renamed files

**Note**: Chrome PWA `.desktop` files reference icon paths like `chrome-<appid>-Default` which resolve to `~/.local/share/icons/hicolor/*/apps/chrome-<appid>-Default.png`. Renaming the `.desktop` file does NOT break icon resolution — the Icon field uses the old app-id path, which still exists.

### Bottom dock separator module

For visual separation between PWA launcher buttons and the taskbar (like macOS Dock's divider), use a `custom/sep` module:

```json
"custom/sep": { "format": "│", "tooltip": false }
```

```css
#custom-sep { padding: 0 3px; color: #555; font-size: 14px; }
```

### Waybar custom module: Tailscale VPN status

Waybar has no built-in Tailscale module. Use `custom/<name>` with `return-type: json` and a polling script:

**Script** (`~/.local/bin/ts-status.sh`):
```bash
#!/bin/bash
if output=$(tailscale status 2>/dev/null | head -4); then
  if echo "$output" | grep -q .; then
    ips=$(echo "$output" | awk '{print $1}' | grep '100\.' | head -3 | tr '\n' ' ')
    echo "{\"text\":\"\",\"alt\":\"connected\",\"tooltip\":\"Tailscale\\n$ips\"}"
    exit 0
  fi
fi
echo "{\"text\":\"󰖪\",\"alt\":\"disconnected\",\"tooltip\":\"Tailscale 未运行\"}"
```

**Waybar config:**
```json
"custom/tailscale": {
    "exec": "/home/dr/.local/bin/ts-status.sh",
    "return-type": "json",
    "interval": 30,
    "format": "{icon}",
    "format-icons": { "connected": "", "disconnected": "󰖪" }
}
```

**CSS:**
```css
#custom-tailscale { color: #a78bfa; }
#custom-tailscale.disconnected { color: #555; }
```

The `alt` field from the JSON output selects the icon. 30s poll is the simplest approach since Tailscale lacks a dbus interface.

## UxPlay AirPlay receiver (sway integration)

UxPlay (`apt install uxplay`) is an AirPlay mirroring/audio server. It creates an XWayland window on sway.

### Installation

```bash
sudo apt install --no-install-recommends uxplay
# If using h265 support, also install:
sudo apt install gstreamer1.0-plugins-bad
# Clear gstreamer cache if plugins were missing:
rm -rf ~/.cache/gstreamer-1.0
```

### sway auto-start + auto-fullscreen

Add to `~/.config/sway/config`:

```
# UxPlay AirPlay receiver
exec_always uxplay -n <name> -h265
# Auto-fullscreen when AirPlay window appears
for_window [app_id="uxplay"] fullscreen enable
```

The `app_id` of the UxPlay window is `uxplay` (lowercase). The window's title is `OpenGL Renderer` (the GStreamer rendering context). The `for_window` rule fires only when a client connects and the window appears — UxPlay itself is a daemon that's always listening but only opens the window during active streaming.

### mDNS NameConflict

If a UxPlay instance was killed prematurely (SIGKILL rather than SIGTERM/Q), the mDNS registration may persist. Restarting UxPlay within seconds produces `kDNSServiceErr_NameConflict`. Fix:

```bash
pkill -9 uxplay; sleep 3; uxplay -n <name> -h265
```

See "Finding the sway IPC socket" above for how scripts can detect the sway socket dynamically.

## See also

- `references/sway-session-architecture.md` — design notes on the unified script pattern, when to extend vs. split
- `references/modern-standby-s0ix.md` — S0ix vs S3 deep detection, SSH-over-s2idle reality, WOL limitations, logind power button mapping
- `references/intel-hdmi-dp-audio-pin-diagnostics.md` — full diagnostic walkthrough for Intel HDA HDMI audio over USB-C dock (Kaby Lake case study: EDID good, pin sense shows display, but pin locked and ELD missing)
- `references/bash-dynamic-terminal-title.md` — dynamic foot/xterm terminal title via bashrc: show running command while active, directory path at rest. Covers `PROMPT_COMMAND`, `DEBUG` trap, and the OSC escape sequence `\033]0;...\007` for foot/foot-256color/tmux-256color.
- `templates/sway-session.py` — portable unified entry point skeleton (Philips string is the one system-specific value to swap)
- `templates/swayidle-config` — minimal config skeleton
- `scripts/verify-swayidle-config.sh` — automated config validator
- `scripts/s2idle-monitor.sh` — live s2idle/SSH/CPU/NIC monitor for diagnosing "is the system really in s2idle?" and "why is SSH slow?"

## Pitfall: surgical revert when two agents edit the same file

If the user asks to revert your waybar changes while another agent is
simultaneously editing the dock section in the same file, **never
wholesale-restore from your backup**. That overwrites the other agent's
in-progress work.

Pattern that worked: use `diff` to identify where your changes end and
the other agent's begin, then `sed -n '1,Np' backup` + `sed -n 'M,$p'
current` to splice your-revert-target lines with the other agent's
edits. The line numbers come from `grep -n` of a section header. Always
validate the spliced result with `python3 -c "import json; json.load(...)"`
before `mv` into place.

For CSS files, the same logic applies but with `patch` rather than
`sed`. **Bonus pitfall**: the user's CSS may be in a different theme
than the one captured by your backup (a sync or git pull may have
replaced it between your read and your edit). Trust the **current**
file state — use `diff` to find your additions and `patch` them out,
don't restore the whole file from backup.

Full worked example: `references/waybar-rich-tooltip-pattern.md` →
"Surgical revert when another agent is working on the same file".

**Better alternative when planning ahead**: instead of letting two agents touch
the same file and needing surgical revert, **split the file as a concurrency
boundary**. For waybar specifically, use `config-top` + `config-bottom` (each
a single `{}` object, two independent waybar processes) so each agent owns
one file and never collides. See `local/waybar-config/SKILL.md` →
"多 agent 并发编辑 waybar 的最佳实践" for the full pattern.

## Pitfall: the "5-30 second SSH wakeup" trap

The widely-cited "5-30 seconds for SSH to work after s2idle wake" figure is misleading. It applies only when the system actually walked a full suspend path AND the network stack was torn down (lid close → suspend → wake). For a system that is just CPU-idle at 800 MHz (S0, just deep C-state), SSH latency is network RTT + 1-5 ms — the NIC is still in D0 if `power/control = on`, and the CPU exits C10 in microseconds.

Before claiming "s2idle blocks SSH", run `scripts/s2idle-monitor.sh` for a few minutes. If the CPU frequency column is mostly 800 MHz but SSH responses are < 1 s, the system was NOT in s2idle — it was just S0-idle. The distinction matters. Full correction in `references/modern-standby-s0ix.md` under "SSH into a sleeping laptop".
