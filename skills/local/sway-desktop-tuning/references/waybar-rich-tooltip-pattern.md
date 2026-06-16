# Waybar Rich-Tooltip Status Modules — Unified Script Pattern

Developed on Debian 13 (sway 1.10.1, waybar 0.12.0). Replaces the built-in
`temperature` / `memory` / `network` modules with custom `custom/*` modules
backed by a **single Python entry point** that emits rich Pango-formatted
tooltips.

## Why a unified script

The user strongly prefers **one entry point with subcommands** over scattered
helper scripts (see SKILL.md "User preference: unified entry point"). The
benefit compounds for waybar:

- **One process model** — five subcommands share the same Python startup
  cost. Waybar runs each on its own `interval`, so the per-invocation cost
  is ~50–200 ms (mostly Python import time).
- **One place to add a new status module** — `memory.py`/`network.py`/
  `temperature.py`/`tailscale.py` all roll into one `waybar-status.py` with
  a new function and one new entry in the `COMMANDS` dict.
- **Consistent JSON output schema** — every subcommand emits the same
  `{text, alt, class, tooltip}` shape. The `class` field drives CSS state
  routing (e.g. `online` / `abnormal` / `offline` for Tailscale).
- **Consistent error handling** — `emit()` always prints valid JSON, never
  a traceback that would crash waybar's polling.

## The JSON schema

Waybar's `custom/*` modules with `return-type: "json"` parse this:

```json
{
  "text":    "TS 6",                          // status-bar text (compact)
  "alt":     "online",                        // short state for icons
  "class":   "online",                        // full CSS class (= alt here)
  "tooltip": "<b>x1tablet.tail…</b>\n  v4…"   // multi-line Pango markup
}
```

Rules that matter:

- `text` is what the user sees at a glance. Keep it short (≤ 8 chars).
- `class` (or `alt`) becomes a CSS class on the module's DOM node. Use it
  for state-based coloring, not `text` substring matching.
- `tooltip` is rendered as Pango markup. Plain text works; `<b>`, `<i>`,
  `<span color="#hex" size="small">`, and `\n` are all supported. **No
  HTML** — `<br/>` does nothing, use `\n`.
- Always emit all four fields, even on failure. An empty `text: "✗"` with
  `alt: "error"` keeps the bar layout stable when a sensor disappears.

## The 4 subcommands

| Subcommand | Replaces built-in | Interval | Notes |
|---|---|---|---|
| `network`     | `network`     | 8 s  | hostname + FQDN + TS MagicDNS, all active interfaces with v4/v6, default gw, DNS |
| `tailscale`   | (none)        | 30 s | self FQDN/IPs, online+offline peer list, exit node marker, advertised subnets |
| `memory`      | `memory`      | 5 s  | total/used/avail/cached/buffers/swap, Sway 家族 breakdown, Top 3 procs |
| `temperature` | `temperature` | 5 s  | CPU package + per-core with bar chart, ThinkPad fan RPM, NVMe, WiFi, loadavg |

## Tailscale three-state pattern

Two-axis state machine:

| BackendState | Peer count online | alt / class | text | Color |
|---|---|---|---|---|
| `Running` | ≥ 1 | `online`   | `TS N` | green  |
| `Running` | 0   | `abnormal` | `TS !` | purple |
| (any other) or daemon down | — | `offline` | `TS ✗` / `TS ·` | gray |

CSS example:

```css
#custom-tailscale            { color: #000; }
#custom-tailscale.online     { color: #2d8a4e; font-weight: bold; }
#custom-tailscale.abnormal   { color: #8a3fd1; font-weight: bold; }
#custom-tailscale.offline,
#custom-tailscale.disconnected { color: #aaa; }
```

The "Running but 0 online" case is the **abnormal** state — daemon is up
and authenticated, but every peer is offline. The user gets a visible
warning (purple) that the VPN is up but the mesh is dark.

## NVMe sensor filtering (sensors -j gotcha)

`sensors -j` returns multiple temperature values per adapter for NVMe:

```json
"nvme-pci-0500": {
  "Composite": 38.0,    // <-- the main temperature
  "Sensor 1":  75.0,    // sub-sensor (often a different die)
  "Sensor 2":  80.0
}
```

Naive parsing that includes any 20–100 °C value will show 3 lines per
NVMe device. Take `Composite` first; fall back to the first `_input`
sibling if it's missing.

Same filtering idea applies to `iwlwifi` (single sensor, no filtering
needed) and `thinkpad` (multiple temps; the relevant one is usually
`CPU` or `temp1`).

## Sway family memory breakdown

The `memory` subcommand reports per-process RSS for `sway`, `swayidle`,
`swaybg`. A typical breakdown is ~120 MB / 3 MB / 6 MB. This answers the
"why is sway using 400 MB?" question immediately in the tooltip.

Reading strategy:

1. Try `pgrep -x <name>` first — fast, single syscall.
2. Fall back to `Path("/proc").glob("[0-9]*/comm")` scan if pgrep isn't
   available or returns nothing. Read `/proc/<pid>/comm` (single word,
   stable) and match exactly, then read `/proc/<pid>/status` for `VmRSS`.

Common pitfall: `/proc/<pid>/status` starts with `Name:\tsway\n` (no
leading newline). A substring check like `"\nName:\tsway\n" in content`
silently fails because the file does not start with `\n`. Match on
`comm` instead, or use a `startswith()` check on the first line.

## Surgical revert when another agent is working on the same file

**Scenario**: user asks to revert your waybar config changes. Another
agent is simultaneously editing the dock section in the same file.
Wholesale `cp backup current` would destroy the other agent's work.

**Pattern** (preserves the other agent's edits, undoes only yours):

```bash
# 1. Diff to confirm your changes are confined to known lines
diff backup current | head

# 2. Identify the line number where the dock section starts
grep -n "Dock" current  # → 54
grep -n "Dock" backup   # → 50

# 3. Splice: backup[1..49] (your-revert-target section) + current[54..end] (other agent's work)
sed -n '1,49p' backup > /tmp/revert.json
sed -n '54,$p' current >> /tmp/revert.json

# 4. Validate JSON parses, then move into place
python3 -c "import json; json.load(open('/tmp/revert.json'))" && \
  mv /tmp/revert.json current
```

The line numbers (`49` and `54`) come from the diff. The exact split
point is whatever section the other agent's work starts at.

**Same pattern for CSS** — use `patch` with surgical `old_string` /
`new_string` rather than `cp backup`. CSS file baselines are even more
likely to be in flux (a different theme may have been synced in between
your read and your edit), so trusting the backup wholesale is risky.

## When the user's current file is in a DIFFERENT state than your backup

This actually happened during this skill's development: my backup
captured the dark theme, but the user had switched to the light theme
between my read and my edit. Wholesale restore from backup would have
re-implemented the dark theme over the user's actual light theme.

**Rule**: trust the current file state as ground truth. Use `diff` to
identify only the lines you added, then `patch` them out. If the diff
shows changes you don't recognize (different theme, reformatted
sections, etc.), **ask the user** before wholesale-replacing anything.

## Putting it together: a working waybar-status.py template

See `templates/waybar-status.py` for a portable starting point. The
template is the working script minus user-specific values (hostname
formatting, exact hwmon paths, Nerd Font icons). `cp` it to
`~/.local/bin/waybar-status.py` and add a `return-type: json` config
block for each subcommand.
