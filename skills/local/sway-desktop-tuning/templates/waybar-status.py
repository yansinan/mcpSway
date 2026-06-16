#!/usr/bin/env python3
"""Waybar 状态脚本 — 统一入口模板

用法:
    waybar-status.py <network|tailscale|memory|temperature>

输出 JSON 给 Waybar custom 模块:
    text     — 状态栏文字(短)
    alt      — 简短状态(便于 CSS 路由)
    class    — 完整 CSS 类名(默认同 alt)
    tooltip  — 多行 Pango 标记

设计原则:
    - 每个子命令 < 200ms 完成
    - 失败时优雅降级,绝不抛 traceback
    - 错误信息走 stderr(便于 sway 日志排查)
    - 永远输出有效 JSON,即使所有数据源都失败

可移植:把 hostname 解析、hwmon 路径、Nerd Font 图标换成你机器的值。
      其余代码可直接复用。
"""
import json
import subprocess
import sys
from pathlib import Path

# ─── 工具函数 ───────────────────────────────────────
def emit(text: str, alt: str, tooltip: str) -> None:
    """统一 JSON 输出。永远打印,从不抛。"""
    print(json.dumps({
        "text": text,
        "alt": alt,
        "class": alt,
        "tooltip": tooltip
    }, ensure_ascii=False))
    sys.exit(0)


