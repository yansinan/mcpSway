#!/usr/bin/env python3
"""
sway-session 统一入口 (portable skeleton)
=========================================

SINGLE SCRIPT for: session save/restore, idle detection, per-monitor DPMS,
any future sway-side action. Add new functionality as a new subcommand
rather than spawning more scripts in ~/Scripts/.

This file is a template. The ONLY system-specific value is
``EXTERNAL_OUTPUT`` at the top of the config block. Find your monitors'
make/model/serial triple with:

    swaymsg -t get_outputs | jq '.[] | select(.type=="output") | {name, make, model, serial}'

Architecture:
    - The script's main loop is a daemon that ticks every INTERVAL seconds
      and conditionally saves the session
    - swayidle timeout/resume events invoke short-lived instances of this
      script with --mark-idle / --mark-active / --screen-off / --screen-on
    - Idle state is shared between the long-running daemon and the
      short-lived event handlers via a marker file in $XDG_RUNTIME_DIR
    - Subcommand dispatch is a single if/elif chain in main()

Subcommands (in this order in main()):
    (no arg) | --start      startup: restore + start daemon
    --save                  manual save
    --restore               manual restore
    --daemon                just the daemon loop
    --mark-idle             swayidle 60s timeout: create idle marker
    --mark-active           swayidle 60s resume: delete idle marker
    --screen-off            swayidle 3600s timeout: dpms off external
    --screen-on             swayidle 3600s resume: dpms on external

Wired from ~/.config/swayidle/config (see templates/swayidle-config):
    timeout 60   ~/Scripts/sway-session --mark-idle   resume ~/Scripts/sway-session --mark-active
    timeout 3600 ~/Scripts/sway-session --screen-off  resume ~/Scripts/sway-session --screen-on

Wired from ~/.config/sway/config:
    exec ~/Scripts/sway-session
    exec swayidle -w
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────

SAVE_FILE = Path.home() / ".config" / "sway" / "sway-session.json"
INTERVAL = 300  # seconds between save ticks (5 min)

# Idle marker lives in XDG_RUNTIME_DIR (vanished on reboot — correct)
XDG_RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
IDLE_MARKER = Path(XDG_RUNTIME) / "sway-user-idle"

# ★ The one system-specific value: fill in your external monitor's
#   make / model / serial triple here. NEVER use DP-N — those change
#   every boot with USB-C docks. Get the triple with:
#     swaymsg -t get_outputs | jq -r '.[] | select(.type=="output") | "\(.make) \(.model) \(.serial)"'
EXTERNAL_OUTPUT = "Make Model 0xSERIAL"  # TODO: replace with your real triple


# ── Helpers ───────────────────────────────────────────────────────────────

def find_swaysock():
    """Locate the current sway IPC socket (PID changes on every restart)."""
    socks = sorted(glob.glob("/run/user/*/sway-ipc.*.sock"))
    if socks:
        os.environ["SWAYSOCK"] = socks[-1]
        return socks[-1]
    return None


def swaymsg(args, raw=False):
    """Run swaymsg, return parsed JSON (raw=True) or stripped stdout."""
    find_swaysock()
    cmd = ["swaymsg", "-t", args]
    if raw:
        cmd.append("--raw")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    if raw:
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return None
    return r.stdout.strip()


# ── Save / Restore (TODO: fill in your session capture logic) ───────────

def save():
    """Capture current sway layout tree and write to SAVE_FILE."""
    # TODO: walk swaymsg -t get_tree JSON, extract per-workspace info,
    #       write to SAVE_FILE. See the user's full implementation for
    #       a chrome/foot-aware app extraction pattern.
    raise NotImplementedError("fill in save() for your setup")


def restore():
    """Read SAVE_FILE and replay the saved layout."""
    if not SAVE_FILE.exists():
        print(f"[session] no save file, skipping")
        return False
    # TODO: read SAVE_FILE, re-launch apps in their workspaces.
    #       See the user's full implementation for a chrome/foot-aware
    #       restore pattern.
    raise NotImplementedError("fill in restore() for your setup")


# ── Daemon (with idle skip) ──────────────────────────────────────────────

def is_user_idle() -> bool:
    """True if swayidle has marked the user idle (60s no activity)."""
    return IDLE_MARKER.exists()


def daemon():
    """Tick every INTERVAL seconds, save unless user is idle."""
    print(f"[session] daemon: save every {INTERVAL}s, skip when idle")
    save()
    while True:
        try:
            time.sleep(INTERVAL)
            if is_user_idle():
                print(f"[session] skip (idle, marker={IDLE_MARKER})")
                continue
            save()
        except KeyboardInterrupt:
            print("\n[session] daemon exiting")
            break


# ── Swayidle event subcommands ───────────────────────────────────────────

def mark_idle():
    """swayidle 60s timeout: create idle marker so daemon skips save."""
    try:
        IDLE_MARKER.touch()
        print(f"[session] idle marker created: {IDLE_MARKER}")
    except OSError as e:
        print(f"[session] mark_idle failed: {e}", file=sys.stderr)
        sys.exit(1)


def mark_active():
    """swayidle 60s resume: delete idle marker so daemon resumes saving."""
    try:
        IDLE_MARKER.unlink(missing_ok=True)
        print(f"[session] idle marker removed: {IDLE_MARKER}")
    except OSError as e:
        print(f"[session] mark_active failed: {e}", file=sys.stderr)
        sys.exit(1)


def _swaymsg_output_dpms(state: str):
    """Set DPMS for the external monitor. state is 'on' or 'off'."""
    find_swaysock()
    cmd = f'output "{EXTERNAL_OUTPUT}" dpms {state}'
    r = subprocess.run(["swaymsg", cmd], capture_output=True, text=True, timeout=8)
    if r.returncode != 0:
        print(f"[session] swaymsg failed: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    print(f"[session] external dpms {state}: {EXTERNAL_OUTPUT}")


def screen_off():
    """swayidle 3600s timeout: turn off the external monitor."""
    _swaymsg_output_dpms("off")


def screen_on():
    """swayidle 3600s resume: turn the external monitor back on."""
    _swaymsg_output_dpms("on")


# ── Entry point ──────────────────────────────────────────────────────────

import glob  # placed here so the helpers above can reference it lazily

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    # Every subcommand (including short-lived event handlers) needs a
    # live sway socket. Bail out early if not.
    if not find_swaysock():
        print("[session] sway IPC unavailable, exiting")
        sys.exit(1)

    if mode == "--save":
        save()
    elif mode == "--restore":
        restore()
    elif mode == "--daemon":
        daemon()
    elif mode == "--mark-idle":
        mark_idle()
    elif mode == "--mark-active":
        mark_active()
    elif mode == "--screen-off":
        screen_off()
    elif mode == "--screen-on":
        screen_on()
    elif mode in ("", "--start"):
        # default startup: restore layout, then enter daemon
        restore()
        daemon()
    else:
        print(f"[session] unknown arg: {mode}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
