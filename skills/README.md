# skills/

此目录存放 Hermes 技能定义（SKILL.md），每个技能一个子目录。

命名约定：`<scope>-<topic>` 形式，例如 `sway-waybar-config`。

## 技能索引

| 技能 | 描述 | 来源 |
|------|------|------|
| `waybar-config` | Waybar 配置参考：双栏布局、模块、custom/* JSON、Pango tooltip、API 凭证、PWA 图标、CSS、陷阱、调试 | 官方 Wiki + man page + 本地经验验证 (Debian 13 / sway 1.10 / waybar 0.12.0) |

## 添加新技能

1. 在 `skills/` 下创建子目录
2. 编写 `SKILL.md`（YAML frontmatter + Markdown 正文）
3. 必须包含 `source` 字段指向官方文档 URL
4. 可附带 `references/` 和 `templates/` 子目录
5. 更新本索引
