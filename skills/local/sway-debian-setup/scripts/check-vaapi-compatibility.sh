#!/usr/bin/env bash
# Check VaapiVideoDecoder compatibility for Chromium on sway/Wayland.
# Usage: bash check-vaapi-compatibility.sh
# Exit 0 = VaapiVideoDecoder should work.
# Exit 1 = VaapiVideoDecoder will cause black screen (Ivy Bridge / pre-Gen9 without iHD).

set -euo pipefail

echo "=== GPU ==="
if ! lspci -nn 2>/dev/null | grep -qi "VGA\|3D\|Display"; then
    echo "FAIL: lspci not available or no GPU found"
    exit 1
fi
GPU_LINE=$(lspci -nn | grep -iE "VGA|3D|Display" | head -1)
echo "  $GPU_LINE"

GPU_DEVICE=$(echo "$GPU_LINE" | grep -oP '\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]' | tail -1)
echo "  Device ID: $GPU_DEVICE"

echo ""
echo "=== VA-API Driver ==="
if ! command -v vainfo &>/dev/null; then
    echo "FAIL: vainfo not installed (sudo apt install vainfo)"
    exit 1
fi

IHD_FAIL=$(vainfo 2>&1 | grep -c "iHD.*init failed" || true)
I965_OK=$(vainfo 2>&1 | grep -c "i965.*returns 0" || true)
DRIVER_LINE=$(vainfo 2>&1 | grep "Driver version" || echo "")

echo "  iHD driver init failed:  $IHD_FAIL"
echo "  i965 driver working:     $I965_OK"
echo "  Active driver:           $DRIVER_LINE"

echo ""
echo "=== VP9 Hardware Decode ==="
VP9_SUPPORT=$(vainfo 2>&1 | grep -c "VP9" || true)
H264_SUPPORT=$(vainfo 2>&1 | grep -c "H264" || true)
echo "  VP9 supported:  $([ "$VP9_SUPPORT" -gt 0 ] && echo YES || echo NO)"
echo "  H.264 supported: $([ "$H264_SUPPORT" -gt 0 ] && echo YES || echo NO)"

echo ""
echo "=== Assessment ==="

if [ "$IHD_FAIL" -gt 0 ] && [ "$I965_OK" -gt 0 ]; then
    echo "  ⚠  iHD driver failed, falling back to i965."
    echo "  ⚠  Chromium 116+ dropped i965 support entirely."
    echo "  ✗  VaapiVideoDecoder will cause black screen — no usable VA-API backend."
    echo "  →  Fix: disable accelerated decode, install h264ify, or switch to Chrome."
    exit 1
fi

if [ "$IHD_FAIL" -gt 0 ]; then
    echo "  ✗  iHD driver failed to initialize. No VA-API backend available."
    echo "  →  Fix: install intel-media-va-driver or disable VaapiVideoDecoder."
    exit 1
fi

if [ "$VP9_SUPPORT" -eq 0 ]; then
    echo "  ⚠  VP9 not supported in hardware."
    echo "  ⚠  With VaapiVideoDecoder, YouTube may black screen."
    echo "  →  Consider h264ify extension or --disable-accelerated-video-decode."
fi

echo "  ✓  VA-API should work with Chromium."
exit 0
