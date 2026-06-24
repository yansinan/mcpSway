---
name: sway-exec-always-safety
title: sway config exec_always 完全指南：进程去重 + 写法陷阱
category: sway
tags: [sway, exec_always, swayidle, uxplay, quoting, sway-config, pkill, dedup, config-reload]
description: >
  Safeguard sway/i3 exec_always lines against duplicate processes on reload
  (pkill + exec pattern), and avoid common pitfalls: line-continuation failure,
  quoting nesting, patch-tool escape corruption, stale-process accumulation,
  cross-machine API-port probing, and verification procedures.
source: man 5 sway; session 2026-06-24 helix 屏保/投屏修复
---

# sway-exec-always-safety

## 1. 进程去重：`pkill + exec` 模式

sway/i3 的 `exec_always` 每次 reload 都重新执行命令——**没有内置的进程去重或自动 kill 机制**。

> 来源：sway(5) man page：*"Like exec, but the shell command will be executed again after reload."*

直接写 `exec_always uxplay -n foo ...` 会导致每次 `$mod+Shift+c` 都多一个进程。

### 标准方案

用 `bash -c` 包装，先 `pkill` 再 `exec`：

```ini
exec_always bash -c 'pkill -x <进程名> 2>/dev/null; sleep 0.2; exec <进程名> <参数...>'
```

关键点：
- `pkill -x` 精确匹配进程名，不误杀同名子进程
- `2>/dev/null` 忽略第一次运行时的 pkill 报错
- `sleep 0.2` 给系统时间释放资源（端口等）
- `exec` 替换 shell 进程，不留下多余 sh 进程

### 哪些 exec_always 需要保护

| 类型 | 例子 | 需要？ | 说明 |
|------|------|--------|------|
| 带 `--replace` 的程序 | `fcitx5 -d --replace` | ❌ | 程序自带去重 |
| 已先 `killall` 再启动 | `killall kanshi; kanshi` | ❌ | 手动 kill 在前面 |
| 普通服务进程 | `uxplay`, `blueman-applet`, `nm-applet` | ✅ | 不加保护则每次 reload 多一个 |
| 后台守护进程 | `waybar`, `swaybg` | ✅ | 已有 `killall` 包装的除外 |

### 实际配置示例

```ini
# uxplay
exec_always bash -c 'pkill -x uxplay 2>/dev/null; sleep 0.2; exec uxplay -n 餐桌 -s 1920x1080 -fps 60 -hls -fs -vs "waylandsink fullscreen=true"'

# blueman-applet
exec_always bash -c 'pkill -x blueman-applet 2>/dev/null; sleep 0.2; exec blueman-applet'
```

### pkill 的常见陷阱

- 不要写 `exec_always pkill -x uxplay; uxplay ...`（两行）— 中间窗口期可能产生重复
- `pkill` 不加 `-x` 可能误杀含相同子串的进程（如 `uxplay` 误杀 `uxplay-server`）
- `sleep` 太短（< 0.1）端口可能还没释放，太长则 reload 有明显的延迟感
- 不要用 `exec` 代替 `exec_always`：`exec` 只在 sway 首次启动时执行，reload 不重复

### 验证

```bash
# 查看当前 uxplay 进程数（应为 1）
pgrep -cx uxplay

# 触发 reload 后再查
swaymsg reload
pgrep -cx uxplay   # 仍应为 1
```

## 2. exec_always 写法陷阱

以下陷阱来源于 helix 机器上 swayidle 屏保和 uxplay 投屏配 置的实际修复过程。

### 2.1 sway config 不支持多行续行

#### 错误写法（不生效）
```ini
exec_always swayidle -w \
  timeout 600 'chromium --new-window "URL" >/dev/null 2>&1' \
  resume "swaymsg [title=\"Screen Saver\"] kill"
```

sway 把每一行当作独立命令解析：
- 第 1 行 `exec_always swayidle -w \` — `\` 是字面字符，不是 shell 续行符
- 第 2 行 试图 exec 字面字符串 `timeout 600 ...`（找不到 binary，静默失败）
- 第 3 行 同上，试图 exec `resume ...`

#### 正确写法（单行）
```ini
exec_always swayidle -w timeout 600 'chromium --new-window "URL" >/dev/null 2>&1' resume 'swaymsg [title="Screen Saver"] kill'
```

**原理**：sway 把 `exec_always` 整行传给 `sh -c` 执行。sway config 不是 shell 脚本，`\n` 不续行。

### 2.2 引号嵌套规则

| 层 | 解析器 | 引号规则 |
|---|---|---|
| 外层 | sway config | 无引号解析，整行给 `sh -c` |
| 中层 | `sh -c` | 用 `'...'` 保护内部双引号 |
| 内层 | chromium URL / swaymsg 参数 | 纯双引号 `"..."` |

写进文件后原始字节应该是：
```
exec_always swayidle ... timeout 600 'chromium --new-window "URL" >/dev/null 2>&1' resume 'swaymsg [title="Screen Saver"] kill'
```

用 `od -c` 或 `cat -A` 验证：文件中不能有字面反斜杠。

### 2.3 patch 工具的 `\"` 陷阱

