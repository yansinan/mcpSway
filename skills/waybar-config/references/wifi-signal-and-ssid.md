# WiFi 信号强度 + SSID 解析

适用场景:最小化 Debian 缺 `iw`/`iwconfig`/`nmcli`/`wpa_cli`,waybar 内置 `network` 模块拿不到 SSID(显示空),需要自写脚本补全。

## 为什么走 wpa_supplicant control socket 不行

`/run/wpa_supplicant/wlp4s0` 默认是 `srwxrwx--- root:root`,即使 dr 在 `netdev` 组也读不到(全局 `-G GROUP=netdev` 只对 global 目录生效,不影响 per-interface socket)。改 systemd unit 才能修,比装 iw 麻烦得多。

**直接装 `iw`**:
```bash
sudo apt install -y iw    # ~50KB,标准无线工具
```

## 拿 SSID

```python
import subprocess, re

def wifi_ssid(iface: str) -> str | None:
    r = subprocess.run(
        ["/sbin/iw", "dev", iface, "link"],
        capture_output=True, text=True, timeout=2
    )
    if r.returncode != 0:
        return None
    m = re.search(r"SSID:\s+(\S+)", r.stdout)
    return m.group(1) if m else None
```

**`iw dev wlp4s0 link` 输出示例**:
```
Connected to 8c:de:f9:e3:32:cd (on wlp4s0)
    SSID: DrHome
    freq: 5200.0
    signal: -49 dBm
    rx bitrate: 520.0 MBit/s VHT-MCS 5 80MHz short GI VHT-NSS 2
```

## 拿 dBm 信号强度(0-4 格)

`/proc/net/wireless` 不需要 root,任何用户可读:
```
Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
 face | tus | link level noise |  nwid  crypt   frag   retry   misc | beacon | 22
wlp4s0: 0000   58.  -52.  -256        0      0      0      1  14241        0
```

**字段含义**:
- 第 2 列:Quality(out of 70) — 信号质量百分比
- 第 3 列:Signal level(dBm,负数,越接近 0 越强) — 用于等级显示

```python
import re
from pathlib import Path

def wifi_signal(iface: str) -> tuple[int, int, int]:
    """返回 (level_dBm, quality_0_70, bars_0_4)"""
    with open("/proc/net/wireless") as f:
        for line in f:
            m = re.match(rf"^\s*{re.escape(iface)}:\s+\S+\s+(\d+)\.\s+(-?\d+)\.", line)
            if m:
                quality, level = int(m.group(1)), int(m.group(2))
                if level >= -50: bars = 4
                elif level >= -60: bars = 3
                elif level >= -70: bars = 2
                elif level >= -80: bars = 1
                else: bars = 0
                return level, quality, bars
    return -100, 0, 0
```

## 5 档 Nerd Font 图标

Material Design Icons (PUA 码位) 阶梯 0 → 4:
- 0 格: U+F08E
- 1 格: U+F08F
- 2 格: U+F090
- 3 格: U+F091
- 4 格(满): U+F092
- 断开: U+F08D

```python
ICON_WIFI = [
    "\uf08e",  # 0 格
    "\uf08f",  # 1 格
    "\uf090",  # 2 格
    "\uf091",  # 3 格
    "\uf092",  # 4 格
]
ICON_WIFI_OFF = "\uf08d"      # 无线断开
```

## waybar text 构造(用户偏好:统一 wifi 风格)

```python
primary = default_dev or (up_ifaces[0][0] if up_ifaces else "net")

if is_wifi(primary):
    level, quality, bars = wifi_signal(primary)
    icon = ICON_WIFI[bars]
    ssid = wifi_ssid(primary) or "WiFi"
    text = f" {icon} {ssid} "
elif primary and not is_wifi(primary):
    # 有线也用 wifi 满格(用户偏好统一风格)
    text = f" {ICON_WIFI[4]} {primary} "
else:
    text = f" {ICON_WIFI_OFF} "
```

**输出示例**(4 格信号):
```
 DrHome
```

## tooltip 完整版(SSID + 信号 + 所有 v4/v6 地址 + DNS)

```python
def cmd_network() -> None:
    hostname = Path("/etc/hostname").read_text().strip()
    fqdn_lan = (run(["hostname", "-f"], timeout=1) or hostname).strip()
    ifaces = parse_ip_addr()  # ip -j addr show 解析
    default_dev, default_gw = parse_ip_route()  # ip -j route show
    ts_dns = parse_tailscale_dns()  # tailscale status --json

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
        extra = ""
        if is_wifi(name):
            level, quality, bars = wifi_signal(name)
            extra = f"  <span size='small' color='#888'>信号 {level} dBm / {quality}/70 · {bars}格</span>"
        lines.append(f"<b>{name}</b>{marker}  <span size='small' color='#888'>{info['state']}</span>{extra}")
        # v4/v6 列表...
```

**tooltip 实际输出**:
```
x1tablet
  LAN:  <span color='#888'>x1tablet.lan</span>
  TS:   <span color='#a78bfa'>x1tablet.tail2e6efb.ts.net</span>

wlp4s0 ★  UP  信号 -49 dBm / 61/70 · 4格
  v4: 192.168.1.249
  v6: 2409:8a00:da0:b160::6d5
tailscale0  UNKNOWN
  v4: 100.66.66.249
  v6: fd7a:115c:a1e0::3e01:d4ca

网关: 192.168.1.1  via wlp4s0
```

## 常见坑

1. **iwd 装了**:`iw dev ... link` 在某些 iwd 实现下输出格式略有不同,fallback 用 `/proc/net/wireless` 拿 dBm 仍有效
2. **dhcpcd 频繁轮询**:`iw` 输出可能在 dhcp 切换瞬间变 "Not connected",这是正常状态,代码里 `if r.returncode != 0: return None` 兜底
3. **SSID 含特殊字符(中文/emoji)**:`SSID:\s+(\S+)` 用 `\S+` 拿整段不会切断,直接用作显示
4. **多 wifi 接口(笔记本 + USB wifi)**:对每个 iface 都跑 `is_wifi()` 检查,挑默认路由那个作为 primary
5. **v6 多地址(link-local + global)**:tooltip 只显示前 2 个 v6 + "v6: +N 更多",避免 tooltip 过长
