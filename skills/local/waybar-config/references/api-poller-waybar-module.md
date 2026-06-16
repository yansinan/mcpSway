# API Poller Waybar 模块 — 持久化 + 趋势分析

> 本文件已被整合入主 SKILL.md §「Dual-mode 架构（Waybar + Cron 双模式）」。

适用于：需要 **定时轮询 REST API + 本地缓存历史 + 趋势/告警分析** 的 Waybar 自定义模块。

## 架构

```
script.py ──→ API (urllib) ──→ 本地 data/history.json ──→ analyze() ──→ Waybar JSON
    │                                    ↑
    └─── cron 模式：完整 JSON 输出 ──────┘（同一脚本，两个入口）
```

## 关键要素

1. **Dual-mode 路由** — `--waybar` → Waybar JSON; 无参数 → 完整 JSON
2. **路径基准** — `Path(__file__).resolve()` 定位 scripts/ 和 data/
3. **历史持久化** — JSON 文件，保留最近 N 条，去重
4. **状态驱动 CSS** — ok / warning / critical / error
5. **优雅降级** — API 挂掉时输出 error class，不抛 traceback
6. **Pango tooltip** — `<b>` 标题，`<span color='#888'>` 辅助信息，`<span color='#e74c3c'>` 告警

## 参考实现

`~/.hermes/skills/local/deepseek-cost/scripts/collect.py`
