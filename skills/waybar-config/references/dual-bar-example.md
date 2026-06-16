# Waybar 双栏配置参考（分文件版）

## 文件结构

```
~/.config/waybar/
├── config-top          # 顶部状态栏，单个 {}
├── config-bottom       # 底部 dock，单个 {}
├── style.css           # 共用样式
└── *.bak.*
```

## sway config

```bash
# 两个独立进程
exec_always bash -c 'killall waybar 2>/dev/null; sleep 0.3; \
  GTK_TOOLTIP_TIMEOUT=0 waybar -c ~/.config/waybar/config-top & \
  GTK_TOOLTIP_TIMEOUT=0 waybar -c ~/.config/waybar/config-bottom &'
```

## CSS 注意

两个实例共享 style.css。window#waybar 匹配两者，最后一条背景色规则覆盖前者。
不要用 window#waybar { background: transparent; } 覆盖底部 dock——改用模块唯一选择器。

## 布局

```
顶部栏 (top, 24px, 独占):
  left:   sway/workspaces
  center: sway/window | custom/term | custom/chrome | custom/files | custom/fuzzel
  right:  temperature | cpu | memory | pulseaudio | bluetooth | network | custom/tailscale | clock

底部 Dock (bottom, 48px, 浮动, 自适应宽度):
  left:   custom/deepseek | custom/hermes | ... (8 PWA 图标按钮)
  center: wlr/taskbar
  right:  custom/os_button (fuzzel)
```

## 关键配置

### wlr/taskbar（窗口栏）
- 图标来源: 窗口 window_icon > icon-theme > 回退
- Chrome PWA 不设 window_icon，需 icon-theme: hicolor
- window_icon 确认: swaymsg -t get_tree | grep window_icon

### GTK tooltip 即时显示
推荐 GTK_TOOLTIP_TIMEOUT=0 环境变量，settings.ini 在 sway 下可能不生效。

### 分隔线
```css
#taskbar { border-left: 2px solid #555; padding-left: 6px; margin-left: 6px; }
```

## PWA 图标生效步骤

1. 确认 app_id: swaymsg -t get_tree | grep 'chrome-.*-Default'
2. 确认图标文件: ls ~/.local/share/icons/hicolor/32x32/apps/chrome-<appid>-Default.png
3. 重建缓存: gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor/
4. .desktop 设置 StartupWMClass=chrome-<appid>-Default
5. wlr/taskbar 设置 icon-theme: hicolor
6. 重启 waybar

## 已知限制

- custom/ 模块无法显示图片图标（GTK Label 控件限制）
- Chrome PWA window_icon=(not set)（Wayland 行为）
- 两个 waybar 实例共用 CSS，window#waybar 无法用 :last-child 区分
