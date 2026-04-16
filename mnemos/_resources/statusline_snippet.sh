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

    local phase current total backlog started_at updated_at last_outcome last_finished_at
    phase=$(jq -r '.phase // "idle"' "$status_file")
    current=$(jq -r '.current // 0' "$status_file")
    total=$(jq -r '.total // 0' "$status_file")
    backlog=$(jq -r '.backlog // 0' "$status_file")
    started_at=$(jq -r '.started_at // ""' "$status_file")
    updated_at=$(jq -r '.updated_at // ""' "$status_file")
    last_outcome=$(jq -r '.last_outcome // ""' "$status_file")
    last_finished_at=$(jq -r '.last_finished_at // ""' "$status_file")

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

    case "$phase" in
        refining) printf "  mnemos: refining %d/%d · %s · backlog %d" "$current" "$total" "$elapsed" "$backlog" ;;
        mining)   printf "  mnemos: mining · %s · backlog %d" "$elapsed" "$backlog" ;;
        busy)     printf "  mnemos: other session active" ;;
        idle)
            # When we have meta from the last completed round, show it.
            if [ -n "$last_finished_at" ]; then
                local finish_epoch ago_min outcome_label
                finish_epoch=$(date -d "$last_finished_at" +%s 2>/dev/null || echo "")
                if [ -n "$finish_epoch" ]; then
                    ago_min=$(( (now_epoch - finish_epoch) / 60 ))
                    case "$last_outcome" in
                        ok)     outcome_label="OK" ;;
                        noop)   outcome_label="no-op" ;;
                        failed) outcome_label="FAIL" ;;
                        *)      outcome_label="$last_outcome" ;;
                    esac
                    if [ "$last_outcome" = "noop" ]; then
                        printf "  mnemos: idle %dm · backlog %d" "$ago_min" "$backlog"
                    else
                        printf "  mnemos: last refine %dm ago · %d notes · %s · backlog %d" \
                            "$ago_min" "$total" "$outcome_label" "$backlog"
                    fi
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
