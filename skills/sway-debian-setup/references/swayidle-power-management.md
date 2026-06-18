# Swayidle & Power Management on Sway

Trigger: configuring auto screen lock, blanking, suspend/hibernate, or coordinating
an idle state with other tools (e.g. session save, media pause, BT disconnect).

## What swayidle actually does

swayidle is **a trigger, not an executor**. It listens to the Wayland
`ext-idle-notify-v1` protocol and runs shell commands on idle/active transitions.
It does **not** itself suspend the system — `systemctl suspend` (or
`systemctl hibernate`) just hands off to systemd-logind, which goes through the
kernel's ACPI interface. Knowing this distinction avoids confusion when
debugging "why didn't my laptop sleep" (usually logind or kernel, not swayidle).

Compile-time requirement: `before-sleep`, `after-resume`, `lock`, `unlock`,
`idlehint` events all require swayidle built with systemd OR elogind support.
On Debian 13, the package is built with systemd by default — verify with
`ldd $(which swayidle) | grep -E "systemd|elogind"`.

## Six event types

| Event | Trigger | Needs systemd/elogind? |
|---|---|---|
| `timeout N <cmd> [resume <cmd>]` | N seconds idle / user resumes | no |
| `before-sleep <cmd>` | logind `PrepareForSleep(true)` | yes |
| `after-resume <cmd>` | logind `PrepareForSleep(false)` | yes |
| `lock <cmd>` | logind `Lock` signal | yes (no systemd ⇒ disabled) |
| `unlock <cmd>` | logind `Unlock` signal | yes |
| `idlehint N` | After N seconds idle, set logind `IdleHint=true` | yes |

`timeout` is the only event that works without systemd. `idlehint` is the bridge
to logind's `IdleAction=ignore|poweroff|reboot|halt|kexec|suspend|hibernate|hybrid-sleep|suspend-then-hibernate` — configured in `/etc/systemd/logind.conf`.

## ⚠ Three critical parsing pitfalls

These bite everyone once. Verify after writing your config with
`swayidle -C ~/.config/swayidle/config -d`:

### 1. `parse_command` only keeps the FIRST token

swayidle's `parse_command` (in `main.c`) does `return strdup(argv[0])`.
Then `cmd_exec` runs `sh -c <param>`. So `sh -c "touch /tmp/marker"` is stored as
just `"sh"` — the `-c` and the command are **lost** at parse time.

**Symptom**: timeout fires, log says "Cmd exec sh", you get a stray shell
window or nothing happens.

**Fix**: anything with arguments must be a single-token script path:

```ini
# WRONG — command gets truncated to "sh"
timeout 60 sh -c "touch /tmp/marker"

# WRONG — swaylock is one token, "-f -c 000000" is dropped
timeout 300 'swaylock -f -c 000000'

# RIGHT — wrap as a script
timeout 60 ~/Scripts/sway-idle-on.sh
timeout 300 ~/Scripts/sway-lock.sh
```

### 2. config is parsed line-by-line, NO line continuation

Bash's `\` line-continuation **does not work** in swayidle config. Each line is
parsed independently. `timeout N cmd` and `resume cmd` MUST be on the **same
line**:

```ini
# WRONG — second line is parsed as a standalone "resume" event, fails
timeout 60 ~/Scripts/sway-idle-on.sh
     resume ~/Scripts/sway-idle-off.sh

# RIGHT — same line
timeout 60 ~/Scripts/sway-idle-on.sh resume ~/Scripts/sway-idle-off.sh
```

The man page example shows `\` continuation because it's a *shell* command
example (CLI args). Inside a config file, ignore that pattern.

### 3. `$XDG_RUNTIME_DIR` may not be expanded in inline commands

Even with `wordexp`, the first-token truncation (pitfall 1) usually masks
variable expansion. If you do manage to keep multi-token commands (via a
script), test that env vars are visible to the script. In practice, prefer
absolute paths in helper scripts and only rely on env vars in well-tested
shims.

## Bridge pattern: swayidle ↔ user scripts via marker file

When multiple long-running tools need to react to the same idle state
(e.g. sway-session.py should skip saving when user is away), use a **marker
file in `$XDG_RUNTIME_DIR/`** as the bridge — much simpler than DBus or
wayland IPC:

```
swayidle (60s idle)   ── touch ──▶  $XDG_RUNTIME_DIR/sway-user-idle
                                       │
                                       │ exists() check on every save tick
                                       ▼
