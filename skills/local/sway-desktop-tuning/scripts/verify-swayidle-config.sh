#!/bin/bash
# verify-swayidle-config.sh — check swayidle config syntax without entering the idle loop
#
# Usage: verify-swayidle-config.sh [path-to-config]
# Default: ~/.config/swayidle/config
#
# Catches the two common swayidle gotchas:
#   - "Too few parameters" → config has too few args (likely a multi-line issue)
#   - "Unsupported command" → a line that should have been a `resume` was parsed standalone
#   - "Shell expansion error" → wordexp failed (likely an unescaped $ or unbalanced quote)
#   - "Compositor doesn't support idle protocol" → sway not running as this user
#
# Exits 0 on clean parse, 1 on any error.

set -u

CONFIG="${1:-$HOME/.config/swayidle/config}"

if [ ! -f "$CONFIG" ]; then
    echo "✗ config not found: $CONFIG"
    echo "  Create it or pass a different path as the first argument."
    exit 1
fi

echo "checking: $CONFIG"

# Run swayidle in debug mode with a 2s timeout — it will parse, log events,
# then exit when the timeout kills it (we don't want it to actually start
# monitoring idle).
OUTPUT=$(timeout 2 swayidle -C "$CONFIG" -d 2>&1)
RC=$?

# Required signals of a healthy parse:
#   - "Loaded config at <path>" line
#   - one or more "Command: ..." lines (one per timeout/hook)
LOADED=$(echo "$OUTPUT" | grep -c "Loaded config at")
COMMANDS=$(echo "$OUTPUT" | grep -c "Command: ")

# Error patterns from swayidle's main.c
ERRORS=$(echo "$OUTPUT" | grep -iE "Too few parameters|Unsupported command|Shell expansion error|Compositor doesn't support" || true)

echo "  events registered: $COMMANDS"
echo "  config loaded:     $LOADED"

if [ -n "$ERRORS" ]; then
    echo "✗ ERRORS:"
    echo "$ERRORS" | sed 's/^/    /'
    echo
    echo "Full swayidle output:"
    echo "$OUTPUT" | sed 's/^/    /'
    exit 1
fi

if [ "$LOADED" -eq 0 ]; then
    echo "✗ config did not load"
    echo
    echo "Full swayidle output:"
    echo "$OUTPUT" | sed 's/^/    /'
    exit 1
fi

# If we got here, parse was clean. Show the registered commands for a sanity check.
echo "  registered commands:"
echo "$OUTPUT" | grep "Command: " | sed 's/^/    /'
echo "✓ config OK"
exit 0
