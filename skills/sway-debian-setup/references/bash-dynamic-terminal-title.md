# Bash Dynamic Terminal Titles (foot/xterm-256color)

Sets the terminal window title to show the current working directory when idle, and the current running command during execution.

**Source:** `~/.bashrc` case block matching `foot*` or `*-256color*` TERM values.

## Implementation

Insert into `~/.bashrc` (after the PS1 definition block, before aliases):

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

1. **PS1 embedding** (`\[\e]0;...\a\]`): The OSC escape sequence `\e]0;title\a` sets the terminal title every time the prompt is displayed. Bash prompt escapes like `\u`, `\h`, `\w` are evaluated at render time. When the prompt shows, the title reads `user@host:~/path`.

2. **DEBUG trap**: Bash fires the DEBUG trap before every command. `$BASH_COMMAND` contains the command text. `#*/` strips path prefix to show just the command name. `\033]0;...\007` is the same OSC sequence. The PS1 overrides it back on the next prompt.

3. **PWD abbreviation**: `${PWD/#$HOME/~}` replaces the full home path with `~`.

## Key details

- Use **single backslashes** in the file: `\[\e]0;` not `\\[\\e]0;`. Double backslashes (`\\[`) are literal backslash characters — the escape sequence won't work.
- The PS1 line must come AFTER the main PS1 assignment so it prepends the title sequence.
- The PS1 resets the title after each command finishes. The DEBUG trap sets it when a command starts.
- Works with `foot`, `foot-256color`, `tmux-256color`, `xterm-256color`, `xterm`, `rxvt`, `kitty`, and most modern terminals.
- Does NOT work in `dumb` terminals (like inside editors or CI runners) — the case block skips non-matching TERM values.

## Foot-specific note

Foot's default TERM is `foot` or `foot-256color`. The original Debian `.bashrc` only matches `xterm*|rxvt*`, so foot users need to add `foot*|*-256color*` to the case pattern for dynamic titles to work at all.
