# for_window Criteria — Syntax & Behavior

**Source:** sway 5 man page (CRITERIA section) — `https://raw.githubusercontent.com/swaywm/sway/master/sway/sway.5.scd`, lines 977–1112.

## Correct syntax — use `=`, value IS the regex

In sway, `app_id`, `class`, `title`, and other attributes that "can be a regular expression" use the **`=` operator** — the value is automatically treated as a PCRE2 regular expression. No tilde (`~`) needed.

```ini
# ✓ CORRECT — value is PCRE2 regex, = is the only operator
for_window [app_id="^chrome-"] border pixel 1
for_window [app_id="google-chrome"] border pixel 1
for_window [title="[Ss]way$"] move workspace 1
for_window [class="^Alacritty$"] floating enable

# ✗ WRONG — tilde ~ is OLD i3 syntax, not sway
for_window [app_id~"^chrome-"] border pixel 1
for_window [app_id ~ "^chrome-"] border pixel 1
```

The man page explicitly shows `[app_id="some-application" title="[Rr]egex.*"]` — the same `=` is used for both exact match and regex. Sway differentiates by whether the criteria attribute supports regex (most do: `app_id`, `class`, `title`, `instance`, `shell`, `tag`, `workspace`, `sandbox_engine`, `sandbox_app_id`, `sandbox_instance_id`).

### PCRE2 features

Sway uses PCRE2 (documented in `man pcre2pattern` / `man pcre2syntax`). Useful patterns:

| Pattern | Meaning | Example |
|---------|---------|---------|
| `^foo` | Starts with "foo" | `[app_id="^chrome-"]` |
| `bar$` | Ends with "bar" | `[app_id="-Default$"]` |
| `[Ss]way` | Case-insensitive alternation | `[title="[Ss]way"]` |
| `foo\|bar` | Alternation | `[app_id="^chrome-\|^google-chrome"]` |

### Criteria attributes that support regex

| Attribute | Applies to | Notes |
|-----------|-----------|-------|
| `app_id` | Wayland native apps | Chrome, foot, all Wayland apps |
| `class` | XWayland apps | Chromium-browser, wine, etc. |
| `title` | Both | Case-sensitive by default |
| `instance` | XWayland apps | `WM_CLASS` instance field |
| `shell` | Both | Values: `xdg_shell` or `xwayland` |
| `workspace` | Both | Workspace name |

### Static match vs regex

A value with no special regex characters (`google-chrome`, `foot`) works as an exact match. PCRE2 treats plain text as literal — `google-chrome` matches only `google-chrome`.

## for_window only applies to NEW windows

`for_window` rules register callbacks on new window creation/mapping. **Existing windows are not affected.** To apply a rule to already-open windows:

```bash
swaymsg '[app_id="foot"]' border pixel 1
swaymsg '[app_id="google-chrome"]' border none
```

The `swaymsg` command is immediate — it runs the sway command on matching windows right now. The `for_window` config rule will catch the next window of that type.

## border pixel vs tabbed/stacking container titles

`for_window [app_id="..."] border pixel 1` removes the **window-level** title bar. It does NOT affect **container-level** decorations:

| Layout | What you see after `border pixel 1` |
|--------|--------------------------------------|
| **split** (splith/splitv) | 1px border around each window — no title bars ✅ |
| **tabbed** | 1px border around the content area, but the **tab bar at the top** persists — it's a container decoration, not a window title bar |
| **stacking** | 1px border around content, but the **stacked title bar** persists (container-level) |

The tabbed/stacking tab header is a feature of the **parent container**, not the child window. `for_window` can only affect the child window that matches the criteria. To hide tab headers, change the container layout:

```bash
swaymsg layout toggle split      # tabbed → splith/splitv
swaymsg layout toggle tabbed     # cycle through layouts
```

## Stale SWAYSOCK causes IPC failures

When checking criteria from a script or terminal session outside sway's own `exec`, `$SWAYSOCK` may point to a stale socket after sway restarted:

```bash
# Stale — PID changed after restart
echo $SWAYSOCK
# /run/user/1000/sway-ipc.1000.1552.sock

# Current socket
export SWAYSOCK=$(ls -t /run/user/1000/sway-ipc.*.sock | head -1)
```

Symptoms: `swaymsg -t get_tree` returns empty, `swaymsg` exits silently, or error "Unable to connect to /run/user/1000/sway-ipc.*.sock".
