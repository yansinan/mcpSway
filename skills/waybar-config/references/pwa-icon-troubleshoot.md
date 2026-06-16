# PWA 图标解析 + 启动排查

## 问题 A: 启动打不开/打开空白页

**症状**:点击 waybar 的 `custom/<pwa>` 按钮或 fuzzel 启动 `.desktop`,Chrome 弹新窗口但页面是空白(显示 `chrome://newtab` 或 `chrome-error://...`),或者完全没反应。

**根因**:`.desktop` 里的 `Exec=` 写错了 `--user-data-dir` 或 `--profile-directory`。PWA 实际上装在另一个 Chrome profile 里(常见:用户在 `~/.hermes/chrome-debug` 装了一个独立的 Chrome 实例),但 `.desktop` 指向 `~/.config/google-chrome/Default`,所以 Chrome 找不到这个 PWA。

**诊断**(找出 PWA 实际装在哪个 profile):

```bash
# 1) 找哪个 profile 的 Preferences 包含目标 app-id
APP_ID="gaclnekabaleococgnghmjhcdfipepjj"  # 替换为 .desktop 里 Exec= 的 --app-id
find ~/.config/google-chrome ~/.hermes/chrome-debug -name "Preferences" \
  -exec grep -l "$APP_ID" {} \;
# 输出: /home/dr/.hermes/chrome-debug/Default/Preferences
# → 这个 PWA 装在 Hermes-Debug profile,不是 Default
```

**修复**两种方式:

**方式 A:改 `.desktop` 自己的 Exec=** (影响 fuzzel 和 waybar)
```bash
# 把 --profile-directory=Default 改成正确的 profile
sed -i 's|--profile-directory=Default|--user-data-dir=/home/dr/.hermes/chrome-debug --profile-directory=Default|' \
  ~/.local/share/applications/chrome-<name>.desktop
```

**方式 B:只改 waybar 的 `on-click`** (不动 .desktop)
```python
# 改 config-top 里 custom/<pwa> 的 on-click
import json
d = json.load(open('/home/dr/.config/waybar/config-top'))
d['custom/hermes']['on-click'] = (
    "/opt/google/chrome/google-chrome "
    "--user-data-dir=/home/dr/.hermes/chrome-debug "  # 加上这个
    "--profile-directory=Default "
    "--app-id=ggodlfkjnmplcjoknpmbaadcecnfflfd"
)
```

**如何预先避免**:从 fuzzel 验证桌面文件能正常打开 — 如果 fuzzel 里点击 `.desktop` 弹窗空白,Exec= 就一定写错了。**先 fuzzel 验证再写进 waybar**,不要直接从 `.desktop` 文件抄 Exec= 然后假设它能跑。

**多 profile 命名约定**(本用户):
- `~/.config/google-chrome/Default` — 日常浏览
- `~/.hermes/chrome-debug/Default` — Hermes / 调试用独立 Chrome(防止和日常 profile cookie 串)

NotebookLM 在 `chrome-debug` 启动,理由:`--user-data-dir=/home/dr/.hermes/chrome-debug --profile-directory=Default --app-id=gjcmcplpgihbecacndmmbaenpfgimlec`。

## 问题 B: wlr/taskbar 中显示 Chrome 图标而非 PWA 图标

### 1. 检查窗口属性

```bash
swaymsg -t get_tree | python3 -c "
import json,sys
data = json.load(sys.stdin)
def find(n):
    if not isinstance(n,dict): return
    aid = n.get('app_id','') or ''
    if 'chrome-' in aid and '-Default' in aid:
        print(f'app_id={aid}  window_icon={n.get(\"window_icon\",\"(not set)\")}')
    for k in ['nodes','floating_nodes']:
        for c in n.get(k,[]): find(c)
find(data)
"
```

- `window_icon=(not set)` → Chrome 没提供窗口图标，Waybar 必须靠 app_id 在 icon-theme 中查找
- `window_icon=...` → Chrome 提供了图标，问题可能在其他地方

### 2. 验证 GTK 能否找到图标