def run(cmd: list, timeout: float = 2.0) -> str:
    """subprocess 简化封装,失败返回空串。"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def read_meminfo(key: str) -> int:
    """读取 /proc/meminfo 中指定 key 的数值(kB)。"""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith(key + ":"):
                    return int(line.split()[1])
    except Exception:
        pass
    return 0


def proc_rss_kb(name: str) -> int:
    """汇总指定进程名的 RSS(kB)。

    先 pgrep,失败回退到 /proc 扫描。注意:不要用 "\nName:\\t<name>\\n"
    子串匹配 status 文件(开头无 \\n,会漏掉),用 /proc/<pid>/comm 比较。
    """
    total = 0
    pids_str = run(["pgrep", "-x", name], timeout=1)
    if pids_str:
        for pid in pids_str.split():
            try:
                with open(f"/proc/{pid}/status") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            total += int(line.split()[1])
                            break
            except (PermissionError, ProcessLookupError, FileNotFoundError, ValueError):
                continue
        return total
    # 回退:扫描 /proc
    for pid_dir in Path("/proc").glob("[0-9]*/comm"):
        try:
            if pid_dir.read_text().strip() == name:
                status = pid_dir.parent / "status"
                with open(status) as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            total += int(line.split()[1])
                            break
        except (PermissionError, ProcessLookupError, FileNotFoundError, ValueError):
            continue
    return total


def kb_to_mb(kb: int) -> float:
    return round(kb / 1024, 1)


# ═══════════════════════════════════════════════════
# 1. NETWORK
# ═══════════════════════════════════════════════════
def cmd_network() -> None:
    # 主机名(改成你想展示的格式)
    hostname = Path("/etc/hostname").read_text().strip() if Path("/etc/hostname").exists() else "?"
    fqdn_lan = (run(["hostname", "-f"], timeout=1) or hostname).strip()

    # 接口列表
    ifaces = {}
    try:
        out_json = run(["ip", "-j", "addr", "show"], timeout=2)
        for iface in json.loads(out_json):
            ifaces[iface["ifname"]] = {
                "state": iface.get("operstate", "?"),
                "mac": iface.get("address", ""),
                "addrs": [a.get("local", "") for a in iface.get("addr_info", []) if a.get("local")]
            }
    except Exception:
        pass

    # 默认路由
    default_dev = default_gw = None
    try:
        out_json = run(["ip", "-j", "route", "show"], timeout=2)
        for r in json.loads(out_json):
            if r.get("dst") == "default":
                default_dev, default_gw = r.get("dev"), r.get("gateway")
                break
    except Exception:
        pass

    # DNS(从 resolvectl)
    dns_servers = []
    rc = run(["resolvectl", "status"], timeout=2)
    for line in rc.splitlines():
        if line.strip().startswith("DNS Servers:"):
            dns_servers.append(line.split(":", 1)[1].strip())

    # Tailscale MagicDNS
    ts_dns = ""
    ts_status = run(["tailscale", "status", "--json"], timeout=2)
    if ts_status:
        try:
            ts_dns = json.loads(ts_status).get("Self", {}).get("DNSName", "").rstrip(".")
        except Exception:
            pass

    up_ifaces = [(n, i) for n, i in ifaces.items() if n != "lo" and i["state"] == "UP"]
    if not up_ifaces:
        emit("  ", "disconnected", "网络断开 — 无活动接口")

    lines = [f"<b>{hostname}</b>"]
    if fqdn_lan and fqdn_lan != hostname:
        lines.append(f"  LAN:  <span color='#888'>{fqdn_lan}</span>")
    if ts_dns:
        lines.append(f"  TS:   <span color='#a78bfa'>{ts_dns}</span>")
    lines.append("")

    for name, info in ifaces.items():
        if name == "lo" or info["state"] not in ("UP", "UNKNOWN"):
            continue
        marker = " ★" if name == default_dev else ""
        v4 = [a for a in info["addrs"] if "." in a]
        v6 = [a for a in info["addrs"] if ":" in a]
        lines.append(f"<b>{name}</b>{marker}  <span size='small' color='#888'>{info['state']}</span>")
        for a in v4:
            lines.append(f"  v4: {a}")
        for a in v6[:2]:
            lines.append(f"  <span size='small' color='#888'>v6: {a}</span>")
        if len(v6) > 2:
            lines.append(f"  <span size='small' color='#888'>v6: +{len(v6)-2} 更多</span>")
    lines.append("")

    if default_gw:
        lines.append(f"网关: {default_gw}  via {default_dev or '?'}")
    if dns_servers:
        lines.append(f"DNS:  {' '.join(dns_servers[:3])}")

    primary = default_dev or (up_ifaces[0][0] if up_ifaces else "net")
    emit(f" {primary} ", "connected", "\n".join(lines).rstrip())


# ═══════════════════════════════════════════════════
# 2. TAILSCALE — 三色状态机
# ═══════════════════════════════════════════════════
def cmd_tailscale() -> None:
    raw = run(["tailscale", "status", "--json"], timeout=3)
    if not raw:
        emit("TS ", "offline", "Tailscale 未运行 (sudo tailscaled?)")

    try:
        data = json.loads(raw)
    except Exception:
        emit("TS ", "offline", "Tailscale 状态解析失败")

    state = data.get("BackendState", "Unknown")
    if state != "Running":
        emit("TS ", "offline", f"Tailscale 状态: {state}")

    self_node = data.get("Self", {}) or {}
    self_dns = self_node.get("DNSName", "").rstrip(".")
    self_ips = data.get("TailscaleIPs", [])

    online, offline, exit_offers, subnet_routes = [], [], [], []
    for _, p in (data.get("Peer") or {}).items():
        name = p.get("HostName", "?")
        tags = p.get("Tags", []) or []
        is_exit = any("exit" in t.lower() for t in tags)
        if p.get("Online"):
            online.append((name, p.get("TailscaleIPs", []), is_exit))
        else:
            offline.append(name)
        if is_exit:
            exit_offers.append(name)

    # 自己广告的子网(非 100.x / fd7a:)
    for r in self_node.get("PrimaryRoutes", []) or []:
        if not r.startswith("100.") and not r.startswith("fd7a:"):
            subnet_routes.append(r)

    # 颜色判定
    if online:
        alt, text = "online", f"TS {len(online)}"
    elif offline:
        alt, text = "abnormal", "TS !"  # 运行但全离线 = 紫
    else:
        alt, text = "offline", "TS ·"   # 0 peer = 灰

    # 工具提示
    lines = []
    if self_dns:
        lines.append(f"<b>{self_dns}</b>")
    if self_ips:
        lines.append(f"  v4: {self_ips[0]}")
        if len(self_ips) > 1:
            lines.append(f"  <span size='small' color='#888'>v6: {self_ips[1]}</span>")
    if subnet_routes:
        lines.append(f"  <span size='small' color='#a78bfa'>路由: {', '.join(subnet_routes)}</span>")
    lines.append("")

    if online:
        lines.append(f"<span color='#8fc9a8'>● 在线 ({len(online)})</span>")
        for n, ips, is_exit in online[:8]:
            mark = " ▲" if is_exit else ""
            ip = ips[0] if ips else ""
            lines.append(f"  {n}{mark}  <span size='small' color='#888'>{ip}</span>")
        if len(online) > 8:
            lines.append(f"  <span size='small' color='#888'>... +{len(online) - 8}</span>")
    if offline:
        lines.append(f"<span color='#777'>○ 离线 ({len(offline)})</span>")
        for n in offline[:5]:
            lines.append(f"  {n}")
        if len(offline) > 5:
            lines.append(f"  <span size='small' color='#888'>... +{len(offline) - 5}</span>")
    if exit_offers:
        lines.append("")
        lines.append(f"<span color='#e8a87c'>▲ 出口节点: {' '.join(exit_offers)}</span>")

    emit(text, alt, "\n".join(lines).rstrip())


# ═══════════════════════════════════════════════════
# 3. MEMORY — 含 Sway 家族拆分
# ═══════════════════════════════════════════════════
def cmd_memory() -> None:
    total = read_meminfo("MemTotal")
    avail = read_meminfo("MemAvailable")
    cached = read_meminfo("Cached")
    buffers = read_meminfo("Buffers")
    shared = read_meminfo("Shmem")
    swap_total = read_meminfo("SwapTotal")
    swap_free = read_meminfo("SwapFree")

    used = total - avail
    pct = round(used * 100 / total) if total else 0
    swap_used = swap_total - swap_free

    sway_rss = proc_rss_kb("sway")
    swayidle_rss = proc_rss_kb("swayidle")
    swaybg_rss = proc_rss_kb("swaybg")
    sway_total = sway_rss + swayidle_rss + swaybg_rss

    top_procs = []
    ps_out = run(["ps", "-eo", "comm,rss", "--sort=-rss"], timeout=2)
    for line in ps_out.splitlines()[1:4]:
        parts = line.split()
        if len(parts) >= 2:
            try:
                top_procs.append((parts[0], int(parts[1]) // 1024))
            except ValueError:
                pass

    lines = [
        "<b>内存</b>",
        f"  已用: {kb_to_mb(used):.1f} MB / {kb_to_mb(total):.1f} MB ({pct}%)",
        f"  可用: {kb_to_mb(avail):.1f} MB",
        f"  缓存: {kb_to_mb(cached):.1f} MB",
        f"  缓冲: {kb_to_mb(buffers):.1f} MB",
        f"  共享: {kb_to_mb(shared):.1f} MB",
    ]
    if swap_total:
        lines.append(f"  交换: {kb_to_mb(swap_used):.1f} / {kb_to_mb(swap_total):.1f} MB")
    lines.append("")
    lines.append(f"<b>Sway 家族: {kb_to_mb(sway_total):.1f} MB</b>")
    lines.append(f"  sway      {kb_to_mb(sway_rss):>6.1f} MB")
    lines.append(f"  swayidle  {kb_to_mb(swayidle_rss):>6.1f} MB")
    lines.append(f"  swaybg    {kb_to_mb(swaybg_rss):>6.1f} MB")

    if top_procs:
        lines.append("")
        lines.append("<b>Top 进程</b>")
        for name, mb in top_procs:
            lines.append(f"  {name:<18} {mb:>6} MB")

    alt = "high" if pct >= 85 else "normal"
    emit(f" {pct}% ", alt, "\n".join(lines).rstrip())


# ═══════════════════════════════════════════════════
# 4. TEMPERATURE — CPU + 风扇 + NVMe + WiFi
# ═══════════════════════════════════════════════════
def cmd_temperature() -> None:
    lines = []

    # CPU 包/核心(直读 sysfs,比 sensors 快且可靠)
    package = None
    cores = []
    hwmon_dir = Path("/sys/devices/platform/coretemp.0/hwmon")
    if hwmon_dir.exists():
        for hw in hwmon_dir.iterdir():
            for label_path in hw.glob("temp*_label"):
                label = label_path.read_text().strip()
                input_path = label_path.with_name(label_path.name.replace("_label", "_input"))
                if not input_path.exists():
                    continue
                try:
                    val = int(input_path.read_text().strip()) // 1000
                except ValueError:
                    continue
                if label.startswith("Core "):
                    cores.append((label, val))
                elif label.startswith("Package"):
                    package = (label, val)

    if package:
        lines.append(f"<b>CPU</b>  {package[1]}°C")
        for name, v in cores:
            bar = "█" * max(0, (v - 30) // 5)
            lines.append(f"  {name}  {v:>3}°C  <span color='#e8a87c'>{bar}</span>")
        if cores:
            temps = [c[1] for c in cores]
            lines.append(f"  max/avg: {max(temps)}°C / {sum(temps)//len(temps)}°C")

    # 风扇/NVMe/WiFi — sensors -j 解析,NVMe 取 Composite 主温度
    sensors_out = run(["sensors", "-j"], timeout=2)
    if sensors_out:
        try:
            sj = json.loads(sensors_out)
            for adapter_name, adapter in sj.items():
                low = adapter_name.lower()
                if "thinkpad" in low:
                    for vals in adapter.values():
                        if isinstance(vals, dict):
                            for k, v in vals.items():
                                if k.startswith("fan") and isinstance(v, (int, float)) and v > 0:
                                    lines.append(f"<b>风扇</b>  {int(v)} RPM")
                if "nvme" in low:
                    # 优先 Composite,无则取第一个合理 _input
                    for vals in adapter.values():
                        if not isinstance(vals, dict):
                            continue
                        if "Composite" in vals and isinstance(vals["Composite"], (int, float)):
                            v = vals["Composite"]
                            if 20 < v < 100:
                                lines.append(f"<b>NVMe</b>  {v:.0f}°C")
                                break
                    else:
                        for vals in adapter.values():
                            if isinstance(vals, dict):
                                for k, v in vals.items():
                                    if k.endswith("_input") and isinstance(v, (int, float)) and 20 < v < 100:
                                        lines.append(f"<b>NVMe</b>  {v:.0f}°C")
                                        break
                                break
                if "iwlwifi" in low:
                    for vals in adapter.values():
                        if isinstance(vals, dict):
                            for k, v in vals.items():
                                if isinstance(v, (int, float)) and 20 < v < 100:
                                    lines.append(f"<b>WiFi</b>  {v:.0f}°C")
        except Exception:
            pass

    # 负载
    try:
        loadavg = Path("/proc/loadavg").read_text().split()
        lines.append(f"<b>负载</b>  {loadavg[0]}  {loadavg[1]}  {loadavg[2]}")
    except Exception:
        pass

    if package:
        main_temp = package[1]
    else:
        main_temp = max([v for _, v in cores] or [0])

    if main_temp == 0:
        emit(" -°C ", "unknown", "无法读取温度传感器")

    alt = "critical" if main_temp >= 80 else ("warm" if main_temp >= 70 else "normal")
    emit(f" {main_temp}°C ", alt, "\n".join(lines).rstrip())


# ─── 入口 ──────────────────────────────────────────
COMMANDS = {
    "network":     cmd_network,
    "tailscale":   cmd_tailscale,
    "memory":      cmd_memory,
    "temperature": cmd_temperature,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(f"用法: {sys.argv[0]} <{'|'.join(COMMANDS)}>", file=sys.stderr)
        sys.exit(1)
    try:
        COMMANDS[sys.argv[1]]()
    except Exception as e:
        emit("", "error", f"脚本异常: {e}")
