# PWA 快捷方式自动发现 (PWA .desktop → waybar `custom/*`)

当用户的 Chrome PWA 多了之后(7-9 个常见:DeepSeek / Hermes / OneNote / NotebookLM / Dynalist / iCloud / Rclone / code-server...),手动给每个写一个 waybar `custom/<name>` 模块很烦。本 reference 给出**自动生成模板**。

## 数据源

所有 PWA 启动器都在 `~/.local/share/applications/chrome-*.desktop`(Chrome 创建的),系统工具在 `/usr/share/applications/*.desktop`。fuzzel 读取的就是这两处,跟用户对 PWA 快捷方式的预期一致。

## 一个 .desktop 长什么样

```
# ~/.local/share/applications/chrome-deepseek.desktop
[Desktop Entry]
Name=DeepSeek - 探索未至之境
Exec=/opt/google/chrome/google-chrome --profile-directory=Default --app-id=gaclnekabaleococgnghmjhcdfipepjj
Icon=chrome-gaclnekabaleococgnghmjhcdfipepjj-Default
StartupWMClass=chrome-gaclnekabaleococgnghmjhcdfipepjj-Default
```

**关键 4 个字段**:
- `Name=` — 显示名(取第一个;同名多 Name 的是 "新建对话" 之类右键菜单项,跳过)
- `Exec=` — waybar `on-click` 直接抄,**不要**改写 `--app-id`
- `Icon=` — waybar `custom/*` 模块不能用图片(GTK Label 不支持),忽略
- `StartupWMClass=` — 仅 `wlr/taskbar` 用,custom 模块不需要

## 自动发现 → waybar 模块的 Python 模板

```python
import re, json
from pathlib import Path

# 1) 列出所有 .desktop(用户 + 系统),并解析
APPS_DIR = Path.home() / ".local/share/applications"
SYSTEM_DIR = Path("/usr/share/applications")

def parse_desktop(path: Path) -> dict:
    """只取第一个 Name= 和 Exec=,过滤菜单项"""
    text = path.read_text(errors="ignore")
    name = exec_cmd = None
    for line in text.splitlines():
        if line.startswith("Name=") and name is None:
            name = line[5:].strip()
        elif line.startswith("Exec=") and exec_cmd is None:
            exec_cmd = line[5:].strip()
            break  # 只取第一个 Exec
    return {"name": name, "exec": exec_cmd, "file": path.name}

# 2) 短名映射(优先用此表,避免从 filename 猜歧义)
SHORT_NAMES = {
    "chrome-deepseek.desktop":     "deepseek",
    "chrome-hermes.desktop":       "hermes",
    "chrome-hermes-webui.desktop": "hermes-webui",
    "rclone-webui.desktop":        "rclone",
    "code-server.desktop":         "code",
    "icloud-photos.desktop":       "icloud",
    "onenote.desktop":             "onenote",
    "notebooklm.desktop":         "notebooklm",
    "dynalist.desktop":           "dynalist",
    "firefox.desktop":             "firefox",
    "foot.desktop":                "term",
    "footclient.desktop":          "term",
    "nautilus.desktop":            "files",
    "google-chrome.desktop":       "chrome",
}

# 3) Nerd Font PUA 码位(用 \u 转义确保不被 strip)
ICONS = {
    "deepseek":     "\uf544",  # robot
    "hermes":       "\uf0e7",  # bolt(信使之神)
    "hermes-webui": "\uf4ac",  # comment-dots
    "rclone":       "\uf0c2",  # cloud
    "code":         "\uf121",  # code
    "icloud":       "\uf03e",  # image
    "onenote":      "\uf02d",  # book
    "notebooklm":   "\uf518",  # book-open
    "dynalist":     "\uf0ca",  # list
    "firefox":      "\uf269",
    "term":         "\ue795",  # terminal
    "files":        "\uf07b",  # folder
    "chrome":       "\uf268",
    "fuzzel":       "\uf002",  # search(独立项,不来自 .desktop)
}

modules = []
for f in sorted(APPS_DIR.glob("*.desktop")) + sorted(SYSTEM_DIR.glob("*.desktop")):
    short = SHORT_NAMES.get(f.name)
    if not short:
        continue
    info = parse_desktop(f)
    if not (info["name"] and info["exec"]):
        continue
    icon = ICONS.get(short, "\uf013")  # 默认 cog
    tooltip = info["name"]
    modules.append({
        f"custom/{short}": {
            "format": f"{icon}  ",
            "on-click": info["exec"],
            "tooltip": True,
            "tooltip-format": tooltip
        }
    })

# 4) 写进 config-top(只动 modules-left 段)
config = json.loads(Path("/home/dr/.config/waybar/config-top").read_text())
config["modules-left"] = ["sway/workspaces", "custom/term", "custom/chrome",
                          "custom/files", "custom/fuzzel"] + \
                         [list(m.keys())[0] for m in modules if list(m.keys())[0] not in config]
for m in modules:
    config.update(m)

# 5) 写入(用 ensure_ascii=False + PUA \u 转义)
Path("/home/dr/.config/waybar/config-top").write_text(
    json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
print(f"✓ 写入 {len(modules)} 个模块")
```

