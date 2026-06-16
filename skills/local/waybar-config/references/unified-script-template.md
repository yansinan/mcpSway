# Waybar 统一入口脚本模板

适用场景:有 ≥2 个 custom/* 模块用脚本输出，且想避免散落多个 `~/.local/bin/*-status.sh`。

## 设计原则

- **单一入口** + **子命令路由**:`script.py <module1> <module2> ...`
- **统一 emit() 助手**:所有模块走同一 JSON 输出格式
- **冷启动 <200ms**:`interval ≥ 5s` 时 Python 启动开销可忽略
- **失败优雅降级**:不抛 traceback 到 stderr(避免污染 sway 日志)
- **Pango 标记一致性**:颜色/字号惯例见下文

## JSON 输出规范

```json
{
  "text":    "TS 6",                            // 状态栏文字
  "alt":     "online",                          // 状态简码 → CSS class
  "class":   "online",                          // DOM class（同 alt）
  "tooltip": "<b>x1tablet.tailX.ts.net</b>..."  // Pango 多行
}
```

**字段语义:**
- `text`:必须,显示文字(可空字符串,模块会"消失")
- `alt`:建议填,作为 CSS class 路由
- `class`:可省,默认与 alt 相同
- `tooltip`:可省,但要 Pango 标记才好看

## Pango 颜色/字号惯例

| 用途 | 标记 |
|------|------|
| 主标签 | `<b>名称</b>` |
| 弱化文字 | `<span color='#888'>...</span>` |
| 小字补充 | `<span size='small' color='#888'>...</span>` |
| 状态色-在线 | `<span color='#8fc9a8'>...</span>`(绿)|
| 状态色-离线 | `<span color='#777'>...</span>`(灰)|
| 状态色-异常 | `<span color='#a78bfa'>...</span>`(紫)|

CSS class 颜色(配合 `alt` 字段):
```css
#custom-xxx         { color: #aaa; }
#custom-xxx.online  { color: #2d8a4e; font-weight: bold; }
#custom-xxx.offline { color: #555; }
#custom-xxx.abnormal{ color: #8a3fd1; font-weight: bold; }
```

## 模板代码

```python
#!/usr/bin/env python3
"""Waybar 状态脚本 — 统一入口

用法: waybar-status.py <module1> <module2> ...
输出 JSON 给 Waybar custom 模块

设计:
    - 每个子命令 < 200ms 完成
    - 失败时优雅降级,绝不抛 traceback
    - 错误信息走 stderr(不污染 waybar JSON 解析)
"""
import json
import subprocess
import sys
from pathlib import Path


# ─── 工具函数 ───────────────────────────────────────
def emit(text: str, alt: str, tooltip: str) -> None:
    """统一 JSON 输出"""
    print(json.dumps({
        "text": text,
        "alt": alt,
        "class": alt,
        "tooltip": tooltip
    }, ensure_ascii=False))
    sys.exit(0)


def run(cmd: list[str], timeout: float = 2.0) -> str:
    """subprocess 简化封装,失败返回空串"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


# ─── 模块实现 ───────────────────────────────────────
def cmd_module1() -> None:
    """第一个模块示例"""
    try:
        # ... 采集数据 ...
        data = run(["some", "command"])
        # ... 解析 ...
        emit("hello", "online", "<b>title</b>\n<span color='#888'>detail</span>")
    except Exception as e:
        emit("✗", "error", f"采集失败: {e}")


def cmd_module2() -> None:
    """第二个模块示例"""
    emit("X%", "normal", "...")


# ─── 入口路由 ───────────────────────────────────────
COMMANDS = {
    "module1": cmd_module1,
    "module2": cmd_module2,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(f"用法: {sys.argv[0]} <{'|'.join(COMMANDS)}>", file=sys.stderr)
        sys.exit(1)
    try:
        COMMANDS[sys.argv[1]]()
    except Exception as e:
        emit("✗", "error", f"脚本异常: {e}")
```

## 配套 waybar config 写法

```jsonc
"modules-right": ["custom/module1", "custom/module2", "clock"],

"custom/module1": {
  "exec": "/home/dr/.local/bin/waybar-status.py module1",
  "return-type": "json",
  "interval": 5,
  "tooltip": true
},
"custom/module2": {
  "exec": "/home/dr/.local/bin/waybar-status.py module2",
  "return-type": "json",
  "interval": 30,
  "tooltip": true,
  "on-click": "foot -e bash -c '...; read'"
}
```

## 常见陷阱

1. **变量名 `out` 与函数 `emit` 冲突** — 早期版本用 `out` 当变量名,后来和 `def out()` 冲突。统一用 `emit()` 函数
2. **`/proc/PID/status` 的 `Name:\t{name}\n` 字段** — 开头没有 leading newline,不能直接 `in content` 搜索。改用 `pgrep -x NAME` + 读对应 PID 的 status 文件
3. **`hostname -f` 输出末尾带 `\n`** — 用 `.strip()` 处理
4. **`sensors -j` 的 NVMe adapter** 有 Composite + Sensor 1/2 三个值,只输出 Composite
5. **`/sys/class/hwmon/*/name` 读失败** — 某些条目可能是空目录或权限受限,用 `Path.exists()` 提前过滤
6. **CSS 文件被 sway 重载/外部进程重写** — 编辑前先 `cp style.css{,.bak.$(date +%F)}`

## 调试流程

```bash
# 1. 单测子命令输出格式
~/.local/bin/waybar-status.py module1 | python3 -m json.tool

# 2. 验证 Pango 标记无语法错误(waybar 自己会忽略无效标记)
# 把 tooltip 贴进 gtk3-demo 的 label 试试

# 3. 重启 waybar 应用(见主 SKILL.md reload 章节)
killall waybar && (GTK_TOOLTIP_TIMEOUT=0 waybar &)

# 4. 看启动日志
waybar 2>&1 | tee /tmp/waybar.log
```
