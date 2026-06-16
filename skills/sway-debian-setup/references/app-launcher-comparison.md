# Wayland Application Launcher Comparison

Quick reference for choosing a launcher on sway/Wayland.

## At a Glance

| Launcher | Size | Backend | .desktop | Icons | Config |
|----------|------|---------|----------|-------|--------|
| **fuzzel** | ~346KB | wlroots layer-shell (Cairo) | ✅ default | ✅ | fuzzel.ini |
| **tofi** | ~100KB | wlroots layer-shell | ✅ tofi-drun | ❌ text-only | tofi.conf |
| **wofi** | ~172KB | GTK3 | ✅ default | ✅ | wofi/style.css |
| **bemenu** | ~100KB | wlroots layer-shell | ❌ PATH only | ❌ text-only | env vars |
| **rofi** | ~800KB+ | X11 (XWayland) | ✅ drun mode | ✅ | themes/rasi |

## Details

### fuzzel ✅ (recommended on sway)
- **Pros**: Wayland-native, discovers Chrome PWAs automatically, icons, fuzzy search, simple config
- **Cons**: Larger than tofi
- **Install**: `sudo apt install fuzzel`
- **Config**: `~/.config/fuzzel/fuzzel.ini`
- **Use**: `bindsym $mod+d exec fuzzel`

### tofi
- **Pros**: Smallest, pure Wayland (layer-shell), dmenu-style keyboard-first
- **Cons**: No icons, text-only. `tofi-drun` for .desktop files, `tofi-run` for PATH
- **Install**: `sudo apt install tofi`
- **Config**: `~/.config/tofi/config`

### wofi
- **Pros**: CSS themeable (like rofi), supports icons, .desktop by default
- **Cons**: GTK3 dependency (~172KB), power-user oriented
- **Install**: `sudo apt install wofi`
- **Config**: `~/.config/wofi/style.css`

### bemenu ❌ (not recommended for desktop use)
- **Pros**: Lightest, Wayland-native
- **Cons**: PATH executables only — no .desktop files, no Chrome PWAs, no system app entries, no icons
- **Install**: `sudo apt install bemenu`
- **Config**: env vars only (BEMENU_OPTS, etc.)

### rofi ❌ (not recommended on sway)
- **Pros**: Most feature-rich — drun/run/window/ssh modes, powerful theming system, scriptable
- **Cons**: X11-native, requires XWayland on sway. Can have focus, scaling, and rendering issues under XWayland. Largest (800KB+)
- **Install**: `sudo apt install rofi`
- **Config**: `~/.config/rofi/config.rasi`

## Recommendation

**Default**: `fuzzel` — works out of the box, finds everything, looks good.

If you want the absolute smallest (text-only, keyboard-only): `tofi`.

If you want rofi-like CSS theming without the XWayland baggage: `wofi` (GTK3) or stick with `fuzzel` (simpler config).
