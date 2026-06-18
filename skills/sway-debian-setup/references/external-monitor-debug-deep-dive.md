# External Monitor Debug: Deep Diagnostic Flow

This reference captures the full diagnostic flow from real sessions on an X1 Tablet Gen 2 (Kaby Lake i915) + Debian 13 + USB-C dock + Philips BDM4350 4K monitor. The monitor was detected by the kernel and every compositor (sway, KWin, gnome-shell) but all of them stayed physically black — no signal reached the panel.

**Key insight from the final session:** The monitor worked on a **Live USB** (different kernel) but failed on Debian 13's 6.12.x kernel. This was true for ALL compositors and even the kernel-level `modetest`. The root cause is a **kernel regression** in 6.12.x's i915 driver for this specific GPU + dock combination, not a compositor bug.

## Test Results (Debian 13 kernel 6.12.x)

| Test | Result |
|------|--------|
| sway (wlroots 0.18) | ✗ Black — software saw it, no signal |
| KWin 6.3.6 (KDE compositor) | ✗ Same — software saw it, no signal |
| gnome-shell 48 / mutter | ✗ Same — no signal (confirmed via DBus API) |
| `modetest -M i915 -s` from TTY | ✗ No signal even from kernel DRM |
| **Live USB (different kernel)** | **✓ Worked** |
| Lower resolution 1920x1080 | ✗ Still black |
| `WLR_DRM_NO_MODIFIERS=1` | ✗ No effect |
| `i915.enable_dp_mst=0` + reboot | ✗ No effect |
| `i915.enable_dp_mst=1` (default) + reboot | ✗ No effect |
| DP link force retrain via debugfs | ✗ No effect |

## What Changed Between Sessions

Session 2 (this session) corrected a key assumption from Session 1:
- Session 1 reference said "gnome (mutter) worked per user report" — **this was wrong.** The user had tested gnome on a Live USB, not on the installed Debian. When actually tested on Debian 13, gnome-shell also failed to light the external monitor.
- The root cause is **kernel version-specific**, not compositor-specific.

## Root Cause

The display only works on a **different kernel version** (Live USB kernel). Debian 13's 6.12.x kernel's i915 driver has a regression or missing backport for this Kaby Lake + USB-C dock combination. The DP AUX channel initializes (EDID is read, link capabilities report correctly), but DP link training fails silently — no error in dmesg or in the compositor.

No kernel parameter toggling (`i915.enable_dp_mst`, `i915.enable_dc`, `i915.enable_psr`) resolved it. The fix would be: install a newer or older kernel (Liquorix, backports, or kernel.org mainline).

## Structured Diagnosis Flow

Use this order to identify the root cause of "monitor detected but black":

### 1. Compositor checks (fast, no reboot)

```bash
# Is the monitor detected by the compositor?
swaymsg -t get_outputs | grep -E '"name"|"active"|"make"|"model"'

# Does dpms say On?
swaymsg -t get_outputs | grep -E '"dpms"|"power"'

# Keybindings can't set env vars — check for stale port names
# Use make+model+serial tuple for stable output addressing:
#   swaymsg output "Vendor Model Serial" mode ...
```

### 2. Kernel-level check

```bash
# Does the kernel see it as connected?
cat /sys/class/drm/card0-DP-*/status

# Is the EDID valid?
wc -c /sys/class/drm/card0-DP-*/edid   # 256 bytes for 4K

# What i915 parameters are active?
cat /proc/cmdline | grep i915
```

### 3. Isolate compositor (from TTY, NOT inside sway)

```bash
# modetest — tests kernel DRM directly, no compositor
sudo apt install -y libdrm-utils
modetest -M i915 -c | grep connected
# Find connector ID (first number), then:
sudo modetest -M i915 -s <CONNECTOR>:3840x2160-60
```

- modetest lights it → issue is compositor-specific (wlroots, buffer handling)
- modetest stays black → issue is kernel/driver/hardware

### 4. Cross-compositor test

If modetest and sway both fail, install KWin and test:
```bash
sudo apt install -y kwin-wayland kscreen
killall sway
kwin_wayland foot     # starts compositor + foot terminal
kscreen-doctor -o     # list outputs
kscreen-doctor output.DP-2.enable
# Exit: Ctrl+Alt+F2 → killall kwin_wayland → Ctrl+Alt+F1
```

If KWin also fails, the issue is not wlroots-specific.

### 5. Kernel parameter toggling (requires reboot)

```bash
# Edit /etc/default/grub, toggle i915.enable_dp_mst:
#   GRUB_CMDLINE_LINUX_DEFAULT="quiet i915.enable_dp_mst=0"
sudo update-grub && sudo reboot
```

### 6. Live USB test

If all of the above fail, boot a Live USB (Ubuntu 24.04+, Debian 12+). If the monitor works there but not on your installed system, the root cause is a kernel version regression. **This is not a sway/KWin/gnome problem.** Fix: install a different kernel.

## Key Debug Files (i915 debugfs)

Available even without `drm.debug=0x1e`:

```bash
# DP link capabilities (live)
sudo cat /sys/kernel/debug/dri/0/DP-2/i915_dp_max_lane_count
sudo cat /sys/kernel/debug/dri/0/DP-2/i915_dp_max_link_rate
sudo cat /sys/kernel/debug/dri/0/DP-2/output_bpc
sudo cat /sys/kernel/debug/dri/0/i915_dp_mst_info

# Force DP link retrain (no reboot)
echo 1 | sudo tee /sys/kernel/debug/dri/0/DP-2/i915_dp_force_link_retrain
echo 4 | sudo tee /sys/kernel/debug/dri/0/DP-2/i915_dp_force_lane_count
echo 540000 | sudo tee /sys/kernel/debug/dri/0/DP-2/i915_dp_force_link_rate
```

## Gnome-shell DBus Monitor Control

When debugging gnome-shell, use the Mutter DisplayConfig DBus interface:

```bash
# List current monitors
gdbus call --session --dest org.gnome.Mutter.DisplayConfig \
  --object-path /org/gnome/Mutter/DisplayConfig \
  --method org.gnome.Mutter.DisplayConfig.GetCurrentState
```

Switching gnome-shell debug output:

```bash
MUTTER_DEBUG=1 MUTTER_VERBOSE=1 dbus-run-session -- gnome-shell --wayland
```
