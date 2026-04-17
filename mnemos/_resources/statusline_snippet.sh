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

    # v0.3.12c: only render in the session that triggered the refine.
    # The parent statusline script stores Claude Code's stdin JSON in $input.
    # If we can extract session_id and it doesn't match, stay silent — the
    # refine belongs to another window.
    local trigger_id my_session_id
    trigger_id=$(jq -r '.triggering_session_id // ""' "$status_file")
    if [ -n "$trigger_id" ] && [ -n "$input" ]; then
        my_session_id=$(echo "$input" | jq -r '.session_id // ""' 2>/dev/null)
        if [ -n "$my_session_id" ] && [ "$trigger_id" != "$my_session_id" ]; then
            return 0
        fi
    fi

    local phase current total backlog started_at updated_at last_outcome last_finished_at last_ok last_skip
    phase=$(jq -r '.phase // "idle"' "$status_file")
    current=$(jq -r '.current // 0' "$status_file")
    total=$(jq -r '.total // 0' "$status_file")
    backlog=$(jq -r '.backlog // 0' "$status_file")
    started_at=$(jq -r '.started_at // ""' "$status_file")
    updated_at=$(jq -r '.updated_at // ""' "$status_file")
    last_outcome=$(jq -r '.last_outcome // ""' "$status_file")
    last_finished_at=$(jq -r '.last_finished_at // ""' "$status_file")
    last_ok=$(jq -r '.last_ok // -1' "$status_file")
    last_skip=$(jq -r '.last_skip // -1' "$status_file")

    local now_epoch
    now_epoch=$(date +%s)

    # Stale-idle check: silent after 10 min so the footer stops showing the
    # "last refine Xm ago" message indefinitely.
    if [ "$phase" = "idle" ]; then
        local updated_epoch
        updated_epoch=$(date -d "$updated_at" +%s 2>/dev/null || echo "$now_epoch")
        (( now_epoch - updated_epoch > 600 )) && return 0
    fi

    # Elapsed timer (since current refine round started)
    local elapsed=""
    if [ -n "$started_at" ]; then
        local start_epoch
        start_epoch=$(date -d "$started_at" +%s 2>/dev/null || echo "")
        if [ -n "$start_epoch" ]; then
            local delta=$(( now_epoch - start_epoch ))
            elapsed="$(( delta / 60 ))m$(( delta % 60 ))s"
        fi
    fi

    # Running tally string (v0.3.12c): show OK/SKIP counts mid-flight
    local tally=""
    if [ "$last_ok" -gt 0 ] 2>/dev/null && [ "$last_skip" -gt 0 ] 2>/dev/null; then
        tally=" · ${last_ok} OK ${last_skip} skip"
    elif [ "$last_ok" -gt 0 ] 2>/dev/null; then
        tally=" · ${last_ok} OK"
    elif [ "$last_skip" -gt 0 ] 2>/dev/null; then
        tally=" · ${last_skip} skip"
    fi

    case "$phase" in
        refining) printf "  mnemos: refining %d/%d%s · %s · backlog %d" "$current" "$total" "$tally" "$elapsed" "$backlog" ;;
        mining)   printf "  mnemos: mining%s · %s · backlog %d" "$tally" "$elapsed" "$backlog" ;;
        busy)     printf "  mnemos: other session active" ;;
        idle)
            # When we have meta from the last completed round, show it.
            if [ -n "$last_finished_at" ]; then
                local finish_epoch ago_min
                finish_epoch=$(date -d "$last_finished_at" +%s 2>/dev/null || echo "")
                if [ -n "$finish_epoch" ]; then
                    ago_min=$(( (now_epoch - finish_epoch) / 60 ))
                    case "$last_outcome" in
                        noop)
                            printf "  mnemos: idle %dm · backlog %d" "$ago_min" "$backlog"
                            ;;
                        ok|skip)
                            # v0.3.11: render real OK/SKIP split when present so
                            # "3 notes · OK" no longer hides "3 SKIPs · 0 notes".
                            if [ "$last_ok" -ge 0 ] && [ "$last_skip" -ge 0 ]; then
                                if [ "$last_ok" -gt 0 ] && [ "$last_skip" -gt 0 ]; then
                                    printf "  mnemos: last refine %dm ago · %d notes · %d skipped · backlog %d" \
                                        "$ago_min" "$last_ok" "$last_skip" "$backlog"
                                elif [ "$last_ok" -gt 0 ]; then
                                    printf "  mnemos: last refine %dm ago · %d notes · backlog %d" \
                                        "$ago_min" "$last_ok" "$backlog"
                                else
                                    printf "  mnemos: last refine %dm ago · 0 notes (%d skipped) · backlog %d" \
                                        "$ago_min" "$last_skip" "$backlog"
                                fi
                            else
                                # Backward compat: pre-v0.3.11 status JSONs lack last_ok/last_skip.
                                local outcome_label
                                case "$last_outcome" in
                                    ok)   outcome_label="OK" ;;
                                    skip) outcome_label="SKIP" ;;
                                esac
                                printf "  mnemos: last refine %dm ago · %d notes · %s · backlog %d" \
                                    "$ago_min" "$total" "$outcome_label" "$backlog"
                            fi
                            ;;
                        failed)
                            printf "  mnemos: last refine %dm ago · FAIL · backlog %d" "$ago_min" "$backlog"
                            ;;
                        *)
                            printf "  mnemos: last refine %dm ago · %s · backlog %d" \
                                "$ago_min" "$last_outcome" "$backlog"
                            ;;
                    esac
                else
                    printf "  mnemos: done (backlog %d)" "$backlog"
                fi
            else
                printf "  mnemos: done (backlog %d)" "$backlog"
            fi
            ;;
        *)        printf "  mnemos: %s" "$phase" ;;
    esac
}

_mnemos_statusline