sway-session.py daemon ─────────────▶ skip save
```

Why this works:
- `XDG_RUNTIME_DIR` is per-user, wiped on reboot (correct semantics for
  "current session idle state")
- Two independent processes, no DBus plumbing
- Race-free enough: at worst you save one snapshot during a 100ms window where
  marker is being created — and the saved snapshot still has the live layout
- Survives the case where one process crashes (other still works)

Other tools that benefit from the same pattern: media auto-pause, BT
disconnect on lock, screenshot before lock, network-aware idle policy.

## Recommended tiered config (5 min → 30 min)

```ini
# ~/.config/swayidle/config
timeout 60  ~/Scripts/sway-idle-on.sh resume ~/Scripts/sway-idle-off.sh
timeout 300 ~/Scripts/sway-lock.sh
timeout 600 ~/Scripts/sway-screen-off.sh resume ~/Scripts/sway-screen-on.sh
timeout 1800 ~/Scripts/sway-suspend.sh
before-sleep ~/Scripts/sway-lock.sh
after-resume  ~/Scripts/sway-screen-on.sh
idlehint 300
```

Helper scripts (drop into `~/Scripts/`, chmod +x):

```sh
# sway-idle-on.sh     — touch marker
: > "$XDG_RUNTIME_DIR/sway-user-idle"

# sway-idle-off.sh    — rm marker
rm -f "$XDG_RUNTIME_DIR/sway-user-idle"

# sway-lock.sh        — screen lock
exec swaylock -f -c 000000

# sway-screen-off.sh  — DPMS off
exec swaymsg 'output * dpms off'

# sway-screen-on.sh   — DPMS on
exec swaymsg 'output * dpms on'

# sway-suspend.sh     — RAM suspend
exec systemctl suspend
```

Add `exec swayidle -w` to `~/.config/sway/config`. The `-w` flag blocks until
each command finishes (essential for `before-sleep` so swaylock is up before
the system actually goes to sleep).

## Debugging: see what swayidle parsed

The `-d` flag prints every line `parse_command` accepted. Combined with a
short `timeout` to auto-exit, you can verify your config in 2 seconds:

```bash
timeout 2 swayidle -C ~/.config/swayidle/config -d 2>&1 | grep -E "Command|Loaded"
```

Expected output: one `Command: /path/to/script.sh` per event, and a final
`Loaded config at /home/dr/.config/swayidle/config`. If you see `Command: sh`
or `Command: swaylock` (not the full path), you've hit pitfall 1.

## Signal control: SIGUSR1, SIGTERM, SIGINT

swayidle responds to signals — useful for scripted idle control:

| Signal | Effect |
|---|---|
| `SIGUSR1` | Immediately enter idle state (trigger all timeouts at once) |
| `SIGTERM`, `SIGINT` | Run all pending `resume` commands, then exit |

`pkill -USR1 swayidle` is a "fake-idle-now" trick for testing: fires all
timeouts so you can verify each command works without waiting 5 minutes.

## Linux suspend vs Windows sleep — quick map

Linux is **stricter** about distinguishing states than Windows:

| User intent | Linux command | ACPI | Windows term |
|---|---|---|---|
| Quick sleep, wake fast | `systemctl suspend` | S3 | "Sleep" |
| Full power off, no drain | `systemctl hibernate` | S4 | "Hibernate" |
| Sleep, auto-hibernate if no wake | `systemctl suspend-then-hibernate` | S3→S4 | (no direct equivalent) |
| S3 + disk backup | `systemctl hybrid-sleep` | S3+swap | "Hybrid sleep" |
| Black screen only, **not sleep** | `swaymsg 'output * dpms off'` | none | "Turn off display" |

**Critical gotcha for ex-Windows users**: `dpms off` is **not sleep**. The CPU
keeps running, Chrome keeps mining, downloads continue. To actually save
power you need `systemctl suspend` (RAM stays powered) or
`systemctl hibernate` (RAM dumped to swap, machine draws 0W).

**Swap size for hibernate**: must be ≥ RAM size. If swap is smaller,
`systemctl hibernate` silently fails or panics. Check with
`swapon --show` and `free -h`.

**Modern Standby (S0ix)**: Windows 8+ laptops enter a low-power S0 state where
the OS keeps running with network/WOL. Linux equivalent is `s2idle` (kernel
build option `CONFIG_SUSPEND_S2IDLE`) — many laptop ACPI firmwares don't
implement it properly, so behavior is uneven across vendors.

## Battery-aware idle policy (advanced)

The same `timeout` events can have different policies on battery vs AC. The
cleanest pattern: read AC status in a helper script and dispatch:

```sh
# sway-idle-policy.sh
bat_status=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null || echo "AC")
if [ "$bat_status" = "Discharging" ]; then
    exec systemctl suspend          # aggressive on battery
