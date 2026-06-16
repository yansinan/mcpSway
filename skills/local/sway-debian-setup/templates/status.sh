#!/bin/bash
# Swaybar status script — date (24h) + CPU load + memory
# Usage: drop into sway config:
#   status_command exec ~/.config/sway/status.sh
# Override /etc/sway/config: sudo sed -i 's|status_command while date.*|status_command exec ~/.config/sway/status.sh|' /etc/sway/config
# Or define a new bar block in ~/.config/sway/config (but that creates a second bar,
# so prefer the sed approach unless you want a custom bar layout.)
while true; do
    date=$(date '+%Y-%m-%d %H:%M')
    cpu=$(uptime | awk -F'load average:' '{print $2}' | cut -d, -f1 | xargs)
    mem=$(free -h | grep Mem | awk '{print $3 "/" $2}')
    echo "$date | CPU: $cpu | MEM: $mem"
    sleep 5
done
