# Sway 桌面内存深度拆解 — 用户环境 (2026-06-14)

## 触发背景

用户问"本机内存占用为什么这么大？分析一下，特别是 sway 相关"。
本地: Lenovo X1 Tablet Gen 2 (i7-8550U, 16GB), Debian 13 + sway 桌面。

## 系统级内存实际数值

```
MemTotal        15.4 GB
MemFree          1.78 GB    ← 看着紧
MemAvailable     7.62 GB    ← 真实可申请
Cached (file)    7.17 GB    ← 文件页缓存，可随时回收
Active(anon)     5.73 GB    ← 真实应用堆内存
Shmem            1.27 GB    ← tmpfs / 共享内存
AnonHugePages    2.05 GB    ← THP 正常工作
SwapUsed         0          ← 12 GB swap 完全空
```

## Chrome 是真凶：双实例架构

用户在跑 **2 个独立 Chrome 实例**：

| 实例 | 路径 | 进程组 RSS | 用途 |
|------|------|-----------|------|
| PWA Chrome | /home/dr/.hermes/chrome-debug | ~4 GB | 用户日常 (含多个 PWA: Hermes WebUI, DeepSeek, OneNote) |
| CDP Chrome | /home/dr/.hermes/cdp-chrome | ~1.5 GB | Hermes agent 用 (browser_navigate / browser_snapshot) |
| **合计** | | **~5.5 GB RSS** | 实际 anon ~3.5 GB, 其余是 V8 JIT / 共享库 / GPU mmap |

**优化路径**（按代价从小到大）：
1. 关掉闲置标签页（用 The Great Suspender 类扩展）
2. 合并两个 Chrome 实例：让 Hermes CDP 共享 PWA Chrome 端口 (browser.cdp_url 配置已有此能力)
3. 切换到 Edge / Brave / ungoogled-chromium（不一定省）

## sway 桌面完整组件 (RSS)

| 组件 | PID | RSS | 角色 |
|------|-----|-----|------|
| sway | 294966 | 108 MB | 合成器本体 (wlroots) |
| swaybar | 294985 | 23 MB | 顶栏 (date/CPU/mem) |
| swaybg | 294975 | 6.5 MB | 壁纸 |
| foot | 295643 | 45 MB | 终端 (单实例) |
| fcitx5 | 295003 | 130 MB | 输入法 (中文词库) |
| blueman-applet | 295007 | 59 MB | 蓝牙托盘 |
| blueman-tray | 295031 | 45 MB | 蓝牙托盘 |
| pipewire | 1499 | 17 MB | 音频服务 |
| wireplumber | 1503 | 21 MB | PipeWire 会话 |
| pipewire-pulse | 1505 | 18 MB | PulseAudio 兼容 |
| xdg-desktop-portal | 5419 | 16 MB | 桌面门户 |
| xdg-document-portal | 5429 | 7.3 MB | 文件选择器 |
| xdg-permission-store | 5424 | 7.0 MB | 权限存储 |
| polkitd | 846 | 8.8 MB | 权限代理 |
| dbus-daemon ×3 | 多 | ~16 MB | 系统总线 |
| systemd-logind | 848 | 9.4 MB | 登录管理 |
| **sway 桌面合计** | | **~540 MB** | |

## 其他大块占用

- systemd-journald 357 MB ⚠ (异常, 见下)
- tailscaled 172 MB (Go daemon, 正常)
- code-server + pyright-langserver 930 MB
- Hermes ecosystem: gateway + webui + 2 sessions ≈ 1.85 GB

## 异常项 — systemd-journald 357 MB

正常应 30-80 MB。修复:
```bash
journalctl --disk-usage
sudo journalctl --vacuum-size=200M
# 永久: /etc/systemd/journald.conf → SystemMaxUse=200M
```

## 对比标杆 (sway vs 传统 DE)

| 桌面 | idle 内存 |
|------|----------|
| GNOME | 1.2 - 1.8 GB |
| KDE Plasma | 1.0 - 1.5 GB |
| **sway (此配置)** | **0.4 - 0.6 GB** |
| 节省 | 60% - 70% |

sway 的核心卖点：极简 Wayland 合成器，比传统 DE 省 600 MB - 1.2 GB。

## 总结

1. 7.7G "已用" 中 ~5.5G 是用户主动选的双 Chrome
2. sway 桌面本身只占 540 MB, 没有任何内存瓶颈
3. system-journald 357 MB 是需要清理的异常
4. MemAvailable 7.6 GB 仍宽裕, 零 swap 触发, 系统健康
