# skills/

此目录存放 Hermes 技能定义（SKILL.md），每个技能一个子目录。

命名约定：`<scope>-<topic>` 形式，例如 `sway-waybar-config`。

## 技能索引

| 技能 | 描述 | 来源 |
|------|------|------|
| `waybar-config` | Waybar 配置参考：双栏布局、模块、custom/* JSON、Pango tooltip、API 凭证、PWA 图标、CSS、陷阱、调试 | 官方 Wiki + man page |
| `sway-debian-setup` | Sway 安装配置（Debian）：显示管理、fcitx5 输入法、蓝牙、会话保存/恢复 | swaywm.org + man pages |
| `sway-desktop-tuning` | Sway 桌面调优：swayidle 配置陷阱、S0ix 电源、PipeWire 音频诊断、HDA 引脚调试 | sway man page + Arch Wiki |
| `linux-audio-pipewire` | PipeWire/WirePlumber 音频诊断命令、ADMI/DP 音频问题、蓝牙音频 | Arch Wiki PipeWire |
| `uxplay` | UxPlay AirPlay 投屏服务：Debian 安装、sway 集成、常见坑点 | GitHub FDH2/UxPlay |
| `debian-btrfs-system` | Debian btrfs 系统管理：@rootfs → @/@home 子卷迁移、Timeshift btrfs 快照、GRUB/LVM 引导修复 | timeshift GitHub + Arch Wiki btrfs |

## 添加新技能

1. 在 `skills/` 下创建子目录
2. 编写 `SKILL.md`（YAML frontmatter + Markdown 正文）
3. 必须包含 `source` 字段指向官方文档 URL
4. 可附带 `references/` 和 `templates/` 子目录
5. 更新本索引
