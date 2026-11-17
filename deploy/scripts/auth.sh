#!/usr/bin/env bash
# Generate the Nginx Basic Auth file and one-time credentials.
set -euo pipefail

tm_deploy_dir() {
    if [[ -n "${TALENTMIND_DEPLOY_DIR:-}" ]]; then
        printf '%s' "$TALENTMIND_DEPLOY_DIR"
    else
        cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
    fi
}

generate_basic_auth() {
    local deploy_dir auth_dir user password hash
    deploy_dir="$(tm_deploy_dir)"
    auth_dir="${TALENTMIND_AUTH_DIR:-$deploy_dir/auth}"
    user="${TALENTMIND_ADMIN_USER:-admin}"
    password="${TALENTMIND_ADMIN_PASSWORD:-}"
    if [[ -z "$password" ]]; then
        password="$(openssl rand -hex 24)"
    fi
    hash="$(openssl passwd -apr1 "$password")"
    mkdir -p "$auth_dir"
    printf '%s:%s\n' "$user" "$hash" > "$auth_dir/htpasswd"
    chmod 640 "$auth_dir/htpasswd" 2>/dev/null || true
    if ! chgrp 101 "$auth_dir/htpasswd" 2>/dev/null; then
        chmod 644 "$auth_dir/htpasswd" 2>/dev/null || true
    fi
    printf 'TALENTMIND_ADMIN_USER=%s\nTALENTMIND_ADMIN_PASSWORD=%s\n' \
        "$user" "$password" > "$auth_dir/.credentials"
    chmod 600 "$auth_dir/.credentials" 2>/dev/null || true
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    generate_basic_auth
fi
