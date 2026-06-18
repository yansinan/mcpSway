# Display Troubleshooting — sway Output Inspection

## Inspect current mode + available modes

```bash
SWAYSOCK=$(find /run/user/$(id -u)/sway-ipc.*.sock | head -1)
swaymsg -s "$SWAYSOCK" -t get_outputs | python3 -c "
import json, sys
outs = json.load(sys.stdin)
for o in outs:
    cm = o.get('current_mode', {})
    print(f\"{o['name']}: {cm.get('width')}x{cm.get('height')} @ {cm.get('refresh',0)/1000:.3f}Hz\")
    print(f\"  make={o['make']} model={o['model']} serial={o['serial']}\")
    print(f\"  active={o['active']} scale={o.get('scale')} transform={o.get('transform')}\")
    if o['modes']:
        modes = sorted(o['modes'], key=lambda m: -(m['width']*m['height']))
        print(f\"  max EDID mode: {modes[0]['width']}x{modes[0]['height']} @ {modes[0]['refresh']/1000:.3f}Hz\")
        print(f\"  modes available: {len(modes)}\")
"
```

## Set a resolution (from EDID mode list)

```bash
swaymsg -s "$SWAYSOCK" 'output <NAME> mode <W>X<H>@<R>Hz'
# e.g.
swaymsg -s "$SWAYSOCK" 'output HDMI-A-1 mode 1920x1080@60Hz'
```

## Force a custom mode (not in EDID)

```bash
swaymsg -s "$SWAYSOCK" 'output <NAME> mode --custom <W>x<H>@<R>Hz'
```

**Warning**: `--custom` may return `"success": true` even when the mode is silently rejected by the GPU/driver. Always verify with the inspect script above.

## Known causes of silent mode rejection

- GPU HDMI version limit (e.g. Intel HD 4000 = HDMI 1.4a → no 4K)
- Cable bandwidth (USB-C dock with HDMI conversion often limited)
- Dock MST constraints (wlroots MST payload allocation issue)
- Monitor EDID corruption or truncation
- Custom modeline not supported by GPU timing generator

## Check GPU capabilities

```bash
# GPU model
lspci | grep -i vga
# i915 generation
sudo cat /sys/kernel/debug/dri/0/i915_capabilities 2>/dev/null | head -10
# CPU for iGPU model
cat /proc/cpuinfo | grep "model name" | head -1
```

## Verify aspect ratio matches the monitor's native ratio

When setting a non-native resolution, the aspect ratio must match the monitor's native ratio or the image will be stretched/squished.

```bash
SWAYSOCK=$(find /run/user/$(id -u)/sway-ipc.*.sock | head -1)
swaymsg -s "$SWAYSOCK" -t get_outputs | python3 -c "
import json, sys
outs = json.load(sys.stdin)
for o in outs:
    cm = o.get('current_mode', {})
    w, h = cm.get('width', 0), cm.get('height', 0)
    ratio = w / h if h else 0
    # Common aspect ratios: 16/9=1.777, 16/10=1.6, 4/3=1.333, 21/9=2.333
    print(f\"{o['name']}: {w}x{h} @ {cm.get('refresh',0)/1000:.3f}Hz\")
    print(f\"  aspect ratio: {ratio:.4f}\")
    if abs(ratio - 16/9) < 0.02:
        print(f\"  -> 16:9 ✓\")
    elif abs(ratio - 16/10) < 0.02:
        print(f\"  -> 16:10\"')
    elif abs(ratio - 4/3) < 0.02:
        print(f\"  -> 4:3\"')
    elif abs(ratio - 21/9) < 0.02:
        print(f\"  -> 21:9\"')
    else:
        print(f\"  -> non-standard ({w}/{h} = {w/gcd(w,h)}:{h/gcd(w,h)})\")
"
```

Native resolution ratio (from the monitor model/EDID) is the reference point. For Philips BDM4065/BDM4350: native is 3840×2160 = **16:9**. Use only 16:9 candidate modes (1920×1080, 1280×720) unless the display is ultrawide.