```python
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
theme = Gtk.IconTheme.get_default()
app_id = 'chrome-<appid>-Default'
info = theme.lookup_icon(app_id, 32, 0)
if info:
    print(f'✅ found -> {info.get_filename()}')
else:
    print('❌ not found — run: gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor/')
```

### 3. 验证 .desktop 文件可被 app_id 找到

Waybar 源码中 wlr/taskbar 的图标解析路径(来自 `src/util/icon_loader.cpp`):

```
app_id → get_app_info_from_app_id_list(app_id)
       → get_desktop_app_info(app_id)
       → get_app_info_by_name(app_id)
       → 搜索 {prefix}/applications/{app_id}.desktop
       → 读 DesktopAppInfo.get_icon() → 在 icon-theme 中查找
```

搜索的文件名就是 app_id 本身(不加 `.desktop` 后缀也试)。如果你的 `.desktop` 文件重命名成了可读名(如 `deepseek.desktop`),而 app_id 是 `chrome-<appid>-Default`,就找不到!

**修复:创建符号链接**

```bash
ln -sf deepseek.desktop chrome-<appid>-Default.desktop
```

### 4. 验证 wlr/taskbar 配置

```json
"wlr/taskbar": {
  "icon-theme": "hicolor",     // 必须
  "icon-size": 32,             // 与 hicolor 中的图标尺寸匹配
  ...
}
```

### 5. 验证 .desktop 的 Icon 字段

```bash
grep "^Icon=" ~/.local/share/applications/chrome-*.desktop
```

Icon 值应该是 `chrome-<appid>-Default`,与 hicolor 中的文件名匹配。

## 完整排查脚本

```bash
#!/bin/bash
# 检查指定 app_id 的图标解析
app_id="$1"
echo "=== app_id: $app_id ==="

# 检查 .desktop 文件
echo "--- .desktop 文件 ---"
for d in ~/.local/share/applications /usr/share/applications; do
    f="$d/$app_id.desktop"
    if [ -f "$f" ]; then
        echo "  ✅ $f -> $(grep '^Icon=' "$f" | head -1)"
    elif [ -L "$f" ]; then
        echo "  🔗 $f -> $(readlink -f "$f") -> $(grep '^Icon=' "$f" | head -1)"
    fi
done

# 检查图标文件
echo "--- 图标文件 ---"
for size in 32x32 48x48 128x128; do
    f="$HOME/.local/share/icons/hicolor/$size/apps/$app_id.png"
    [ -f "$f" ] && echo "  ✅ $f" || true
done

# 检查 GTK 能找
python3 -c "
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
theme = Gtk.IconTheme.get_default()
info = theme.lookup_icon('$app_id', 32, 0)
if info: print(f'  ✅ GTK: {info.get_filename()}')
else: print('  ❌ GTK not found')
"
```

## 典型根因

| 症状 | 根因 | 修复 |
|------|------|------|
| PWA 按钮点击后空白页 | `.desktop` Exec= 写错 profile(见问题 A)| 改 .desktop 或 waybar on-click |
| 所有 PWA 窗口都显示 Chrome 图标 | 删除了 app_id 名称的 .desktop 文件 | 创建 symlink |
| 仅某个 PWA 显示 Chrome 图标 | 该 PWA 的 app-id 被误删或改名未建 symlink | 检查并创建 symlink |
| 之前能显示,我改了某些东西后不显示 | `.desktop` 文件改名/删除/修改导致不匹配 | 恢复 app_id 对应的符号链接 |
| GTK 能找到图标但 waybar 不显示 | icon-theme 配置缺失 | 加 `"icon-theme": "hicolor"` |
| custom/* 按钮显示空 padding 而非图标 | Nerd Font PUA 码位被 `write_file` 过滤 | 用 Python `\u` 转义重写 |

## 一句话总结

- **打不开**:看 `.desktop` 的 `--user-data-dir` / `--profile-directory` 是不是写错(用 `find ... -name Preferences -exec grep` 找 PWA 实际位置)
- **图标错**:看 `.desktop` 文件名是不是和 app_id 不一致(创建 symlink 修复)
- **图标空白**:看 `format` 字段的 Nerd Font PUA 码位是不是被 `write_file` 过滤(用 Python `\u` 重写)
