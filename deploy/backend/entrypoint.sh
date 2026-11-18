#!/usr/bin/env bash
set -euo pipefail

# Start Xvfb/x11vnc/noVNC only for the long-running app. Short-lived commands
# (image checks, health probes, one-off shells) exec directly so their stdout
# stays clean and their exit code is the container exit code.
start_graphics=0
if [[ "${1:-}" == "uvicorn" || "${TALENTMIND_START_GRAPHICS:-0}" == "1" ]]; then
    start_graphics=1
fi

graphics_pids=()
app_pid=""

start_graphics_services() {
    local display=":99"
    local socket="/tmp/.X11-unix/X99"

    Xvfb "$display" -screen 0 1280x800x24 -nolisten tcp \
        >/tmp/talentmind-xvfb.log 2>&1 &
    graphics_pids+=("$!")
    local _ attempt
    for attempt in $(seq 1 50); do
        [[ -S "$socket" ]] && break
        sleep 0.1
    done
    if [[ ! -S "$socket" ]]; then
        printf 'Xvfb did not create %s; see /tmp/talentmind-xvfb.log\n' "$socket" >&2
        exit 1
    fi

    x11vnc -display "$display" -localhost -nopw -forever -shared -rfbport 5900 \
        >/tmp/talentmind-x11vnc.log 2>&1 &
    graphics_pids+=("$!")

    websockify --web=/usr/share/novnc 6080 127.0.0.1:5900 \
        >/tmp/talentmind-websockify.log 2>&1 &
    graphics_pids+=("$!")
}

cleanup() {
    local status=$?
    trap - EXIT TERM INT
    if [[ -n "$app_pid" ]] && kill -0 "$app_pid" 2>/dev/null; then
        kill -TERM "$app_pid" 2>/dev/null || true
        wait "$app_pid" 2>/dev/null || true
    fi
    local pid
    for pid in "${graphics_pids[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    for pid in "${graphics_pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    exit "$status"
}

forward_signal() {
    local signal="$1"
    if [[ -n "$app_pid" ]]; then
        kill "-$signal" "$app_pid" 2>/dev/null || true
    fi
}

if [[ "$start_graphics" -eq 0 ]]; then
    exec "$@"
fi

trap cleanup EXIT
trap 'forward_signal TERM' TERM
trap 'forward_signal INT' INT

start_graphics_services

"$@" &
app_pid=$!
status=0
# A trapped signal interrupts wait; keep waiting until the app really exits so
# its own exit code (not 128+signal) reaches the container runtime.
while kill -0 "$app_pid" 2>/dev/null; do
    status=0
    wait "$app_pid" || status=$?
done
exit "$status"
