# API 依赖的 Waybar 自定义模块指南

> 本文件已被整合入主 SKILL.md §「API 依赖模块 — 凭证 + 容错」。
> 更新时优先改主 SKILL.md，此处仅保留核心缩略版供快速参考。

## 凭证传递

Waybar 通过 sway `exec_always` 启动，继承 **sway 进程的环境**，不是 `systemd --user` 的。
因此脚本需做双重 fallback：

```python
import os
from pathlib import Path

ENV_FILE = Path.home() / ".config" / "environment.d" / "99-deepseek.conf"

def _load_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return ""
```

## 优雅降级

```python
def emit_waybar(text, alt, tooltip=""):
    print(json.dumps({"text": text, "alt": alt, "class": alt, "tooltip": tooltip}, ensure_ascii=False))
    sys.exit(0)

def fail_waybar(reason):
    emit_waybar(" ✗", "error", f"<span color='#e74c3c'>采集失败</span>\n{reason}")
```

## CSS

```css
#custom-xxx            { color: #aaa; }
#custom-xxx.error      { color: #e74c3c; }
#custom-xxx.ok         { color: #2d8a4e; }
#custom-xxx.warning    { color: #d2691e; font-weight: bold; }
#custom-xxx.critical   { color: #e05252; font-weight: bold; }
```

## 参考实现

`~/.hermes/skills/local/deepseek-cost/scripts/collect.py`
