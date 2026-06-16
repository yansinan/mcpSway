# lamco-rdp-server config for sway/wlroots

Minimal tested config for Sway on Debian 13 with Tailscale.

```toml
[server]
listen_addr = "127.0.0.1:3389"
max_connections = 5
use_portals = true

[security]
cert_path = "/home/dr/x1tablet.tail2e6efb.ts.net.crt"
key_path = "/home/dr/x1tablet.tail2e6efb.ts.net.key"
enable_nla = false
auth_method = "none"

[video]
target_fps = 30
cursor_mode = "metadata"

[audio]
enabled = true
codec = "auto"

[capture]
protocol = "auto"
allow_fallback = true

[input]
use_libei = true
keyboard_layout = "auto"

[clipboard]
enabled = true

[multimon]
enabled = true
max_monitors = 2

[performance.adaptive_fps]
enabled = true
min_fps = 5
max_fps = 60

[performance.latency]
mode = "balanced"

[logging]
level = "info"

[damage_tracking]
enabled = true
method = "hybrid"

[hardware_encoding]
enabled = true
vaapi_device = "/dev/dri/renderD128"
fallback_to_software = true

[display]
allow_resize = true
dpi_aware = true
```

## Notes

- `listen_addr` is effectively ignored — server always binds to `0.0.0.0:3389`
- `[egfx] enabled = false` does NOT prevent EGFX DVC registration — see main SKILL.md
- If using i915 DP-MST issues, set `[hardware_encoding] enabled = false`
