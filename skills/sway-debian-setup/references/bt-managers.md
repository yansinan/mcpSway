# Bluetooth Managers on Sway/Wayland

## Comparison

| Tool | UI Type | Wayland? | Install | Features | Recommendation |
|---|---|---|---|---|---|
| **overskride** | GUI (GTK4+libadwaita, Rust) | ✅ Native | `cargo install overskride` (need libgtk-4-dev, libadwaita-1-dev) | Pair, connect, browse, send files. 887★, active. | **Best native Wayland GUI** |
| **bluetuith** | TUI | ✅ Native (runs in foot) | Download binary from releases | Pair, connect, TUI keyboard-driven. Go-based. | Lightest option, keyboard-friendly |
| **blueman** | GUI (GTK3) | ❌ XWayland | `sudo apt install blueman` | Full featured: pair, send files, audio, network. Includes applet. | Most mature. **Easiest install.** Works great even under XWayland. |
| **bluedevil** | GUI (Qt/KDE) | ⚠️ KDE-only | `sudo apt install bluedevil` | KDE Bluetooth stack. Heavy deps. | Don't install on non-KDE. |
| **gnome-bluetooth** | GUI (GTK/GNOME) | ✅ Native | Part of gnome-control-center | GNOME Settings Bluetooth panel. Heavy deps. | Don't install standalone on sway. |

## Recommendation Flow

```
Want the most reliable, quick install?                  → blueman (apt, XWayland)
Want native Wayland GUI?                                 → overskride (cargo, GTK4)
Want keyboard-only, minimal deps?                        → bluetuith (TUI, foot)
```

## Prerequisites

All BT managers need the BlueZ stack running:

```bash
sudo systemctl enable --now bluetooth
bluetoothctl show     # verify adapter present
```

## Install Notes

### overskride (from source)

```bash
sudo apt install -y libgtk-4-dev libadwaita-1-dev
cargo install overskride
```

### bluetuith (binary)

```bash
# Grab the latest release from https://github.com/bluetuith-org/bluetuith/releases
# e.g. for amd64 Linux:
curl -LO https://github.com/bluetuith-org/bluetuith/releases/latest/download/bluetuith_linux_amd64.tar.gz
tar xzf bluetuith_linux_amd64.tar.gz
sudo mv bluetuith /usr/local/bin/
```

### blueman (Debian)

```bash
sudo apt install -y blueman
# Applet auto-starts via /etc/xdg/autostart/blueman.desktop
```
