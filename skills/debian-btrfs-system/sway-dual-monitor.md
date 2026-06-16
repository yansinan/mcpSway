# Sway / Wayland — Dual Monitor Debugging

## Display Diagnostics (in Sway)

```bash
swaymsg -t get_outputs          # list outputs, modes, positions
wlr-randr                        # current mode config per output (after `sudo apt install wlr-randr`)
wdisplays                        # GUI display arrangement tool (after `sudo apt install wdisplays`)
```

## Kernel-side Diagnostics

```bash
# Check connector status
cat /sys/class/drm/card0-*/status

# List available modes per connector
cat /sys/class/drm/card0-*/modes

# Full DRM pipeline state (Intel)
sudo cat /sys/kernel/debug/dri/0/i915_display_info

# Decode monitor EDID
sudo cat /sys/class/drm/card0-DP-3/edid | sudo edid-decode
```

## DP-MST Issue (Kabylake + 4K External)

**Symptom:** Display detected (connector shows connected, modes available, CRTC active, framebuffer allocated) but physical monitor shows no signal.

**Root cause:** Intel Kabylake GPU (UHD 620) drives external DP through DP-MST (Multi-Stream Transport) encoder. Some 4K monitors lose signal over MST.

**Fix:** Add kernel parameter to disable MST:
```bash
# /etc/default/grub
GRUB_CMDLINE_LINUX="... i915.enable_dp_mst=0"
sudo update-grub
sudo reboot
```

## Tools

```bash
sudo apt install -y wlr-randr wdisplays kanshi edid-decode libdrm-tests
```

## Kanshi Auto-Switch Config

`~/.config/kanshi/config`:
```
profile dual {
    output eDP-1 enable
    output DP-3 enable mode 3840x2160@60Hz position 3000 0
}

profile single {
    output eDP-1 enable
    output DP-3 disable
}
```

Sway config (`~/.config/sway/config`):
```
exec_always killall kanshi 2>/dev/null
exec_always kanshi
```
