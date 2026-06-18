# Native Wayland Audio Management GUIs

Volume control, routing, and sound-effect tools that run natively on Wayland (no XWayland dependency).

## Volume Control

| Tool | Stack | Install | Per-App? | Routing? | Notes |
|---|---|---|---|---|---|
| **pwvucontrol** | GTK4+Rust | `flatpak install com.saivert.pwvucontrol` | ✅ | ✅ Sink switch | Recommended daily-driver vol control. Verified on Flathub. |
| **Simple Wireplumber GUI** | GTK4 | `flatpak install io.github.dyegoaurelio.simple-wireplumber-gui` | ❌ View only | ❌ | Rename devices, view properties. Lightweight. |
| **wiremix** | Rust TUI | `cargo install wiremix` | ✅ | ✅ | 940★, active (v0.11.0). Per-app vol + routing + device config. Runs in foot = Wayland native. |
| **EasyEffects** | GTK4 | `sudo apt install easyeffects` | Per-stream with filters | ❌ | Equalizer, compressor, limiter, auto volume. Not a manager — an effects processor. |
| **ncpamixer** | NCURSES TUI | `sudo apt install ncpamixer` | ✅ | ✅ | Classic TUI, runs in foot. Simpler than wiremix. |

## Patchbay / Audio Routing

| Tool | Stack | Install | Wayland? | Notes |
|---|---|---|---|---|
| **qpwgraph** | Qt | `sudo apt install qpwgraph` | ⚠️ `QT_QPA_PLATFORM=wayland` | Qt-based PipeWire graph patchbay. Heavy dep (Qt5/Qt6). |
| **Helvum** | GTK3 | `flatpak install org.pipewire.Helvum` | ❌ XWayland | PipeWire patchbay inspired by JACK catia. |

## Recommendation Flow

```
Just need volume control?            → pwvucontrol
Need per-app volume + routing?       → wiremix or pwvucontrol
Want effects (EQ/compressor)?        → EasyEffects
Need full JACK-style patchbay?       → qpwgraph with QT_QPA_PLATFORM=wayland
Want keyboard-only + lightweight?    → wiremix or ncpamixer in foot
```
