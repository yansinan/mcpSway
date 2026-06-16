# Intel HDMI/DP Audio Pin Diagnostics (Kaby Lake + USB-C Dock)

## Case: Lenovo X1 Tablet Gen 3 + HP Dock + Philips BDM4350 (DP 1.2)

### Symptom
- Video over USB-C dock DP works fine at 4K
- Audio: `aplay -D plughw:0,N` succeeds, no sound from monitor speakers
- Internal speakers (Built-in Audio) work fine
- EDID contains Audio Data Block (2ch PCM, 48/44.1/32 kHz)

### Hardware chain
```
X1 Tablet (Kaby Lake-R i7-8550U)
  → USB-C (Intel HDA HDMI codec#2, NID 0x05-0x07)
    → HP USB-C Dock (DisplayPort MST via USB-C)
      → DP 1.2 cable → Philips BDM4350 (3840×2160, speakers 2×7W)
```

### Diagnostic steps (in order)

```bash
# 1. List ALSA HDMI devices
aplay -l | grep HDMI
# → device 3: HDMI 0 [PHL BDM4350]
# → device 7: HDMI 1 [HDMI 1]
# → device 8: HDMI 2 [HDMI 2]

# 2. Check DRM connectors
for c in /sys/class/drm/card0-*; do
    [ -d "$c" ] || continue
    status=$(cat "$c/status" 2>/dev/null)
    [ "$status" = "connected" ] && basename "$c"
done
# → card0-DP-5: connected  (this is the Philips monitor)
# → card0-eDP-1: connected  (built-in screen)

# 3. Dump and analyze EDID
sudo cat /sys/class/drm/card0-DP-5/edid > /tmp/philips-edid.bin
edid-decode /tmp/philips-edid.bin
# → Audio Data Block present ✅ (2ch PCM, 48/44.1/32 kHz, 24/20/16 bit)
# → Speaker Allocation: FL/FR ✅

# 4. Check ELD (EDID-to-HDA bridge)
find /sys/devices/ -name "eld*" 2>/dev/null | while read f; do echo "--- $f ---"; cat "$f"; done
# → NO ELD files found ❌ (i915 never passed audio info to HDA)

# 5. Examine HDA HDMI codec
cat /proc/asound/card0/codec#2 | grep -A10 "Node 0x0[5-7]"
# → Node 0x05: Pin-ctls 0x00 (disabled)
# → Node 0x06: Pin-ctls 0x40 (enabled)
# → Node 0x07: Pin-ctls 0x00 (disabled)

# 6. Pin sense (presence detect)
sudo hda-verb /dev/snd/hwC0D2 0x05 0xf09 0  # → 0x0 (no display)
sudo hda-verb /dev/snd/hwC0D2 0x06 0xf09 0  # → 0x80000000 (display!)
sudo hda-verb /dev/snd/hwC0D2 0x07 0xf09 0  # → 0x0 (no display)
# → NID 0x06 has the display, 0x05 and 0x07 are empty
# → ALSA device 3 (labeled "PHL BDM4350") maps to NID 0x05 (empty!)
# → The actual display is on NID 0x06 (ALSA device 7, labeled "HDMI 1")

# 7. Test each device
timeout 1.5 aplay -D plughw:0,3 -c 2 /usr/share/sounds/alsa/Noise.wav      # NID 0x05 — no display
timeout 1.5 aplay -D plughw:0,7 -c 2 /usr/share/sounds/alsa/Front_Left.wav # NID 0x06 — has display!
timeout 1.5 aplay -D plughw:0,8 -c 2 /usr/share/sounds/alsa/Front_Right.wav # NID 0x07 — no display
```

### Root cause
The ALSA device-to-HDA-NID mapping is **not 1:1** with `aplay -l` labels. ALSA device 3 bears the monitor's name ("PHL BDM4350") from the initial EDID probe during boot, but the actual physical connection is on NID 0x06. Meanwhile, the i915→snd_hda_intel ELD handshake failed entirely (no ELD anywhere), so even the correctly mapped pin (NID 0x06) won't drive audio — the GPU hardware disables the DP audio lane when it receives no EDID audio report from the DRM layer.

`hda-verb` SET_PIN_WIDGET_CONTROL is silently ignored because the pin is locked by the kernel driver.

### Resolution
EDID firmware override (`drm.edid_firmware=`) won't help — the EDID already has Audio Data Block. The problem is a **driver handshake failure**, not a data problem. No software-only workaround exists on the current kernel.

**Practical fix**: 3.5mm audio cable from dock's headphone jack to monitor's audio input.
