# Dynamic Bash Terminal Titles for sway (foot/xterm/tmux)

**Problem**: In sway tabbed/stacking containers, the terminal's title appears as a small label. By default foot shows just `"foot"` — useless for identifying which terminal is which.

**Solution**: Set the terminal window title dynamically via bash:
- **Running a command**: show `"command → ~/path"`
- **At prompt (idle)**: show `"user@host:~/path"`

## Implementation (`.bashrc`)

```bash
# 终端窗口标题：当前路径 + 运行命令 (支持 foot/xterm/tmux)
case "$TERM" in
xterm*|rxvt*|foot*|*-256color*)
    # 空闲时显示 "用户@主机:路径"
    PS1="\[\e]0;${debian_chroot:+($debian_chroot)}\u@\h: \w\a\]$PS1"
    # 运行命令时显示 "命令 → 路径"
    trap 'printf "\033]0;%s → %s\007" "${BASH_COMMAND##*/}" "${PWD/#$HOME/~}"' DEBUG
    ;;
*)
    ;;
esac
```

## How it works

| Mechanism | What it does | When |
|-----------|-------------|------|
| `PS1` with `\[\e]0;...\a\]` | OSC 0 escape sequence sets terminal title | Every prompt display (after command finishes) |
| `trap ... DEBUG` | Overrides title to show the command being run | Before every command executes |
| `${BASH_COMMAND##*/}` | Strips path from command (e.g. `vim` not `/usr/bin/vim`) | In DEBUG trap |
| `${PWD/#$HOME/~}` | Shortens home directory to `~` | In both |

## The OSC escape sequence

- `\033]0;` — OSC code 0 (set window title + icon name)
- `\007` — BEL character, terminates the OSC sequence
- foot also accepts `\033\\` (ST) as terminator

The same escape works in: foot, foot-256color, xterm, xterm-256color, tmux-256color, kitty, alacritty, and most modern terminals.

## Pitfalls

1. **`$TERM` must match**: foot native = `foot` or `foot-256color`. Inside tmux = `tmux-256color`. The case statement needs all three patterns.
2. **`-256color` suffix is common**: Debian foot, tmux, and xterm all emit `*-256color`. Cover with `foot*|*-256color*`.
3. **PS1 must be set before the OSC prefix is appended**: The `PS1=...\[\e]0;...\a\]$PS1` pattern prepends the escape to the existing PS1. If PS1 is empty at that point, the title is empty.
4. **DEBUG trap fires for PROMPT_COMMAND too**: The trap sets the title to `PROMPT_COMMAND → ~/path` just before the OS calls PROMPT_COMMAND. This is usually harmless (the PROMPT_COMMAND runs in ~1ms, then PS1 fires and overwrites the title back). If visually annoying, add a filter in the trap.
5. **Foot only supports `\033]0` for title**: `\033]2` (icon only) and `\033]1` (icon name) are not standard on Wayland terminals.