else
    exec swaylock -f -c 000000      # light on AC
fi
```

Wire as: `timeout 300 ~/Scripts/sway-idle-policy.sh`. Adjust the timeout
threshold in the same way if you want different AC/battery cutoff times.

## What swayidle cannot do (you need a wrapper)

- **Detect fullscreen video / media playback** — swayidle has no concept of
  "app is showing video". Use `playerctl` to detect active media and
  `pkill -STOP swayidle` / `-CONT` to pause/resume timing, or
  `swaymsg inhibit_idle` via `swayidle-inhibit` (separate tool).
- **Detect user presence** (camera, Bluetooth proximity) — beyond keyboard/
  mouse input, swayidle knows nothing.
- **Dynamically adjust timeout** based on context — must be done by an outer
  script that rewrites the config and restarts swayidle.
- **Coexist with screen lockers that use their own idle detection**
  (gnome-screensaver, etc.) — pick one as the source of truth.

## Common session log path

When "it's not working", check the journal first:

```bash
journalctl --user -u swayidle -n 50 --no-pager
# or, if swayidle was launched from sway config (not a service):
journalctl -b --no-pager | grep -i swayidle
```

Look for: `Wayland display connect failed`, `Compositor doesn't support
idle protocol` (sway always supports it), or `Lock signal received` for
lock events. The debug `-d` output goes to stderr — capture with
`2> ~/swayidle.log` if you need persistent logs.

## Cross-reference

- `~/.config/swayidle/config` — location of the config file (XDG-respecting)
- `man swayidle` — official event reference
- `man 5 logind.conf` — `IdleAction`, `IdleActionSec`, `HandlePowerKey`,
  `HandleLidSwitch` — the underlying logind policy that `idlehint` triggers
- `references/sway-workspace-restore-research.md` — for sway-session.py
  coordination patterns

## Quick verification recipe (end-to-end)

After changing sway-session.py to gate on `$XDG_RUNTIME_DIR/sway-user-idle`:

```bash
# 1. Start sway-session daemon in test mode (interval=2s)
sed -i 's/^INTERVAL = 300/INTERVAL = 2/' ~/Scripts/sway-session.py
python3 ~/Scripts/sway-session.py --daemon &

# 2. Tick 1: no marker → should save
sleep 3

# 3. Create marker → ticks should skip
touch $XDG_RUNTIME_DIR/sway-user-idle
sleep 3

# 4. Remove marker → should save again
rm -f $XDG_RUNTIME_DIR/sway-user-idle
sleep 3

# 5. Cleanup
pkill -f sway-session.py
sed -i 's/^INTERVAL = 2/^INTERVAL = 300/' ~/Scripts/sway-session.py
```

Watch the daemon's stdout for `✓ 已保存 N 个工作区` (saved) vs
`跳过 (用户 idle)` (skipped) to confirm the bridge works.
