# skills/

此目录存放 Hermes 技能定义（SKILL.md），每个技能一个子目录。

命名约定：`<scope>-<topic>` 形式，例如 `sway-waybar-config`。

## 技能索引

所有本地自建技能集中在 `local/` 子目录下：

```
skills/local/
├── apple-icloud-linux         Linux iCloud Drive/Photos 挂载
├── debian-btrfs-system        btrfs 子卷迁移 + Timeshift 快照
├── linux-audio-pipewire       PipeWire 音频诊断
├── linux-system-resource-analysis  系统资源分析
├── python-dockerize           Python Docker 化
├── sway-debian-setup          Sway 安装配置
├── sway-desktop-tuning        Sway 桌面调优
├── uxplay                     AirPlay 投屏服务
├── waybar-config              Waybar 配置
└── wayland-rdp-setup          RDP 远程桌面
```

## 添加新技能

1. 在 `skills/` 下创建子目录
2. 编写 `SKILL.md`（YAML frontmatter + Markdown 正文）
3. 必须包含 `source` 字段指向官方文档 URL
4. 可附带 `references/` 和 `templates/` 子目录
5. 更新本索引
