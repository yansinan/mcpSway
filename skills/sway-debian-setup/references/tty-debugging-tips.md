# TTY Debugging Workflow — Practical Tips

From a real session debugging sway external monitor on X1 Tablet Gen 2 (Kaby Lake i915) + USB-C dock + Philips 4K monitor.

## The TTY pasting problem

TTY (Ctrl+Alt+F1/F2) does NOT support:
- Mouse selection/copy/paste
- Clipboard operations
- Any form of text transfer from the agent's response to the terminal

**Workaround: write scripts to `~/` and tell the user to run them.**

Instead of:
```
I'll type it for you:
> sudo sed -i 's/.../.../' /etc/default/grub
```

Do:
```
cat > ~/grub.sh << 'EOF'
#!/bin/bash
set -e
sudo sed -i 's/.../.../' /etc/default/grub
sudo update-grub
echo "Done. sudo reboot."
EOF
chmod +x ~/grub.sh
echo "Run: sh ~/grub.sh"
```

## Diagnosis summary for Kaby Lake + USB-C dock

The actual bug was never resolved. The monitor was:
- Detected by kernel (connected, EDID=256 bytes)
- Detectable by modetest (connector listed)
- Configurable by sway (mode set success, dpms on)
- BUT physically black — no pixel output

All of these were tried without success:
- `WLR_DRM_NO_MODIFIERS=1` — no effect
- `i915.enable_dp_mst=0` (both toggled) — no effect
- `modetest` from TTY (no compositor) — no effect
- `kwin_wayland` (non-wlroots compositor) — no effect

Gnome (mutter) did work per user report. The suspected root cause is a Kaby Lake i915 + USB-C dock link-training negotiation quirk that mutter handles but standalone wlroots/KWin don't.

## Quick script pattern reference

```bash
# grub edit + update
cat > ~/grub.sh << 'EOF'
#!/bin/bash
set -e
sudo sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="quiet"/GRUB_CMDLINE_LINUX_DEFAULT="quiet i915.enable_dp_mst=0"/' /etc/default/grub
sudo update-grub
echo "=== Done. Run: sudo reboot ==="
EOF

# modetest
cat > ~/t.sh << 'EOF'
#!/bin/bash
sudo modetest -M i915 -s $(modetest -M i915 -c | grep 'connected' | head -1 | awk '{print $1}'):3840x2160-60
echo "Press Enter to exit"
read
EOF
```
