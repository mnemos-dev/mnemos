#!/usr/bin/env bash
# Add this line to your ~/.claude/statusline-command.sh (or equivalent):
#   source "$(dirname "$0")/mnemos-statusline.sh"
# or copy this entire file's body into your statusline script.
#
# Reads $MNEMOS_VAULT/.mnemos-hook-status.json and prints a compact fragment.

_mnemos_statusline() {
    local status_file="${MNEMOS_VAULT:-$HOME/mnemos}/.mnemos-hook-status.json"
    [ -f "$status_file" ] || return 0

    # Require jq; silently skip if missing
    command -v jq >/dev/null 2>&1 || return 0

    local phase current total backlog started_at
    phase=$(jq -r '.phase // "idle"' "$status_file")
    current=$(jq -r '.current // 0' "$status_file")
    total=$(jq -r '.total // 0' "$status_file")
    backlog=$(jq -r '.backlog // 0' "$status_file")
    started_at=$(jq -r '.started_at // ""' "$status_file")

    # idle > 30s old → silent
    if [ "$phase" = "idle" ]; then
        local updated_at now_epoch updated_epoch
        updated_at=$(jq -r '.updated_at // ""' "$status_file")
        now_epoch=$(date +%s)
        updated_epoch=$(date -d "$updated_at" +%s 2>/dev/null || echo "$now_epoch")
        (( now_epoch - updated_epoch > 30 )) && return 0
    fi

    # elapsed timer
    local elapsed=""
    if [ -n "$started_at" ]; then
        local start_epoch
        start_epoch=$(date -d "$started_at" +%s 2>/dev/null || echo "")
        if [ -n "$start_epoch" ]; then
            local delta=$(( $(date +%s) - start_epoch ))
            elapsed="$(( delta / 60 ))m$(( delta % 60 ))s"
        fi
    fi

    case "$phase" in
        starting) printf "  mnemos: starting %s" "$elapsed" ;;
        refining) printf "  mnemos: refining %d/%d · %s · backlog %d" "$current" "$total" "$elapsed" "$backlog" ;;
        mining)   printf "  mnemos: mining · %s · backlog %d" "$elapsed" "$backlog" ;;
        busy)     printf "  mnemos: auto-refine busy (another session)" ;;
        idle)     printf "  mnemos: done (backlog %d)" "$backlog" ;;
        *)        printf "  mnemos: %s" "$phase" ;;
    esac
}

_mnemos_statusline
