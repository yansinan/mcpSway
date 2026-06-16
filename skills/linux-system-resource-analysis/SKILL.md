---
name: linux-system-resource-analysis
source:
  - https://www.kernel.org/doc/html/latest/filesystems/proc.html
  - https://man7.org/linux/man-pages/man5/proc.5.html
description: "Diagnose Linux system resource usage — memory footprint, CPU performance, multi-host comparison, desktop environment (sway/GNOME/KDE) memory breakdown."
tags: [linux, monitoring, performance, memory, cpu, sysadmin]
---

# Linux System Resource Analysis

A reusable workflow for diagnosing Linux system resource usage — both single-host (memory/CPU profiling) and multi-host (comparison across machines over SSH/Tailscale).

## When to load this skill

Load when the user asks any of:
- "为什么内存占用这么大" / "what's eating my RAM" / "memory high"
- "分析 sway / 桌面系统 的内存占用" / "analyze DE footprint"
- "比较本机和 serverhome / 主机 A 和 B" / "compare host A and host B"
- "CPU 性能对比" / "memory performance comparison"
- "swap 触发了么" / "load average 多高算正常" / "system slow"

## Memory analysis workflow (single host)

### Step 1: System-level breakdown from /proc/meminfo

Always read these fields first. They are the canonical memory picture:

```
MemTotal        物理总量
MemFree         真·空闲 (low is normal — not a problem)
MemAvailable    应用还能申请多少 ← 关键指标
Cached          文件页缓存 (随时可回收)
Active(anon)    应用堆内存 (真实占用)
Inactive(file)  可回收的文件缓存
Shmem           tmpfs / 共享内存
AnonHugePages   大页使用 (THP) — 高 = 应用在用 mmap 块
Buffers         块设备缓存 (几乎总是 ~0)
SwapTotal/Free  swap 容量/空闲
```

**Pitfall — `free -h` 看起来很紧但其实没压力**：用户看到 `used=7.7G/16G, free=1.8G` 经常误以为 OOM 快到了。事实：
- `MemFree` ≠ 真实空闲；要看 `MemAvailable`
- `Cached` 永远算在 "used" 里，但随时可回收
- 真正危险信号是 `SwapFree` 持续下降 + `/proc/pressure/memory:some` 高

**Pitfall — `Committed_AS` 大于 `CommitLimit` 不一定 OOM**：前者是进程"承诺"会用的虚拟内存总量，可以远超物理内存（lazy allocation）。只有当内核真的开始 reclaim + swap 才算压力。

### Step 2: Process-level breakdown by command family

```bash
# 按 RSS 排序的前 30 进程
ps -eo pid,user,rss,vsz,comm,args --sort=-rss | head -31

# 按用户聚合 RSS (可看到 dr vs root 各占多少)
ps -eo user,rss --sort=-rss | awk '{rss[$1]+=$2; count[$1]++} END {for (u in rss) printf "%-12s %8.1f MB  %d procs\n", u, rss[u]/1024, count[u]}'

# 按 comm 主进程名聚合 (用于 Chrome / sway 之类多进程)
ps -eo comm,rss --sort=-rss | awk '{rss[$1]+=$2; count[$1]++} END {for (c in rss) printf "%-30s %8.1f MB  %d procs\n", c, rss[c]/1024, count[c]}' | sort -k2 -n -r
```

**Pitfall — RSS 虚高 / 重复计算**：
- Chrome / Electron / VSCode 每个标签页 = 1 个 renderer (~150-460 MB)
- GPU 进程把整块显存 mmap 进自己地址空间（1-1.5 GB），但实际占用没这么多
- 共享库按 mmap 计入每个进程的 RSS，但物理只占一份
- 加总所有进程 RSS 通常 > MemTotal，因为有共享页

**正确判断"谁吃内存"**：
- 对单进程：`PSS` (Proportional Set Size) 比 RSS 准，可用 `smem -t -k -p` 或 `cat /proc/<pid>/smaps` 看
- 对多进程族：聚合 comm 名，比加 RSS 更直观
- 对 anon 真·内存：`ps -eo pid,comm,rss,vsz --sort=-rss` + `VmRSS` 字段对比

