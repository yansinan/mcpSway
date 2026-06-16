# Sway-session architecture — design notes

## Why a unified entry point

For a sway desktop that needs session persistence, idle detection, and per-monitor power control, the obvious design is one script per concern:

```
~/Scripts/save-session.py
~/Scripts/idle-marker.sh
~/Scripts/screen-control.sh
```

This user's stated preference is the opposite: a single script with subcommands. Reasons from working through this:

1. **One place to audit.** When something misbehaves, you grep one file. With scattered scripts you grep four, then read four, then realize the bug is in the inter-script contract (e.g. the marker file path or socket name).

2. **Subcommand dispatch is cheap.** A 20-line `if/elif` chain is less code than a second script's shebang + imports + arg parsing.

3. **One shebang, one set of imports.** If you switch languages or update a dependency, one edit, not N.

4. **Subcommands are additive.** Adding `--lock` for swaylock is one new function and one new `elif`. Adding a third helper script is a new file plus deciding where it goes, what permissions, how to invoke from swayidle config.

The cost is that the file gets long (~300 lines in this user's setup). Mitigations:
- Clear section headers (`# ── Helpers ──`, `# ── Save / Restore ──`)
- One responsibility per function
- A docstring at the top listing every subcommand

## When to split (don't be dogmatic)

Split into a new script if the new function is genuinely orthogonal:
- Different language ecosystem (e.g. a C program for performance)
- Different lifecycle (e.g. a one-shot setup script that runs once)
- Different invocation context (e.g. a script run from udev, not swayidle)
- True independence (no shared state, no shared config)

For everything else, extend the unified entry point.

## The marker-file IPC pattern

Why a marker file and not, say, a Unix socket or dbus signal:

- **vs Unix socket:** A socket needs the daemon to bind, the short-lived
  process to connect, and a protocol (newline-delimited JSON? length-prefixed?
  just write a byte?). For a single boolean signal this is huge overkill.
- **vs dbus:** Requires a service file under `~/.local/share/dbus-1/services/`,
  a stable bus name, dbus-send invocations, and lifecycle management (what if
  the daemon restarts mid-event?). For "set a flag" this is heavy.
- **vs sway IPC polling:** sway doesn't expose "is user idle" via
  `swaymsg -t get_*`. The idle state is a wayland-protocol concept
  (`ext-idle-notify-v1`) that only the idle manager (swayidle) sees directly.
  Polling a wayland protocol from Python is hundreds of lines of code.
- **vs signal (SIGUSR1 to daemon):** Works, but requires the short-lived
  process to know the daemon's PID, and requires the daemon to set up
  signal handlers. Marker file is simpler for "set/clear" semantics.

The trade-off: marker file is observable by any process on the system
(technically, by any process running as the same user — `XDG_RUNTIME_DIR`
is mode 700). For a "is the user idle" signal, this is fine — the signal
itself is non-sensitive (we're not putting credentials in it). For a
secret, don't use a marker file.

## Why $XDG_RUNTIME_DIR and not /tmp or ~/.cache

- `/tmp` is wiped on reboot. The marker correctly says "no idle state yet"
  on a fresh boot. ✓
- `~/.cache` survives reboot. The marker would say "user is idle" after
  a clean restart, until swayidle's first timeout fires. ✗
- `$XDG_RUNTIME_DIR` (default `/run/user/$UID`) is the right place for
  per-user, per-session, ephemeral runtime state. systemd and most desktop
  specs route here.

## 60s vs other idle thresholds

The 60s threshold for "user is idle" (skip save) is shorter than the
3600s threshold for "screen off" (60 minutes) on purpose:

- A user walking to get coffee → 60s triggers → 5-min save skips
- A user leaving for a meeting → 3600s triggers → screen turns off
- A user coming back from coffee (within 5 min) → 60s resume → save resumes
- A user coming back from meeting → 3600s resume → screen turns back on

If we used a single threshold (say 60 min for both), then between
60s and 60 min, the user is "kind of idle" but we're still saving.
That's the wasted-state case we wanted to avoid. Two thresholds
give four useful states: active, briefly-idle, long-idle, gone.

## Subcommand names: verb-first, hyphen-separated

- `--save` / `--restore` (action)
- `--daemon` (mode)
- `--mark-idle` / `--mark-active` (action + state)
- `--screen-off` / `--screen-on` (action + state)

This makes grepping for the action easy (`grep "mark-"`) and the
state reads naturally when combined with swayidle's
`timeout N action-stamp resume action-unstamp` syntax.

Avoid `--idle_on` (underscore) — looks like a different language style
and breaks the verb-first pattern.

## Testing without waiting

`pkill -USR1 swayidle` triggers swayidle's SIGUSR1 handler, which
"enter[s] idle state immediately" per the man page. All your timeout
events fire without waiting. Use this to verify:

1. Your scripts are wired correctly
2. The commands actually do what you expect
3. Resume events work (type something to trigger user activity, or
   `pkill -TERM swayidle` which runs all pending resumes on exit)

Without this, you'd be waiting the full 60s or 3600s to test each
event. Not practical for iteration.
