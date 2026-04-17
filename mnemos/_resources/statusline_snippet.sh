#!/usr/bin/env bash
# Mnemos auto-refine statusline snippet (one-shot).
#
# Claude Code calls the statusline command once at session start, NOT
# continuously. This snippet renders a single snapshot — no timers, no
# live progress. The user sees what's happening now; results appear on
# the next session start.
#
# Reads $MNEMOS_VAULT/.mnemos-hook-status.json.
# Expects the parent statusline script to store Claude Code's stdin JSON
# in $input (used for session_id filtering).

_mnemos_statusline() {
    local status_file="${MNEMOS_VAULT:-$HOME/mnemos}/.mnemos-hook-status.json"
    [ -f "$status_file" ] || return 0
    command -v jq >/dev/null 2>&1 || return 0

    # Only render in the session that triggered the refine. Other windows
    # stay silent — prevents the "refining itself" false impression.
    local trigger_id
    trigger_id=$(jq -r '.triggering_session_id // ""' "$status_file")
    if [ -n "$trigger_id" ] && [ -n "$input" ]; then
        local my_session_id
        my_session_id=$(echo "$input" | jq -r '.session_id // ""' 2>/dev/null)
        if [ -n "$my_session_id" ] && [ "$trigger_id" != "$my_session_id" ]; then
            return 0
        fi
    fi

    local phase backlog last_ok last_skip total
    phase=$(jq -r '.phase // "idle"' "$status_file")
    backlog=$(jq -r '.backlog // 0' "$status_file")
    total=$(jq -r '.total // 0' "$status_file")
    last_ok=$(jq -r '.last_ok // -1' "$status_file")
    last_skip=$(jq -r '.last_skip // -1' "$status_file")

    case "$phase" in
        refining)
            printf "  mnemos: refining %d sessions in background · backlog %d" "$total" "$backlog"
            ;;
        mining)
            printf "  mnemos: mining · backlog %d" "$backlog"
            ;;
        idle)
            # Show previous round's result (if available and from this session).
            if [ "$last_ok" -ge 0 ] 2>/dev/null && [ "$last_skip" -ge 0 ] 2>/dev/null; then
                if [ "$last_ok" -gt 0 ] && [ "$last_skip" -gt 0 ]; then
                    printf "  mnemos: done · %d notes · %d skipped · backlog %d" "$last_ok" "$last_skip" "$backlog"
                elif [ "$last_ok" -gt 0 ]; then
                    printf "  mnemos: done · %d notes · backlog %d" "$last_ok" "$backlog"
                elif [ "$last_skip" -gt 0 ]; then
                    printf "  mnemos: done · 0 notes (%d skipped) · backlog %d" "$last_skip" "$backlog"
                else
                    printf "  mnemos: done · backlog %d" "$backlog"
                fi
            elif [ "$total" -gt 0 ]; then
                printf "  mnemos: done · backlog %d" "$backlog"
            fi
            ;;
    esac
}

_mnemos_statusline
