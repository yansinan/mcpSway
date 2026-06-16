# Tailscale RDP Debug Session Notes

## Environment
- Host: Debian 13 (trixie), kernel 6.12.90+deb13.1
- Compositor: sway 1.10.1 / wlroots 0.18.2
- Server: lamco-rdp-server v1.4.2 (DEB package)
- Network: Tailscale 1.98.4, node x1tablet (100.66.66.249)
- Clients tested: iOS iPad (100.108.139.125), iPhone (100.66.66.206)

## Issue: iOS Error 0x04 (Connection interrupted)

### Server log pattern
```
ERROR lamco_rdp_server::server: Connection error from 100.x.x.x:port after Xs:
client loop failure: X224 input error:
[<ironrdp_egfx::server::GraphicsPipelineServer as ironrdp_dvc::DvcProcessor>::process::{{closure}}]
decode error:
[<ironrdp_egfx::pdu::cmd::CapabilityVersion as core::convert::TryFrom<u32>>::try_from]
invalid `version`: invalid capability version
```

### Root cause

1. Microsoft RDP client on iOS sends an EGFX capability version (likely V10_8+) that the bundled IronRDP (only supports up to V10_7 = 0xa_0701) doesn't recognize.

2. The `[egfx] enabled = false` config flag does NOT prevent EGFX DVC registration — it's never checked in `src/server/mod.rs`. The `LamcoGfxFactory` is always created and always registered via `.with_gfx_factory(Some(Box::new(gfx_factory)))`.

3. CapabilityVersion constants defined in IronRDP (`crates/ironrdp-egfx/src/pdu/cmd.rs`):
   - V8 = 0x8_0004
   - V8_1 = 0x8_0105
   - V10 = 0xa_0002
   - V10_1 = 0xa_0100
   - V10_2 = 0xa_0200
   - V10_3 = 0xa_0301
   - V10_4 = 0xa_0400
   - V10_5 = 0xa_0502
   - V10_6 = 0xa_0600
   - V10_6_ERR = 0xa_0601
   - V10_7 = 0xa_0701

### Fix needed

In `src/server/mod.rs`, wrap the `LamcoGfxFactory` creation around a `config.egfx.enabled` check:

```rust
if config.egfx.enabled {
    let gfx_factory = LamcoGfxFactory::with_config(...);
    // ... build with .with_gfx_factory(Some(Box::new(gfx_factory)))
} else {
    // ... build with .with_gfx_factory(None)
}
```

### Workarounds tested

| Approach | Result |
|----------|--------|
| Set `[egfx] enabled = false` | No effect — DVC still registered |
| Remove entire `[egfx]` section | Defaults to `enabled: true` — EGFX still active |
| Set `codec = "avc420"` | Doesn't help — capability version check happens before codec negotiation |
| Set `[hardware_encoding] enabled = false` | Doesn't affect EGFX DVC |
| iOS→Windows→x1tablet chain | Black screen — EGFX still active on server |

### Working options
- Use Jump Desktop (iOS) — doesn't negotiate EGFX
- Patch and recompile lamco-rdp-server
- Upgrade IronRDP to support newer CapabilityVersion