### Step 3: Desktop environment footprint (sway / GNOME / KDE)

For sway (user's setup), the full ecosystem typically:
```
sway                  ~108 MB   合成器本体
swaybar               ~23 MB    顶栏
swaybg                ~6 MB     壁纸
foot                  ~45 MB    终端 (per instance)
fcitx5                ~130 MB   输入法 (中文词库加载后偏大)
blueman-applet+tray   ~104 MB   蓝牙托盘 (偏大, 可换 blueberry)
pipewire ×3           ~56 MB    音频栈
xdg-desktop-portal 系 ~30 MB    桌面门户
dbus + polkit + logind ~34 MB   系统服务
─────────────────────────────
sway 桌面合计          ~540 MB
```

Compare to:
- GNOME 完整会话  idle  ≈ 1.2-1.8 GB
- KDE Plasma      idle  ≈ 1.0-1.5 GB
- **sway          idle  ≈ 0.4-0.6 GB** (60% lighter than traditional DE)

Useful commands:
```bash
# sway 生态进程 (合成器 + 终端 + 输入法 + 蓝牙 + 音频)
ps -eo pid,user,rss,comm --sort=-rss | awk '/sway|wayland|foot|fuzzel|swaybar|swaylock|swayidle|waybar|wlroots|fcitx|blueman|pipewire|wireplumber|xdg|polkit|dbus|systemd-logind/'

# 检查 systemd-journald 占用 (通常 30-80 MB, 异常大说明日志没 rotate)
ps -o rss= -C systemd-journald
journalctl --disk-usage
sudo journalctl --vacuum-size=200M    # 砍到 200 MB
```

## CPU analysis workflow

### Step 1: Core topology
```bash
lscpu | grep -E "Model name|Architecture|CPU\(s\)|Thread|Core|Socket|Vendor|Flags"
cat /proc/cpuinfo | grep -E "model name|cpu MHz|cache size" | head -3
```

### Step 2: Hardware identity (when model name is censored/redacted)
Some hosts (cloud VMs, kernels with CPU brand string masking) show `i7-5###U` placeholders. Recover real identity from DMI/SMBIOS:
```bash
cat /sys/devices/virtual/dmi/id/product_name
cat /sys/devices/virtual/dmi/id/board_vendor
cat /sys/devices/virtual/dmi/id/board_name
cat /sys/devices/virtual/dmi/id/bios_vendor
cat /sys/devices/virtual/dmi/id/bios_version
cat /sys/devices/virtual/dmi/id/bios_date
```

Cross-reference with Intel/AMD ARK: "CRESCENTBAY" + "INTEL Corporation" + 2C/4T + 2.20GHz + 4MB L3 + 2018 BIOS = **Intel NUC5i7RYH** with i7-5650U (Broadwell-U).

### Step 3: Performance comparison (no benchmark required)
Use published PassMark / Cinebench R15 numbers as rough estimates for cross-generation comparison:
```
i7-5650U (Broadwell)     ~1500 single / ~3000 multi  PassMark
i7-8550U (Kaby Lake-R)   ~1900 single / ~7700 multi  PassMark
                                    ↑ 30% IPC + 4C8T vs 2C4T
```

## Multi-host comparison workflow

### Step 1: Check reachability
```bash
ping -c 2 -W 2 <host>          # 验证 Tailscale / 网络可达
ssh -o BatchMode=yes -o ConnectTimeout=3 <host> 'echo OK'   # 验证 SSH 密钥
```

### Step 2: First-time SSH host key handling
**Do NOT use `-o StrictHostKeyChecking=no`** (MITM vulnerable). Use:
```bash
ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 <host> '<cmd>'
```
- `accept-new` adds key on first connect, refuses on subsequent change
- After successful first connect, the key is in `~/.ssh/known_hosts` for future sessions
- The "Host key verification failed" error from default `BatchMode=yes` is expected on first run

### Step 3: Run identical probes on both hosts
```bash
LOCAL_CMD='lscpu | grep -E "Model name|CPU\(s\)|Core|Thread"; free -h; cat /sys/devices/virtual/dmi/id/board_name; uptime'

# 本机
bash -c "$LOCAL_CMD"

# 远端 (Tailscale hostname preferred over IP, 见 ssh config 备忘)
ssh <user>@<host>.tail*.ts.net "$LOCAL_CMD"
```

If the remote shell has MOTD/PS1 substitutions that mangle output (e.g. censors `5xxxU` → `5###U`), bypass with:
```bash
ssh <host> 'bash --noprofile --norc -c "<clean commands>"'
```

### Step 4: Tailscale hostname discovery
```bash
tailscale status --json 2>/dev/null | jq -r '.Peer[] | "\(.HostName)\t\(.TailscaleIPs[0])"' | grep -i <shortname>
# or
tailscale status | grep -i <shortname>
```

## Common heavy hitters on Debian 13 + sway (user's environment)

| Process family        | Typical RSS   | Notes                                     |
|-----------------------|---------------|-------------------------------------------|
| Chrome (PWA + CDP)    | 3-6 GB        | Each tab = renderer ~150-460 MB; GPU ~1.5 GB mapped |
| code-server + pyright | 0.7-1.0 GB    | VSCode extension host + LSP                |
| Hermes agent (Python) | 0.4-0.8 GB    | Venv, gateway, webui server.py             |
| sway + DE             | 0.4-0.6 GB    | See sway breakdown above                   |
| systemd-journald      | 30-80 MB norm | 200+ MB = 没 rotate, 见上 cleanup          |
| tailscaled            | 100-200 MB    | Go daemon, 正常                            |

## Pitfalls — memory analysis

1. **`free` 看到的 used = MemTotal - MemFree**，但 Cached 也在 used 里，**不能直接看 used 判定 OOM 风险**。永远用 MemAvailable。
2. **`Zswap` / `Zswapped` 不为 0** 表示内核在做 zswap 压缩 swap page（好事，节省 I/O），不是问题。
3. **AnonHugePages 接近 Active(anon) 一半** = THP 正常工作。不要去改 `/sys/kernel/mm/transparent_hugepage/enabled`。
4. **Chrome 的 RSS 加总虚高**：GPU 进程的 mmap 显存、共享库、shmem 都重复计入。要看实际 anon，用 `ps -o rss= -p <pid>` × 进程数 + PSS 校正。
5. **fcitx5 130 MB** 是正常的（中文拼音词库 + addon），不是泄漏。如果只需要拼音，可关 chttrans / clipboard addon 减半。
6. **blueman 100+ MB** 偏大，不用时可关，或者换 blueberry。
7. **systemd-journald > 200 MB** 异常，必有日志没 rotate。先 `journalctl --disk-usage` 看，再 `vacuum-size`。

## Pitfalls — CPU comparison

1. **跨代 IPC 差异容易被忽视**：Broadwell → Kaby Lake ~15% IPC/clock, → Skylake 再 ~5%, → Zen/+ 再 ~15%。所以 i7-8550U vs i7-5650U 不只是频率差。
2. **核心数比单核频率重要**（对并行负载）：4C8T vs 2C4T 在编译、训练、并行编译时差 2-3×，单线程负载差 ~30%。
3. **`/proc/cpuinfo` 显示的 cpu MHz 是当前频率**（scaling governor 影响），不是基频/睿频。要基频看 model name 后的 `@ x.xxGHz`。
4. **缓存大小影响内存密集负载**：8MB L3 vs 4MB 在数据库、编译、大模型推理上差距明显。

## Output format (terminal-friendly)

When reporting analysis, prefer this structure (text-renderable, no markdown bloat):
```
================================================================
                    <section title>
================================================================
<aligned columns or bullet list>

★ Key takeaway in one line
```

## References

- `references/2026-06-14-sway-footprint-deep-dive.md` — full sway ecosystem breakdown for this user (Chrome + Hermes + sway dual-Chrome setup)
