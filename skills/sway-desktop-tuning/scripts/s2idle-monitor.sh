#!/bin/bash
# s2idle-monitor.sh — live monitoring of s2idle state, SSH events, and CPU/NIC power
#
# Usage: s2idle-monitor.sh [duration-seconds]   (default 300 = 5 min)
#
# Samples every second and writes a timestamped log. Logs to:
#   /tmp/s2idle-monitor-YYYYMMDD-HHMMSS.log
#
# Captures: mem_sleep, NIC power/control + runtime_status, CPU0 frequency,
# Tailscale state, SSH connection count. Marks SSH connection count changes
# with *** so you can correlate external SSH events with system state.
#
# Use this BEFORE making any "s2idle doesn't respond to SSH" claim — run it for
# a few minutes, then look at the CPU frequency column. If it's mostly 800 MHz
# and the system responds to SSH, the system was CPU-idle in S0, NOT in s2idle.
# These are different things.

set -u

DURATION="${1:-300}"

LOG="/tmp/s2idle-monitor-$(date +%Y%m%d-%H%M%S).log"

echo "[$(date +%H:%M:%S)] 监控启动, 持续 ${DURATION}s, 日志: $LOG"
echo "[$(date +%H:%M:%S)] 本机 Tailscale IP: $(tailscale ip -4 2>/dev/null | head -1)"

echo "[$(date +%H:%M:%S)] 当前 SSH 连接:"
ps -ef | grep -E "sshd:" | grep -v grep | head -5

LAST_SSH=$(ps -ef | grep -E "sshd:" | grep -v grep | wc -l)
echo

for i in $(seq 1 "$DURATION"); do
    NOW=$(date +%H:%M:%S)
    MEM=$(cat /sys/power/mem_sleep 2>/dev/null)
    WIFI_CTRL=$(cat /sys/class/net/wlp4s0/device/power/control 2>/dev/null)
    WIFI_RT=$(cat /sys/class/net/wlp4s0/device/power/runtime_status 2>/dev/null)
    CPU_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null)
    CURR_SSH=$(ps -ef | grep -E "sshd:" | grep -v grep | wc -l)
    TS_STATE=$(tailscale status 2>/dev/null | grep "$(tailscale ip -4 2>/dev/null | head -1)" | head -1 | awk '{print $4}')

    if [ "$CURR_SSH" != "$LAST_SSH" ]; then
        echo "[$NOW] *** SSH 连接变化: $LAST_SSH -> $CURR_SSH ***" >> "$LOG"
        if [ "$CURR_SSH" -gt "$LAST_SSH" ]; then
            echo "[$NOW] *** 新 SSH 连接到达! ***" >> "$LOG"
            ps -ef | grep -E "sshd:" | grep -v grep >> "$LOG"
            cat /proc/loadavg >> "$LOG"
        fi
        LAST_SSH="$CURR_SSH"
    fi

    echo "[$NOW] mem_sleep=$MEM  wifi_ctrl=$WIFI_CTRL  wifi_rt=$WIFI_RT  cpu0=${CPU_FREQ} kHz  ts=$TS_STATE  ssh=$CURR_SSH" >> "$LOG"

    sleep 1
done

echo
echo "[$(date +%H:%M:%S)] 监控结束, 日志: $LOG"
echo
echo "=== 日志中标记 SSH 变化的行 ==="
grep -E "\*\*\*|新 SSH" "$LOG" 2>/dev/null | head -10
echo
echo "=== CPU 频率分布 (整个监控期间) ==="
awk -F'cpu0=' '{print $2}' "$LOG" 2>/dev/null | awk '{print $1}' | sort | uniq -c | sort -rn | head -5
