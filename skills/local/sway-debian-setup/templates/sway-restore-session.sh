#!/bin/bash
# sway-restore-session — Restore apps to workspaces from a saved session.
#
# Saves/loads ~/.sway-session/workspace-apps.json which maps workspace names
# to ordered lists of app_ids. Used alongside the save-session.sh script.
#
# Add to sway config:
#   exec ~/.config/sway/restore-session.sh

set -euo pipefail

SESSION_FILE="$HOME/.sway-session/workspace-apps.json"

restore_session() {
    if [ ! -f "$SESSION_FILE" ]; then
        echo "No saved session at $SESSION_FILE"
        exit 0
    fi

    jq -c 'to_entries[]' "$SESSION_FILE" | while read -r entry; do
        ws=$(echo "$entry" | jq -r '.key')
        apps=$(echo "$entry" | jq -r '.value[]')

        [ "$apps" = "null" ] || [ -z "$apps" ] && continue

        # Switch to workspace (creates it if needed)
        swaymsg workspace "$ws"
        sleep 0.3

        echo "$apps" | while IFS= read -r app_id; do
            case "$app_id" in
                foot)           foot & ;;
                firefox)        firefox & ;;
                firefoxdeveloperedition) firefox-developer-edition & ;;
                chromium)       chromium & ;;
                code-oss)       code-oss & ;;
                code)           code & ;;
                nautilus)       nautilus & ;;
                org.gnome.Nautilus) nautilus & ;;
                thunderbird)    thunderbird & ;;
                org.wezfurlong.wezterm) wezterm & ;;
                Alacritty)      alacritty & ;;
                kitty)          kitty & ;;
                *)              # Unknown app_id — try launching it raw
                                command -v "$app_id" &>/dev/null && "$app_id" & ;;
            esac
            sleep 0.5  # Let the window appear before the next one
        done
    done

    echo "Session restored from $SESSION_FILE"
}

save_session() {
    mkdir -p "$HOME/.sway-session"

    # Get all workspace names
    local workspaces
    workspaces=$(swaymsg -t get_workspaces --raw | jq -r '.[].name')

    local first=true
    echo "{" > "$SESSION_FILE"

    echo "$workspaces" | while read -r ws; do
        [ -z "$ws" ] && continue

        apps=$(swaymsg -t get_tree --raw | jq -r "
            [.. | select(.type? == \"con\" and .app_id? != null and .app_id? != \"\") | .app_id]
            | unique | .[]
        " 2>/dev/null | sort)

        if [ -n "$apps" ]; then
            if [ "$first" = true ]; then
                first=false
            else
                echo "," >> "$SESSION_FILE"
            fi

            echo -n "\"$ws\": [" >> "$SESSION_FILE"
            local first_app=true
            echo "$apps" | while IFS= read -r app; do
                [ -z "$app" ] && continue
                if [ "$first_app" = true ]; then
                    first_app=false
                else
                    echo -n ", " >> "$SESSION_FILE"
                fi
                echo -n "\"$app\"" >> "$SESSION_FILE"
            done
            echo "]" >> "$SESSION_FILE"
        fi
    done

    echo "}" >> "$SESSION_FILE"
    echo "Session saved to $SESSION_FILE"
}

case "${1:-restore}" in
    save)
        save_session
        ;;
    restore)
        restore_session
        ;;
    *)
        echo "Usage: $0 {save|restore}"
        echo "  save    — save current workspace layout"
        echo "  restore — restore apps to workspaces"
        exit 1
        ;;
esac
