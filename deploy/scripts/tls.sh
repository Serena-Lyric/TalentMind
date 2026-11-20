#!/usr/bin/env bash
# Generate a self-signed certificate for the configured server name/IP.
set -euo pipefail

tm_deploy_dir() {
    if [[ -n "${TALENTMIND_DEPLOY_DIR:-}" ]]; then
        printf '%s' "$TALENTMIND_DEPLOY_DIR"
    else
        cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
    fi
}

generate_self_signed() {
    local deploy_dir tls_dir server san log
    deploy_dir="$(tm_deploy_dir)"
    tls_dir="${TALENTMIND_TLS_DIR:-$deploy_dir/tls}"
    server="${TALENTMIND_SERVER_NAME:-}"
    if [[ -z "$server" || "$server" == "_" ]]; then
        server="$(hostname -I 2>/dev/null | awk '{print $1}')"
        [[ -n "$server" ]] || server="127.0.0.1"
    fi
    if [[ "$server" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ || "$server" == *:* ]]; then
        san="IP:$server"
    else
        san="DNS:$server"
    fi
    mkdir -p "$tls_dir"
    log="$(mktemp)"
    if ! MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
        -keyout "$tls_dir/privkey.pem" \
        -out "$tls_dir/fullchain.pem" \
        -subj "/CN=$server" \
        -addext "subjectAltName=$san" >"$log" 2>&1; then
        cat "$log" >&2
        rm -f "$log"
        return 1
    fi
    rm -f "$log"
    chmod 600 "$tls_dir/privkey.pem" 2>/dev/null || true
    chmod 644 "$tls_dir/fullchain.pem" 2>/dev/null || true
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    generate_self_signed
fi
