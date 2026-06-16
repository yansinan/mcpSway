# Windows MSTSC Black Screen Debug

Session date: 2026-06-13
Server: lamco-rdp-server v1.4.2 on Debian 13 (Trixie), sway 1.10.1
Client: Windows 11 MSTSC → Tailscale → x1tablet

## Symptoms

- Connection establishes (no error code)
- Screen is entirely black
- Monitor controls show it's connected (resolution detected)
- No frames rendered

## Root Cause

**OpenH264 library not installed.** The Windows client negotiates AVC420/AVC444 via EGFX. The server advertises these codecs. But the OpenH264 shared library is absent, so both encoder creation attempts fail:

```
WARN Failed to create AVC444 encoder: OpenH264 library not found
WARN Failed to create AVC420 encoder: OpenH264 library not found
```

## Fallback Behavior

When both AVC encoders fail, the server falls back to RemoteFX:

```
→ Falling back to RemoteFX
→ No H.264 encoder available, using RemoteFX bitmap path (no EGFX surface)
```

However, it **also** keeps replaying cached EGFX init frames:

```
📦 Replaying cached frame for EGFX init (3840x2160, frame 28390)
```

This loop happens indefinitely until the client disconnects. The RemoteFX frames are never actually sent—the server is stuck in EGFX frame-replay mode.

## Fix

```bash
sudo apt install -y libopenh264-8
kill -9 $(pgrep lamco-rdp)
systemctl --user start lamco-rdp-server-tailscale.service
```

After install, verify at next client connection:

```
journalctl --user -u lamco-rdp-server*.service --no-pager | grep "DMA-BUF"
# ✅ EGFX[AVC444,AVC420,RFX]
```

## Debian 13 Package Detail

- Package: `libopenh264-8` (version 2.6.0+dfsg-2)
- SONAME: `libopenh264.so.8` (ABI v8)
- Path: `/usr/lib/x86_64-linux-gnu/libopenh264.so.8 → libopenh264.so.2.6.0`
- The lamco-rdp-server loader (`src/egfx/openh264_compat/loader.rs`) scans all directories in `SEARCH_DIRS` including `/usr/lib/x86_64-linux-gnu`, matches files starting with `libopenh264.so`, sorts by version desc, and tries `dlopen`. Both ABI v7 (.so.7) and v8 (.so.8) are supported via the `AbiGeneration` enum.
- No `ldconfig` registration needed—the loader uses full paths.
- Server log warning says to install `libopenh264-7` (Debian/Ubuntu) but Trixie ships `libopenh264-8`; installing -8 works despite the warning message being stale.

## Deb Confusion Timeline

1. Initially: `sudo apt install -y libopenh264-7` → `Unable to locate package`
2. Searched `apt-cache search openh264` → found `libopenh264-8`
3. Installed `libopenh264-8` → `ldconfig -p` didn't show it (expected—loader uses direct paths)
4. Restarted server → `DMA-BUF ... EGFX[AVC444,AVC420,RFX]` confirmed it loaded

## Config Pitfalls Re-Tested

- `[egfx] enabled = false` → EGFX DVC still registered, DVC processor still active. Confirmed by reading `src/server/mod.rs` lines 606-622: `LamcoGfxFactory` always created, always passed to `.with_gfx_factory(Some(...))`, never wrapped in `if config.egfx.enabled`.
- `[egfx] codec = "avc420" + avc444_enabled = false` → Server starts with "Codec: RemoteFX" but EGFX DVC still present. The codec config affects the RESULT of negotiation, not whether negotiation happens.
- `listen_addr = "127.0.0.1:3389"` → Server still binds to `0.0.0.0:3389`. Config ignored.
- `allowed_resolutions = ["1920x1080"]` in `[display]` → Only limits client-requestable resolutions. Server still captures native display (3840x2160). No downscaling.

## iOS vs Windows Behavior Comparison

| Aspect | iOS (Microsoft RD Client) | Windows (MSTSC) |
|--------|--------------------------|------------------|
| EGFX negotiation | Fails with 0x04 (invalid capability version V10_8+) | Succeeds (sends known version) |
| With OpenH264 | Still fails (same version issue) | Works (AVC420/AVC444) |
| Without OpenH264 | N/A (connection fails before codec) | Black screen (Session OK, no frames) |
| Workaround | Use Jump Desktop (different codec path) | Install OpenH264 |