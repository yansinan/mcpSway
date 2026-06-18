# iOS RDP Client EGFX Debugging Session

## Environment
- **Server:** x1tablet, Debian 13, Sway 1.10.1, lamco-rdp-server v1.4.2 (DEB)
- **Client:** iPad Pro 10.5" (100.108.139.125), iPhone 17 Pro (100.66.66.206)
- **Network:** Tailscale, binding via `tailscale serve --tcp 3389` then direct binding
- **TLS:** Self-signed cert → Tailscale cert (`tailscale cert x1tablet.tail2e6efb.ts.net`)

## Error Progression

### 1. Error 0x204 (Can't connect)
- **Symptom:** iOS RDP client "The remote computer is not available"
- **Log:** No connection attempts reached the server
- **Cause:** Self-signed TLS certificate rejected by iOS client
- **Fix:** Replaced with `tailscale cert` and connected via hostname `x1tablet.tail2e6efb.ts.net`

### 2. Error 0x04 (Connection interrupted) — EGFX version mismatch
- **Symptom:** TLS handshake succeeds, connection drops after 3-7 seconds
- **Log:**
  ```
  Connection error from 100.66.66.206:63939 after 3.0s:
    client loop failure: X224 input error:
    [<ironrdp_egfx::server::GraphicsPipelineServer as ironrdp_dvc::DvcProcessor>::process::{{closure}}]
    decode error:
    [<ironrdp_egfx::pdu::cmd::CapabilityVersion as core::convert::TryFrom<u32>>::try_from]
    invalid `version`: invalid capability version
  ```
- **Root cause:** `LamcoGfxFactory` always registered regardless of `[egfx] enabled = false` config

## Code Discovery Path

1. Found that `ss -tlnp` shows `0.0.0.0:3389` regardless of `listen_addr` config value
2. Checked journal for connection errors → found EGFX capability version error
3. Tried `[egfx] enabled = false` → no effect, EGFX handler still logged
4. Tried removing entire `[egfx]` section → EGFX handler still registered
5. Searched server source (`src/server/mod.rs`):
   - Found `gfx_factory` creation at ~line 614
   - Found `.with_gfx_factory(Some(Box::new(gfx_factory)))` at lines 870, 894
   - **No `if config.egfx.enabled` check exists anywhere**
6. Searched IronRDP `CapabilityVersion` definition:
   - Newtype `pub struct CapabilityVersion(pub u32)`
   - Known versions: V8(0x8_0004) through V10_7(0xa_0701)
   - iOS client sends a version not in known list

## Workarounds

1. Use Jump Desktop (iOS) instead of Microsoft Remote Desktop
2. Patch and build from source with `if config.egfx.enabled { ... }` guard
3. Wait for upstream fix

## Commands Used

```bash
# Check service status
systemctl --user status lamco-rdp-server-tailscale.service
journalctl --user -u lamco-rdp-server-tailscale.service -n 50

# Verify port
ss -tlnp | grep 3389

# Generate Tailscale cert
tailscale cert x1tablet.tail2e6efb.ts.net

# Set up Tailscale TCP serve
tailscale serve --tcp=3389 off
tailscale serve --bg --tcp 3389 tcp://127.0.0.1:3390
tailscale serve status

# Check Tailscale connectivity
tailscale ping 100.108.139.125

# FG-ONLY: Check Tailscale peers
tailscale status --self=false --json

# Kill stubborn process
kill -9 <PID>

# Source navigation
curl -sL "https://raw.githubusercontent.com/lamco-admin/lamco-rdp-server/main/src/server/mod.rs" | grep -n "gfx_factory\|with_gfx\|egfx"

# Check IronRDP CapabilityVersion
curl -sL "https://raw.githubusercontent.com/Devolutions/IronRDP/master/crates/ironrdp-egfx/src/pdu/cmd.rs" | grep "pub const V"
```
