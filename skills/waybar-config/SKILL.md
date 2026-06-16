---
name: waybar-config
title: Waybar 配置参考
description: "Waybar 配置参考：模块文档、custom/* JSON 协议、Pango tooltip、API 凭证、常见陷阱。"
version: 2.1.1
author: Hermes Agent → mcpSway
source: https://github.com/Alexays/Waybar/wiki
platforms: [linux]
metadata:
  hermes:
    tags: [waybar, sway, wayland, bar, config]
    related_skills: [sway-debian-setup, sway-desktop-tuning, deepseek-cost]
  principles:
    - "官方文档优先：man 5 waybar-<module> / GitHub Wiki"
    - "来源已注明：所有配置均来自官方 wiki / man page"
    - "经验验证：本技能内容经过 dr@x1tablet 的 Debian 13 + sway 1.10.1 + waybar v0.12.0 环境验证"
---

# Waybar 配置参考

当前版本: **v0.12.0** (Debian 13 trixie)
配置格式: **JSONC**（支持 `//` `/* */`）
样式: GTK3 CSS（不支持 `::after`/`::before`）

## 参考资料

- [GitHub Wiki](https://github.com/Alexays/Waybar/wiki)
- 本地 man: `man 5 waybar-<module>` (e.g. `waybar-custom`, `waybar-pulseaudio`)

---

## 双栏布局

**推荐拆分两个文件**，每个文件是单 `{}`，不是数组：

```
~/.config/waybar/
├── config-top        # 顶部栏
├── config-bottom     # 底部 dock
└── style.css         # 共享样式
```

sway 启动：

```bash
exec_always bash -c 'killall waybar 2>/dev/null; sleep 0.3; \
  GTK_TOOLTIP_TIMEOUT=0 waybar -c ~/.config/waybar/config-top & \
  GTK_TOOLTIP_TIMEOUT=0 waybar -c ~/.config/waybar/config-bottom &'
```

手动重启：

```bash
killall waybar 2>/dev/null
GTK_TOOLTIP_TIMEOUT=0 waybar -c ~/.config/waybar/config-top &
```

**注意：** `swaymsg reload` 不会重执行 `exec_always`，改 config 后必须手动重启。

---

## 常用模块

### sway/workspaces

```json
"sway/workspaces": { "all-outputs": true }
```

### sway/window

```json
"sway/window": { "max-length": 50, "rewrite": { "^(?!.*\\S).*": "浏览器" } }
```

### wlr/taskbar

```json
"wlr/taskbar": { "format": "{icon}", "icon-size": 32, "icon-theme": "hicolor", "on-click": "activate" }
```

### pulseaudio

```json
"pulseaudio": {
  "format": "{icon} {volume}%",
  "on-click": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
  "on-scroll-up": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.05+",
  "on-scroll-down": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.05-"
}
```

### bluetooth

```json
"bluetooth": {
  "format": " {status}",
  "format-connected": " 已连", "format-disabled": " 关闭",
  "on-click": "blueman-manager", "tooltip": true
}
```

### network（内置）

```json
"network": { "format-wifi": "{essid}", "format-ethernet": " {ifname}", "format-disconnected": "" }
```

内置模块拿不到 SSID 时装 `iw`：`sudo apt install iw`

---

## custom/ 自定义模块

### 静态按钮

```json
"custom/term": { "format": "  ", "on-click": "foot", "tooltip": false }
```

底层是 GTK Label，只能文字/Nerd Font，不能图片。

### 动态脚本

**配置：**

```json
"custom/xxx": {
  "exec": "/path/to/script.py",
  "return-type": "json",
  "interval": 5,
  "tooltip": true
}
```

**脚本输出 JSON：**

```json
{ "text": "显示文字", "alt": "状态简码", "class": "状态全名", "tooltip": "多行\n富文本" }
```

字段说明：
- `text`: **必须**，状态栏文字
- `alt` / `class`: CSS class 路由，class 支持数组
- `tooltip`: hover 显示，Pango 标记
- `percentage`: 0-100 数值

`return-type` 可选值：`json`（推荐）/ 空（i3blocks 三行输出）/ `txt` / `raw`

### interval 参考

| 场景 | interval | 说明 |
|------|----------|------|
| 本地监控（CPU/内存） | 1-5s | 无网络 |
| 低频状态（网络） | 8-30s | |
| API 轮询 | 60-300s | 受 rate limit 约束 |
| 信号触发 | `"once"` + signal | `pkill -RTMIN+N waybar` |

### exec-if

```json
"custom/spotify": { "exec": "script.sh", "exec-if": "pgrep spotify" }
```

exit code 0 才执行 `exec`。

---

## Tooltip 机制

### 正确用法

```json
"tooltip": true
```

脚本 JSON 输出 `tooltip` 字段。waybar 通过 `label_.set_tooltip_markup(tooltip_)` 渲染。

### 关键规则

1. **不要加 `tooltip-format: "{tooltip}"`** — man 明确说明 tooltip-format **会覆盖** JSON 输出的 tooltip
2. **Pango 转义** — `set_tooltip_markup()` 将 `<` `>` 当作标签。动态数据中有 `< 1h` 时解析失败，静默丢弃 tooltip
3. **修正在 Python 中**：
   ```python
   import html
   esc = html.escape
   tooltip_lines = [
       "<b>标题</b>",
       f"  数值: <b>¥{amount:.2f}</b>",
       f"  <span color='#888'>{esc(detail)}</span>",  # 动态数据必须 esc()
   ]
   tooltip = "\n".join(tooltip_lines)
   ```
4. v0.12.0 源码分支（`src/modules/custom.cpp` `update()`）：
   - `tooltip_format_enabled_` → 用 tooltip-format 覆盖
   - `text_ == tooltip_` → 用 `str`（format 结果）做 tooltip
   - 否则 → 用 `tooltip_`（JSON 的 tooltip 字段）

### Pango 标记参考

| 用途 | 标记 |
|------|------|
| 主标签 | `<b>名称</b>` |
| 弱化文字 | `<span color='#888'>...</span>` |
| 小字 | `<span size='small' color='#888'>...</span>` |
| 告警 | `<span color='#e74c3c'>...</span>` |

### 延迟

```bash
GTK_TOOLTIP_TIMEOUT=0 waybar
```

---

## API 依赖模块

### 凭证传递

Waybar 继承 **sway 进程环境**，不是 `systemd --user`。`environment.d` 和 `import-environment` 无效。

脚本必须做文件回退：

```python
ENV_FILE = Path.home() / ".config" / "environment.d" / "99-deepseek.conf"

def _load_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY=***                return line.split("=", 1)[1].strip().strip("\"'")
    return ""
```

### 优雅降级

```python
def emit_waybar(text, alt, tooltip=""):
    print(json.dumps({"text": text, "alt": alt, "class": alt, "tooltip": tooltip}, ensure_ascii=False))
    sys.exit(0)

def fail_waybar(reason):
    emit_waybar(" ✗", "error", f"<span color='#e74c3c'>采集失败</span>\n{reason}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        fail_waybar(str(e))
```

### Dual-mode 架构（Waybar + Cron 共用）

```
skill-name/
├── scripts/collect.py   # --waybar → Waybar JSON; 无参数 → cron JSON
└── data/history.json    # 持久化，保留最近 N 条，同分钟同值去重
```

```json
"custom/xxx": { "exec": "python3 scripts/collect.py --waybar", "return-type": "json", "interval": 300, "tooltip": true }
```

完整示例：`deepseek-cost` skill。

---

## PWA 图标

### wlr/taskbar 图标解析路径

```
app_id → 搜索 {prefix}/applications/{app_id}.desktop → Icon 字段 → icon-theme 查询
```

### PWA 显示 Chrome 图标

**根因**：`.desktop` 文件名不匹配 app_id（PWA app_id 为 `chrome-{32字符}-Default`）

**修复**：创建符号链接

```bash
ln -sf deepseek.desktop chrome-{appid}-Default.desktop
```

**验证**：

```bash
swaymsg -t get_tree | python3 -c "
import json,sys; d=json.load(sys.stdin)
def f(n):
    aid=n.get('app_id','')
    if 'chrome-' in aid: print(f'app_id={aid}')
    for k in ['nodes','floating_nodes']: [f(c) for c in n.get(k,[])]
f(d)
"
```

### 判断 Chrome 自动 vs 用户手建

```python
import re
if re.match(r"^chrome-.{16,}-Default\\.desktop$", name, re.I):
    continue  # Chrome 自动生成，跳过
```

文件名正则（32 字符 base32 appid）是**唯一可靠**方法，文件大小/行数/内容字段都不可靠。

---

## CSS 要点

### 选择器

- 模块：`#custom-<name>` / `#custom-<name>.<class>`
- taskbar：`#taskbar button` / `#taskbar button.active`
- 分隔线用 CSS border，不用 custom/ 模块

### 状态着色

```css
#custom-deepseek-cost.ok         { color: #2d8a4e; }
#custom-deepseek-cost.warning    { color: #d2691e; font-weight: bold; }
#custom-deepseek-cost.critical   { color: #e05252; font-weight: bold; }
#custom-deepseek-cost.error      { color: #e05252; }
```

### 统一 icon+data 格式

右侧模块：`[Nerd Font 图标] [数据]`

| 模块 | text 示例 | 图标 |
|------|-----------|------|
| 温度 | ` 73°C` |  |
| CPU | ` 47%` |  |
| 内存 | ` 64%` |  |
| 音量 | ` 60%` |  高/中/低 |
| 网络 | ` DrHome` | wifi 格数 |
| Tailscale | ` 6` |  |
| DeepSeek 余额 | ` ¥14.93` |  |

---

## 配置文件路径

```
~/.config/
├── sway/config                  # exec_always waybar
├── waybar/
│   ├── config-top               # 顶部栏 JSONC
│   ├── config-bottom            # 底部 dock JSONC
│   └── style.css                # 共享样式
├── environment.d/
│   └── 99-deepseek.conf         # API 凭证
└── local/bin/waybar-status.py   # 统一入口脚本
```

---

## 陷阱

| # | 问题 | 原因 | 解决 |
|---|------|------|------|
| 1 | tooltip 不显示 | 动态数据含 `<`（如 `< 1h`），Pango 解析失败 | `html.escape()` 转义 |
| 2 | tooltip 不更新 | 加了 `tooltip-format: "{tooltip}"` | 去掉，JSON 输出 `tooltip` 字段即可 |
| 3 | 采集失败 | API key 不在 waybar 环境 | 脚本加 `environment.d` 文件回退 |
| 4 | 图标方块 | 缺 Nerd Font | 安装 NerdFontsSymbols |
| 5 | custom/* 按钮空 | format 中 Nerd Font PUA 被 write_file 过滤 | 用 patch 或 Python `\u` 转义 |
| 6 | 按钮报 not found | `on-click` 二进制没装 | `which` 验证 |
| 7 | taskbar PWA 显示 Chrome 图标 | .desktop 文件名不匹配 app_id | 创建 symlink |
| 8 | `load()` 报错 | JSONC 含 `//` 注释 | 用 `json5` 包验证 |

### Nerd Font 安装

```bash
curl -fL -o /tmp/NerdFontsSymbolsOnly.zip \
  https://github.com/ryanoasis/nerd-fonts/releases/download/v3.3.0/NerdFontsSymbolsOnly.zip
mkdir -p ~/.local/share/fonts/NerdFontsSymbols
unzip -o /tmp/NerdFontsSymbolsOnly.zip -d ~/.local/share/fonts/NerdFontsSymbols
fc-cache -fv
```

CSS：`font-family: "Symbols Nerd Font", "Noto Sans CJK SC", "Noto Sans", sans-serif;`

### Nerd Font PUA 被过滤

```python
import json
d = json.load(open('/home/dr/.config/waybar/config-top'))
d['custom/term']['format'] = '\ue795  '  # 用 \u 转义
open('/home/dr/.config/waybar/config-top', 'w').write(json.dumps(d, indent=2, ensure_ascii=False) + '\n')
```

`patch` 工具不受此问题影响。

---

## 调试

```bash
# 1. 单测脚本
python3 script.py --waybar | python3 -m json.tool

# 2. 验证 JSON 字段 + Pango 合规
python3 script.py --waybar | python3 -c "
import json,sys
d = json.load(sys.stdin)
print('text:', d.get('text'), 'class:', d.get('class'))
print('tooltip has unescaped <:', '<' in d.get('tooltip','') and '&lt;' not in d.get('tooltip',''))
"

# 3. 模拟 waybar 环境（无继承变量）
env -i HOME=\"$HOME\" PATH=\"$PATH\" python3 script.py --waybar

# 4. 重启看日志
killall waybar 2>/dev/null; GTK_TOOLTIP_TIMEOUT=0 waybar -c ~/.config/waybar/config-top 2>&1

# 5. 配置验证
python3 -c "import json; json.load(open('/home/dr/.config/waybar/config-top')); print('✅')"
```
