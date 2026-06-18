#!/bin/bash
# Tailscale 状态检测 — 3 态版本
# 输出 JSON: { "text": "...", "alt": "online|abnormal|disconnected", "tooltip": "..." }
#
# 状态语义:
#   online       — daemon 运行, ≥1 peer 在线
#   abnormal     — daemon 运行, 但 0 peer 在线(自身孤岛 / 网络问题)
#   disconnected — daemon 未运行
#
# 3 态 vs 2 态(原版):
#   原版只有 connected/disconnected — 把"daemon 在但 0 peer"和"daemon 没跑"混为一谈
#   3 态分开后,UI 可分别染色:绿/紫/灰,异常有专门提示
#
# CSS 配套:
#   #custom-tailscale            { color: #000; }      (默认)
#   #custom-tailscale.online     { color: #2d8a4e; font-weight: bold; }  (绿)
#   #custom-tailscale.abnormal   { color: #8a3fd1; font-weight: bold; }  (紫)
#   #custom-tailscale.disconnected { color: #aaa; }    (灰)

if ! output=$(tailscale status 2>/dev/null); then
  echo '{"text":"TS ✗","alt":"disconnected","tooltip":"Tailscale 未运行 (sudo tailscaled?)"}'
  exit 0
fi

# 统计在线 peer 数(排除 self 与 offline 节点)
# 关键陷阱:grep -cP "^100\." 把自身行也算进去,得减 1
all_count=$(echo "$output" | awk '$1 ~ /^100\./' | wc -l)
offline_count=$(echo "$output" | awk '$1 ~ /^100\./ && /offline/' | wc -l)
online_count=$((all_count - offline_count - 1))  # 减掉自身

# tooltip 取前 3 个 IP 作摘要
ips=$(echo "$output" | awk '$1 ~ /^100\./ {print $1}' | head -3 | tr '\n' ' ')

if [ "$online_count" -ge 1 ]; then
  echo "{\"text\":\"TS ${online_count}\",\"alt\":\"online\",\"tooltip\":\"Tailscale 在线 ${online_count} 节点\\n${ips}\"}"
elif [ "$online_count" -eq 0 ]; then
  # daemon 在跑但 0 peer 在线 → 异常
  echo '{"text":"TS !","alt":"abnormal","tooltip":"Tailscale daemon 在跑,但 0 peer 在线(孤岛/网络问题)"}'
else
  echo '{"text":"TS ✗","alt":"disconnected","tooltip":"Tailscale 状态异常"}'
fi
