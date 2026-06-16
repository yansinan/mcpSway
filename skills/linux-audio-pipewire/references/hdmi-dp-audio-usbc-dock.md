# HDMI/DP Audio Over USB-C Dock Debugging

## Symptom
`aplay -l` shows the HDMI/DP device, `aplay` plays without errors, but **no sound** comes out of the monitor. Audio works in Windows.

## Why It Happens
i915 (Intel GPU driver) fails to pass EDID audio information to snd_hda_intel (HDA audio driver). The HDA codec pin for the monitor's DP connection has `Pin-ctls: 0x00` (disabled) and `pin-sense: 0x0` (no display detected) even though video is fine.

## Diagnostic Steps

### 1. Identify the DRM connector
```bash
# Find which connector is the external monitor via dock
cat /sys/class/drm/card0-*/status | grep connected
# Example: card0-DP-5:connected
```

### 2. Check EDID for audio support
```bash
sudo cat /sys/class/drm/card0-DP-5/edid | edid-decode
# Look for "Audio Data Block" and "Linear PCM"
```

### 3. Find the HDA codec
```bash
# Intel HDMI/DP codec is typically codec#2 on Kabylake
cat /proc/asound/card0/codec#2 | head -20
# Look for "Codec: Intel Kabylake HDMI" or similar
```

### 4. Check pin complex states with hda-verb
```bash
# List all pins and their current control state
sudo hda-verb /dev/snd/hwC0D2 0x05 0xf07 0  # Pin 0x05
sudo hda-verb /dev/snd/hwC0D2 0x06 0xf07 0  # Pin 0x06  
sudo hda-verb /dev/snd/hwC0D2 0x07 0xf07 0  # Pin 0x07

# Check presence detect
sudo hda-verb /dev/snd/hwC0D2 0x05 0xf09 0  # Pin sense 0x05
sudo hda-verb /dev/snd/hwC0D2 0x06 0xf09 0  # Pin sense 0x06

# Expected output for working pin: value = 0x40 (PIN_OUT enabled)
# Expected output for presence: value = 0x80000000 (bit 31 = display connected)
```

### 5. Map ALSA PCM to HDA pins
```bash
cat /proc/asound/card0/pcm3p/info  # device 3 = HDMI 0
cat /proc/asound/card0/pcm7p/info  # device 7 = HDMI 1  
cat /proc/asound/card0/pcm8p/info  # device 8 = HDMI 2

# A pin with display connected AND PIN_OUT is the active one
```

### 6. Check ELD (EDID-like data for HDMI audio)
```bash
ls /proc/asound/card0/eld*  2>/dev/null
# If empty, i915 didn't pass audio info to HDA driver
```

## HDA Verb Reference

| Command | Verb | Param |
|---------|------|-------|
| GET_PIN_WIDGET_CONTROL | 0xf07 | — |
| SET_PIN_WIDGET_CONTROL | 0x707 | 0x40 = PIN_OUT |
| GET_PIN_SENSE | 0xf09 | — |
| SET_PIN_SENSE | 0x709 | — |
| GET_CONV (stream) | 0xf0c | — |

## Known hda-verb Issue
`SET_PIN_WIDGET_CONTROL` via hda-verb often silently fails on modern kernels — the kernel driver ignores the write because pin state is managed by i915/snd_hda_intel component interface.

## Solutions (in priority order)

### Best: 3.5mm Audio Cable
Bypass DP audio entirely. If dock has analog audio output:
```
Dock 3.5mm OUT → 3.5mm cable → Monitor Audio IN
```
Works perfectly, zero config. WirePlumber sees the dock's USB audio as a sink.

### EDID Firmware Override
If EDID already has Audio Data Block (check with edid-decode), this won't help — the issue is i915 not passing existing EDID audio info.

If EDID lacks audio, create a binary EDID with Audio Data Block:
```bash
# 1. Dump current EDID
sudo cat /sys/class/drm/card0-DP-N/edid > edid.bin

# 2. Use edid-decode to create modified version
# 3. Place in /lib/firmware/edid/
# 4. Add to kernel cmdline: drm.edid_firmware=DP-N:edid/filename.bin
```

### HDMI Cable
If dock has HDMI port, try that. HDMI protocol carries audio inherently; DP audio depends on MST/EDID negotiation.

## ELD Doesn't Exist
`/proc/asound/card0/eld#*.1` missing = i915-snd_hda_intel component handshake failed. This is a known kernel bug with USB-C docks on Intel Kabylake/Coffee Lake/UHD 630. No reliable kernel-patch-level fix confirmed — hardware workaround is the practical answer.
