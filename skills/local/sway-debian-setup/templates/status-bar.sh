#!/bin/bash
# sway 系统状态栏 — CPU / 内存 / 温度 / 音量
# 与 sway config 同目录，由 bar 的 status_command 调用
# 输出 i3bar 协议 JSON（swaybar 可解析）
# 复制到 ~/.config/sway/status.sh 后 chmod +x 即可使用
# shellcheck 零警告

CLR_DEF="#ffffff"
CLR_WARN="#ffcc00"
CLR_HOT="#ff6600"
CLR_CRIT="#ff3333"

SENSOR="/sys/class/thermal/thermal_zone0/temp"

# CPU 预采样（需 2 秒间隔才有有效差值）
read -r CPU_LINE < /proc/stat
read -ra CPU_A <<< "$CPU_LINE"
PREV_IDLE=${CPU_A[4]}
TOTAL=0
for i in {1..7}; do ((TOTAL += CPU_A[i])); done
PREV_TOTAL=$TOTAL
sleep 2

# i3bar 协议头（必需，否则 swaybar 当纯文本显示）
echo '{"version":1}'
echo '['

FIRST=true

while true; do
    # ── CPU ──
    read -r CPU_LINE < /proc/stat
    read -ra CPU_A <<< "$CPU_LINE"
    IDLE=${CPU_A[4]}
    TOTAL=0
    for i in {1..7}; do ((TOTAL += CPU_A[i])); done
    DIFF_IDLE=$(( IDLE - PREV_IDLE ))
    DIFF_TOTAL=$(( TOTAL - PREV_TOTAL ))
    CPU_PCT=$(( 100 * (DIFF_TOTAL - DIFF_IDLE) / DIFF_TOTAL ))
    PREV_IDLE=$IDLE
    PREV_TOTAL=$TOTAL
    if [ "$CPU_PCT" -ge 80 ]; then
        CCOL=$CLR_CRIT
    else
        CCOL=$CLR_DEF
    fi

    # ── 内存 ──
    MEM_TOT=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
    MEM_AVL=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
    MEM_USED=$(( (MEM_TOT - MEM_AVL) / 1024 ))
    MEM_TOT_MB=$(( MEM_TOT / 1024 ))
    MEM_PCT=$(( (MEM_TOT - MEM_AVL) * 100 / MEM_TOT ))
    if [ "$MEM_PCT" -ge 85 ]; then
        MCOL=$CLR_CRIT
    elif [ "$MEM_PCT" -ge 70 ]; then
        MCOL=$CLR_WARN
    else
        MCOL=$CLR_DEF
    fi

    # ── 温度 (acpitz) ──
    if [ -r "$SENSOR" ]; then
        read -r T_RAW < "$SENSOR"
        T_C=$(( T_RAW / 1000 ))
        if [ "$T_C" -ge 80 ]; then
            TCOL=$CLR_CRIT
        elif [ "$T_C" -ge 65 ]; then
            TCOL=$CLR_HOT
        else
            TCOL=$CLR_DEF
        fi
    else
        T_C="--"
        TCOL=$CLR_DEF
    fi

    # ── 音量（PipeWire） ──
    VOL_LINE=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null)
    VOL_PCT=$(echo "$VOL_LINE" | awk '{printf "%.0f", $2 * 100}')
    if echo "$VOL_LINE" | grep -qi "muted"; then
        VOL_STR="🔇 ${VOL_PCT}%"
        VOLCOL=$CLR_CRIT
    elif [ "$VOL_PCT" -le 1 ]; then
        VOL_STR="🔇 ${VOL_PCT}%"
        VOLCOL=$CLR_WARN
    else
        VOL_STR="🔊 ${VOL_PCT}%"
        VOLCOL=$CLR_DEF
    fi

    # ── 时间 ──
    NOW=$(date '+%H:%M')

    # ── JSON 输出（i3bar 协议） ──
    # 第一行：[（外层数组第一个元素）；后续行：,（后续元素）
    if $FIRST; then
        printf '[{"full_text":" 🖥 %s%%","color":"%s"},{"full_text":" 🧠 %sM/%sM","color":"%s"},{"full_text":" 🌡 %s°C","color":"%s"},{"full_text":" %s","color":"%s"},{"full_text":" ⏱ %s","color":"%s"}]\n' \
            "$CPU_PCT" "$CCOL" \
            "$MEM_USED" "$MEM_TOT_MB" "$MCOL" \
            "$T_C" "$TCOL" \
            "$VOL_STR" "$VOLCOL" \
            "$NOW" "$CLR_DEF"
        FIRST=false
    else
        printf ',[{"full_text":" 🖥 %s%%","color":"%s"},{"full_text":" 🧠 %sM/%sM","color":"%s"},{"full_text":" 🌡 %s°C","color":"%s"},{"full_text":" %s","color":"%s"},{"full_text":" ⏱ %s","color":"%s"}]\n' \
            "$CPU_PCT" "$CCOL" \
            "$MEM_USED" "$MEM_TOT_MB" "$MCOL" \
            "$T_C" "$TCOL" \
            "$VOL_STR" "$VOLCOL" \
            "$NOW" "$CLR_DEF"
    fi

    sleep 2
done
