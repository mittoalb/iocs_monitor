#!/bin/bash
# Shared helpers for iocs_monitor scripts.
#
# Every IOC control script sources this file:
#     source "$(dirname "$0")/_lib.sh"
#
# It provides `iom_open`, a drop-in replacement for
#     gnome-terminal --tab --title="<title>" -- bash -c "<command>"
# that falls back to a headless nohup+log run when a terminal cannot
# be created. This matters when the calling context has no DISPLAY,
# no D-Bus session bus, or no gnome-terminal binary — the previous
# behavior was that the whole script silently died and the IOC was
# never touched.
#
# Force headless mode with:  IOM_HEADLESS=1  (Python launcher sets this)
# Override the log directory: IOM_LOGDIR=/path/to/logs
#                              (default: $HOME/.iocs_monitor/logs)

_iom_have_terminal() {
    [ -n "$DISPLAY" ] || return 1
    command -v gnome-terminal >/dev/null 2>&1 || return 1
    if [ -n "$DBUS_SESSION_BUS_ADDRESS" ]; then
        return 0
    fi
    if [ -S "/run/user/$(id -u)/bus" ]; then
        export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
        return 0
    fi
    return 1
}

# iom_open <title> <command>
#   Runs <command> either in a new gnome-terminal tab (interactive)
#   or under `nohup bash -c` with logging (headless). Never fails
#   the caller: if the terminal can't be created it falls through
#   to headless mode instead of exiting.
iom_open() {
    local title="$1"
    local cmd="$2"

    if [ "${IOM_HEADLESS:-0}" != "1" ] && _iom_have_terminal; then
        # Terminal available: keep the shell open after cmd exits so
        # the user can inspect output, matching legacy behavior.
        if gnome-terminal --tab --title="$title" -- \
                bash -c "$cmd
exec bash" 2>/dev/null; then
            return 0
        fi
        echo "[iom] gnome-terminal failed; falling back to headless run" >&2
    fi

    local logdir="${IOM_LOGDIR:-$HOME/.iocs_monitor/logs}"
    mkdir -p "$logdir" 2>/dev/null || logdir="/tmp"
    local safe
    safe=$(printf '%s' "$title" | tr ' /\\' '___' | tr -cd '[:alnum:]_.-')
    [ -z "$safe" ] && safe="ioc"
    local logfile="$logdir/${safe}_$(date +%Y%m%d_%H%M%S_%N).log"

    echo "[iom] headless: $title  (log: $logfile)"
    nohup bash -c "$cmd" >"$logfile" 2>&1 &
    disown 2>/dev/null || true
    return 0
}
