# Gnome-shell / Mutter DisplayConfig DBus API

Used for cross-compositor debugging: querying and applying monitor configurations when sway/KWin also fail to drive an external display.

## Service and path

```
org.gnome.Mutter.DisplayConfig
/org/gnome/Mutter/DisplayConfig
```

## GetCurrentState

```bash
dbus-send --session --dest=org.gnome.Mutter.DisplayConfig \
  --type=method_call --print-reply \
  /org/gnome/Mutter/DisplayConfig \
  org.gnome.Mutter.DisplayConfig.GetCurrentState
```

Returns: `(u serial, a(...) physical_monitors, a(...) logical_monitors, a{sv} properties)`

The key field in the logical monitor struct is the **boolean** at position 4: `true` = enabled, `false` = disabled. If mutter reports the DP output as disabled, it means the modeset failed silently.

## ApplyMonitorsConfig

Type signature: `(uua(iiduba(ssa{sv}))a{sv})`
```
u = serial (from GetCurrentState)
u = method (1=verify, 2=temporary, 3=persistent)
a(iiduba(ssa{sv})) = array of logical monitors
  i = x position
  i = y position
  d = scale
  u = transform (0=normal, 1=90° ccw, 2=180°, 3=90° cw)
  b = enabled (true/false)
  a(ssa{sv}) = outputs [(connector, mode_string, properties_dict), ...]
a{sv} = top-level properties dict (empty if unused)
```

### Python example

```python
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
proxy = Gio.DBusProxy.new_sync(bus, 0, None,
    "org.gnome.Mutter.DisplayConfig",
    "/org/gnome/Mutter/DisplayConfig",
    "org.gnome.Mutter.DisplayConfig", None)

result = proxy.GetCurrentState()
serial = result[0]

# Enable DP-2 alongside eDP-1
logical_monitors = GLib.Variant('a(iiduba(ssa{sv}))', [
    (0, 0, 2.0, 0, True, [
        ('eDP-1', '3000x2000@59.999', {}),
    ]),
    (1500, 0, 1.0, 0, True, [
        ('DP-2', '3840x2160@59.997', {}),
    ]),
])

try:
    proxy.call_sync('ApplyMonitorsConfig',
        GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})',
            (serial, 2, logical_monitors, {})),
        Gio.DBusCallFlags.NONE, -1, None)
    print("Applied")
except GLib.GError as e:
    print(f"Failed: {e.message}")
```

### Common errors

| Error | Meaning |
|-------|---------|
| `Invalid args: Invalid mode` | The mode string doesn't match the monitors capabilities |
| `Logical monitors not adjacent` | The two monitors don't touch edge-to-edge |
| `Logical monitors overlap` | Monitors overlap in coordinate space |

The "not adjacent" error can also mask a **silent modeset failure** — mutter tries the atomic commit, the kernel fails (no signal), and mutter reports the error as an adjacency check failure.
