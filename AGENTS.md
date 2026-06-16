# AGENTS.md — mcpSway 仓库 AI Agent 工作指南

本文档是 AI Agent（Hermes、Claude Code 等）在操作此仓库时的行为准则。任何代理人（Agent）在执行本仓库内的任务前，必须首先阅读并遵守本文件。

---

## 仓库范围

Sway 桌面环境相关的配置、脚本、技能定义仓库。

**目录结构：**

```
mcpSway/
├── skills/
│   └── local/      # Hermes 技能定义（SKILL.md），每个子目录一个技能
├── scripts/         # 实用脚本（sway-session 等，带中文注释）
├── configs/         # 参考配置（sway/ waybar/ wofi/ mako/ fcitx5/ systemd/ environment/）
├── docs/            # 文档与笔记（硬件信息、已知问题、workaround）
├── PRINCIPLES.md    # 仓库基本原则（详细版）
└── README.md
```

**计划收录内容：**
- sway 配置（layout、keybindings、rules）
- waybar 双栏 macOS 风格配置
- sway-session 管理（save/restore/daemon/idle）
- wofi / rofi 启动器
- mako 通知
- systemd 用户服务（uxplay、waybar 等）
- PipeWire / WirePlumber 音频
- fcitx5 输入法
- 蓝牙设备管理
- DPMS / s2idle 电源管理

---

## 五项基本原则

### 1. 官方文档优先

以各功能模块的 **官方文档** 为第一优先依据源。所有技能文档中的配置参数、命令、路径均应以官方文档为准，不得凭空杜撰。

### 2. 来源必注明

所有与系统有关的设置动作，**先有具体的来源出处，再执行操作**。每个配置项、每条命令、每个脚本，都必须在文档中注明其来源 URL 或引用出处。

### 3. 来源优先级

当多个信息源矛盾时，按以下优先级裁决：

```
官方文档（本地/线上） > 开源仓库 > 社区信息 > 技能注明的以往经验 > 其他网络信息
```

- **官方文档**：项目的官方文档站、man page、README、Wiki
- **开源仓库**：GitHub/GitLab 等源码仓库的 issue、PR、源码注释
- **社区信息**：论坛、讨论区、博客等经验分享
- **技能注明的以往经验**：本仓库技能中已有的、经过验证的历史配置
- **其他网络信息**：上述之外的网络资料

### 4. 不确定即查证

**不知道/不确定的马上去查线上/线下资料**，不要盲猜、乱测。搜索流程：

1. 先查本地已有的官方文档（man page、info、`--help`）
2. 再查线上官方文档站
3. 搜索具体错误信息或配置项
4. 记录查证结果到技能或笔记中

### 5. 定期同步

**本地文档信息源安排定期同步线上官方文档来源。**

- 对每个技能，在 SKILL.md 中注明 `source` 字段指向线上官方文档 URL
- 当线上官方文档更新时（如版本升级、配置参数变更），及时更新本地技能
- 可通过 Hermes cron 任务定期检查依赖的官方文档是否有变更

---

## Agent 操作规范

### 编写技能（SKILL.md）

- 每个技能必须包含 `source` 字段，指向官方文档 URL
- 配置示例必须经过实际验证，不得凭空构造
- 中文注释
- 实用至上，避免冗余

### 引用配置

- 配置文件的参考版本放在 `configs/` 子目录中，按组件分类
- 参考配置必须以实际可用的完整文件形式存放，而非片段
- 每个配置必须注明对应的官方文档链接

### 搜索优先级

在不确定任何配置项时，按以下顺序查证：

1. `man <component>` / `<command> --help`
2. 搜索 `<component> official documentation`
3. 搜索 `<component> <error/feature> site:github.com`
4. 本仓库已有技能和配置
5. 其他网络搜索

### 更新流程

1. 搜索官方文档确认最新配置方式
2. 在本地技能/配置中更新，注明来源
3. 验证配置有效
4. 提交变更

---

*本文件需与 PRINCIPLES.md 保持一致。*  
*更新 PRINCIPLES.md 后应同步更新本文件。*