## 验证脚本生效

```bash
# 1. JSON 合法
python3 -c "import json; json.load(open('/home/dr/.config/waybar/config-top')); print('✓ JSON OK')"

# 2. 每个 format 字符串的第一个字符都在 PUA 范围
python3 -c "
import json
d = json.load(open('/home/dr/.config/waybar/config-top'))
for k in d.get('modules-left', []):
    if not k.startswith('custom/'): continue
    fmt = d[k].get('format', '')
    cp = ord(fmt[0]) if fmt else 0
    ok = 0xE000 <= cp <= 0xF8FF
    print(f'  {\"✓\" if ok else \"✗\"} {k:22}  U+{cp:04X}')"
```

## 短名命名规则

- **优先**用语义短名(`deepseek` > `chrome_gaclneka`)
- **避免** chrome 内部的 24/32 字符 app-id
- **同名去重**:某些 .desktop 含多个 `Name=`(右键菜单项),用 `parse_desktop` 里的 `name is None` 守卫取第一个
- **多 profile**:`Exec=` 里的 `--profile-directory=Default` 一定要保留(用户的 PWA 在 Default profile),改 Profile 会找不到

## 已有 PWA 的快速发现命令

```bash
# 列出所有用户 PWA
ls ~/.local/share/applications/chrome-*.desktop

# 一次性 dump 所有相关字段(用于生成模块)
for f in ~/.local/share/applications/chrome-*.desktop; do
  echo "===== $(basename $f) ====="
  grep -E "^(Name|Exec|StartupWMClass)=" "$f" | head -3
  echo
done
```

## 已知坑

1. **`chrome-hermes-webui.desktop` 可能有 2 个 `Name=`:**
   第一个是主入口("Hermes"),第二个是右键菜单("New conversation")。`parse_desktop` 的 `name is None` 守卫只取第一个 — 正确。

2. **某些 PWA `.desktop` 缺 `StartupWMClass=`:**
   缺失时 `wlr/taskbar` 显示该 PWA 窗口为 Chrome 图标。这是 Chrome 的 bug,不是 waybar 修得了的。**左侧 custom 按钮仍可用**。

3. **重命名 .desktop 不破坏快捷方式:**
   `chrome-<appid>.desktop` → `deepseek.desktop` 完全 OK。`Exec=` 里的 `--app-id=` 是稳定的,fuzzel 和 waybar 都按 app-id 识别,跟文件名无关。

4. **新增 PWA 后:**
   - 重跑上面的 Python 模板(或手动加 `custom/<name>` 块到 config-top)
   - `killall waybar && waybar -c config-top &` 不需要(waybar 重读配置),但新模块要等下次 waybar 启动

## 完整生产版参考

本用户当前的 `~/.config/waybar/config-top` 就是这个模板的实例化版(2026-06-16)。9 个 PWA + 4 个系统工具 = 13 个 `custom/*` 模块在 `modules-left`,全部带 Nerd Font 图标 + 中文 tooltip。

如需要扩到更多 PWA,改 `SHORT_NAMES` / `ICONS` 两个 dict 即可。