#### 问题
`patch` 工具的 JSON 参数里写 `\"`，会被序列化成**字面反斜杠 + 引号**写入文件：

```
patch(old_string='resume "swaymsg..."')
# 文件里变成了
resume \"swaymsg...
```

#### 修法
- 用 `sed -i '14s/.*/.../'` 直接写整行（推荐）
- 或用 `write_file` 重写整个文件
- 避免用 `patch` 修含 `\"` 的行

#### 验证
```bash
sed -n '14p' /home/dr/.config/sway/config | od -c   # 看原始字节
```

### 2.4 用 `pgrep -ax` 而非 `ps | grep` 查进程

#### 错误
```bash
ps -eo pid,args | grep [s]wayidle
```
Hermes 自己的 bash wrapper 命令行里可能包含 `swayidle` 字符串，`ps | grep` 会误匹配。

#### 正确
```bash
pgrep -ax swayidle   # 只匹配进程名=swayidle
```

### 2.5 `swaymsg reload` 不会自动清理旧进程

`swaymsg reload` 触发 `exec_always` 重跑时，新 swayidle 拉起但旧进程还在。多次 reload 后会堆积多个 idle 进程同时监听同一个 timeout，屏保会触发多次。

#### 症状
```bash
pgrep -ax swayidle
# 输出多个 PID，etime 不同
```

#### 修法
reload 前先手动 kill 旧的：
```bash
pkill -x swayidle ; swaymsg reload ; sleep 1 ; pgrep -ax swayidle
```

x1tablet 用 systemd user unit 守护的 swayidle 不受影响（`BindsTo=graphical-session.target`），这台 helix 没这套机制，只能手动。

### 2.6 跨机调 Hermes API 探活（常见路径坑）

调用远端 hermes agent 转发任务时，永远不要相信 `.env` 写的端口——服务可能因 key 校验失败没启动，或端口被别的进程占用。

#### 探活顺序
```bash
# 1. TCP 探测（不要直接 curl，避免 shell 转义陷阱）
for p in 8643 8787 5000 5001 ; do timeout 3 bash -c "</dev/tcp/<host>/$p" 2>&1 && echo "$p OPEN" || echo "$p closed" ; done

# 2. 看实际监听 + 进程身份
ssh <host> 'ss -tlnp | grep -v "127.0.0.53"'

# 3. 看 hermes-gateway 启动日志
ssh <host> 'journalctl --user --since "1 hour ago" | grep -iE "api_server|placeholder"'

# 4. 用 python（干净字符串，避免 bash 转义）打 /v1/chat/completions
python3 -c 'import urllib.request,json; req=urllib.request.Request("http://<host>:<port>/v1/chat/completions",data=json.dumps({"model":"hermes","messages":[{"role":"user","content":"ping"}],"max_tokens":10}).encode(),headers={"Authorization":"Bearer <KEY>","Content-Type":"application/json"}); print(urllib.request.urlopen(req,timeout=8).read()[:300])'
```

#### 典型陷阱
| .env 写的 | 实际情况 | 教训 |
|---|---|---|
| `API_SERVER_PORT=8643` | 服务未启动（key 校验失败），5000 是 code-server | 先 `ss -tlnp` 看 PID 和 cmdline |
| `API_SERVER_KEY=<8chars>` | 服务无限循环刷"Refusing to start: <16 chars" | placeholder key 太短，必须 `openssl rand -hex 32` |
| `Authorization: Bearer <KEY>` | 401 Unauthorized | 端口对了但 key 不对，或端口实际是别人的服务 |

## 3. 验证清单（修改 sway config 后）

```bash
# 1. 语法检查
sway -C -c ~/.config/sway/config

# 2. 查看原始字节（确认无转义反斜杠）
sed -n '<行号>p' ~/.config/sway/config | od -c

# 3. reload
swaymsg reload

# 4. 检查目标进程
pgrep -ax swayidle

# 5. 检查重要依赖
systemctl is-active avahi-daemon          # uxplay 需要 mDNS
systemctl is-active avahi-daemon.socket   # uxplay 需要 mDNS
```

## 4. 配套 support files

- `references/helix-screensaver-recovery-2026-06-24.md` —— helix 屏保恢复完整流程
- `templates/swayidle-screensaver-exec-always.txt` —— 验证过的单行模板
- `scripts/verify-sway-config.sh` —— 一键验证脚本（语法 + 原始字节 + 进程 + 依赖）

## 5. 跨机分享

本地 skill → x1tablet 的 `~/.hermes/skills/local_share/<category>/` → mcpSway 仓库 `skills/local/<name>/` → git push。

x1tablet 的 mcpSway 仓库里可能有占位目录，先 `cat` 确认是否空，空就填充，有内容就合并不覆盖。
