# Sway 双屏配置（ThinkPad X1 Tablet + 外接 4K）

本会话实际配置。硬件：Intel UHD Graphics 620, Debian 13, sway 1.10.1。

## 获取输出名称

```bash
# 在 Sway 中
swaymsg -t get_outputs

# 或从 TTY
sudo -u dr env XDG_RUNTIME_DIR=/run/user/1000 wlr-randr
```

## 实测配置

```bash
cat ~/.config/sway/config
```

```
# eDP-1: 3000x2000 内置屏
# DP-3:  3840x2160 外接 4K

output DP-3 mode 3840x2160@60Hz position 3000 0
output eDP-1 mode 3000x2000@60Hz position 0 0

workspace 1 output DP-3
workspace 2 output eDP-1
workspace 3 output DP-3
workspace 4 output eDP-1
workspace 5 output DP-3

bindsym $mod+Return exec foot
bindsym $mod+d exec bemenu-run
bindsym $mod+Shift+q kill

bindsym $mod+Left focus left
bindsym $mod+Right focus right
bindsym $mod+Up focus up
bindsym $mod+Down focus down

include /etc/sway/config
```

## 注意事项

- `$mod` 默认是 Mod4（Super/Windows 键）
- `include /etc/sway/config` 会带入 Debian 默认配置（含 vim 方向键 $mod+h/j/k/l、状态栏、音量/亮度键等）
- 应用启动器推荐 `bemenu-run`（Wayland 原生）而非 `dmenu_run`（X11）
- 配置文件修改后 sway 内按 **Mod+Shift+C** 重载
