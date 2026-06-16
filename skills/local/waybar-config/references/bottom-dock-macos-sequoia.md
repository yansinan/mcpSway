# macOS Sequoia 风格底部 Dock 配置参考

## 参考项目

https://github.com/kamlendras/waybar-macos-sequoia

该项目底部 dock **没有 PWA 快捷按钮**。只有：
- 左侧: custom/os_button（搜索，wofi --show drun）
- 中间: sway/mode + wlr/taskbar（运行中的窗口）

## 我们的扩展设计（用户要求）

```
左侧: PWA 纯图标按钮 (Nerd Font 字形, 8 个)
中间: wlr/taskbar (运行中的窗口)
右侧: custom/os_button (fuzzel 启动器)
```

## 自适应宽度

需要添加 width/margin 让 dock 居中浮动，不是通栏：

```json
"width": 2,
"margin": "4",
"spacing": 5
```

## 关键限制

- custom/ 模块无法显示图片图标（GTK Label 控件限制）
- Chrome PWA 窗口在 Wayland 下不设置 window_icon（swaymsg 确认 window_icon=not set）
- PWA 按钮只能用 Nerd Font 字形代替图像图标
- wlr/taskbar 显示运行中的窗口（含 PWA），但图标来自 Chrome 默认

## 图标选择

```
DeepSeek     
Hermes       
Rclone       
code-server  
iCloud       
OneNote      
NotebookLM   
Dynalist     
```

## 完整 JSON

```json
{
  "layer": "top",
  "position": "bottom",
  "exclusive": false,
  "height": 48,
  "width": 2,
  "margin": "4",
  "spacing": 5
}
```

## 关键 CSS

```css
#custom-deepseek, #custom-hermes, ... { padding: 0 6px; font-size: 16px; color: #999; }
#taskbar { border-left: 2px solid #555; padding-left: 6px; margin-left: 6px; }
#taskbar button.active { border-bottom: 3px solid #5294e2; }
#taskbar button:not(.active) { border-bottom: 3px solid rgba(255,255,255,0.2); }
```
