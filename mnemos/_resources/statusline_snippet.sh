#!/usr/bin/env bash
# Mnemos auto-refine + recall-briefing statusline snippet (v1.0).
#
# Claude Code calls the statusline command once at session start, NOT
# continuously. This snippet renders a single snapshot — no timers, no
# live progress. The user sees what's happening now; results appear on
# the next session start.
#
# Reads $MNEMOS_VAULT/.mnemos-hook-status.json. Expects the parent
# statusline script to store Claude Code's stdin JSON in $input (used
# for session_id filtering).
#
# v1.0 narrative-first pivot: drawer extraction is removed. Phases we
# render are `refining` (auto-refine background worker), `briefing`
# (recall-briefing catch-up), and `idle` (last refine + identity-refresh
# marker). The identity_last_refreshed field surfaces when the L0 identity
# layer was last regenerated so users notice when refresh has fallen stale.

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

    local phase backlog last_ok identity_last_refreshed
    phase=$(jq -r '.phase // "idle"' "$status_file")
    backlog=$(jq -r '.backlog // 0' "$status_file")
    last_ok=$(jq -r '.last_ok // 0' "$status_file")
    identity_last_refreshed=$(jq -r '.identity_last_refreshed // ""' "$status_file")

    case "$phase" in
        refining)
            printf "  mnemos: refining..."
            ;;
        briefing)
            printf "  mnemos: briefing..."
            ;;
        idle)
            if [ -n "$identity_last_refreshed" ]; then
                printf "  mnemos: %d notes · identity %s · backlog %d" \
                    "$last_ok" "$identity_last_refreshed" "$backlog"
            else
                printf "  mnemos: %d notes · backlog %d" "$last_ok" "$backlog"
            fi
            ;;
        *)
            printf "  mnemos: %s" "$phase"
            ;;
    esac
}

_mnemos_statusline
