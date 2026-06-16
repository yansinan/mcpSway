# iOS EGFX CapabilityVersion Debug — 2026-06-13

## Environment
- **Server**: x1tablet, Debian 13 (trixie), sway 1.10.1 (wlroots)
- **Server IP**: 100.66.66.249 (Tailscale)
- **Clients**: iPad Pro 10.5" (100.108.139.125), iPhone 17 Pro (100.66.66.206)
- **RDP Server**: lamco-rdp-server v1.4.2 (DEB install)
- **RDP Client**: Microsoft Remote Desktop (iOS)

## Observed Errors

### Error 0x204 ("Cannot connect to remote PC")
- Occurred when connecting via IP address (100.66.66.249) with self-signed TLS cert
- Resolved by switching to `tailscale cert` (Let's Encrypt) + connecting via MagicDNS hostname (`x1tablet.tail2e6efb.ts.net`)

### Error 0x04 ("The connection was interrupted")
- Occurred after switching to Tailscale cert — connection established (TLS OK) but dropped after ~3s
- Server log showed EGFX capability negotiation failure
- Exact error:
  ```
  ERROR: Connection error from 100.66.66.206:63930 after 3.3s: client loop failure:
  X224 input error: [<ironrdp_egfx::server::GraphicsPipelineServer as ironrdp_dvc::DvcProcessor>::process::{{closure}}]
  decode error: [<ironrdp_egfx::pdu::cmd::CapabilityVersion as core::convert::TryFrom<u32>>::try_from]
  invalid `version`: invalid capability version
  ```

## Root Cause

The Microsoft Remote Desktop client on iOS sends a newer EGFX CapabilityVersion (likely a <u32> value not in IronRDP's CapabilityVersion enum). lamco-rdp-server v1.4.2 bundles an IronRDP version that only knows up to a certain version.

## What DIDN'T Work

1. `[egfx] enabled = false`: The server still registers the EGFX DVC (Dynamic Virtual Channel) handler. When the client opens the EGFX channel, the server tries to parse the client's CapabilityVersion packet → same error.

2. Setting `listen_addr = "100.66.66.249:3389"`: lamco-rdp-server ignores `listen_addr` entirely, always binds `0.0.0.0:PORT`.

3. `tailscale serve --tcp 3389` with RDP server on same port: Port conflict because the server binds to `0.0.0.0`.

## Fix

Force a compatible graphics pipeline configuration. The key is not `egfx.enabled` but the codec selection:

```toml
[egfx]
enabled = true
codec = "avc420"
avc444_enabled = false
zgfx_compression = "never"
```

This causes the server to advertise **RemoteFX** instead of EGFX. RemoteFX doesn't use the EGFX DVC channel, so the CapabilityVersion negotiation path is never hit.

Verified by server log:
```
INFO lamco_rdp_server::server:   Codec: RemoteFX
```

## Test Sequence

1. `sudo dpkg -i lamco-rdp-server_*_amd64.deb` + `sudo apt install -f -y`
2. `tailscale cert x1tablet.tail2e6efb.ts.net`
3. Config: write to `~/.config/lamco-rdp-server/config.toml`
4. Custom systemd user service (D-Bus service mode has over-strict hardening)
5. `systemctl --user start lamco-rdp-server.service`
6. Test local: `echo | nc -w 2 127.0.0.1 3389` should return 0
7. Connect from iOS: use MagicDNS hostname, NOT IP

## Key Debugging Commands

```bash
# Check if server is listening
ss -tlnp | grep 3389

# Check server logs for connection errors
journalctl --user -u lamco-rdp-server.service --no-pager -n 80 | grep -iE "ERROR|bind|client|egfx|xt224"

# Verify codec mode
journalctl --user -u lamco-rdp-server.service --no-pager | grep "Codec:"

# Force stop (server ignores SIGTERM, needs SIGKILL)
kill -9 $(pgrep lamco-rdp-serve)

# Tailscale cert
tailscale cert <hostname>.tailXXXXX.ts.net
```

## Tailscale Serve vs Direct

For lamco-rdp-server, **direct exposure** (Option A) works best because:
- The server always binds `0.0.0.0`, so it can't share port 3389 with tailscale serve
- Direct access via Tailscale IP is just as secure (only tailnet peers reach it)
- Fewer moving parts

Option B (tailscale serve with non-default port) adds unnecessary complexity.
