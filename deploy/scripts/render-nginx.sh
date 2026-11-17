#!/usr/bin/env bash
# Render the runtime Nginx configuration from the tracked template.
set -euo pipefail

tm_deploy_dir() {
    if [[ -n "${TALENTMIND_DEPLOY_DIR:-}" ]]; then
        printf '%s' "$TALENTMIND_DEPLOY_DIR"
    else
        cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
    fi
}

tm_python() {
    local candidate
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 \
            && "$candidate" -c 'import json' >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    printf 'python3'
}

render_nginx() {
    local deploy_dir template output server secret python_bin
    deploy_dir="$(tm_deploy_dir)"
    template="${TALENTMIND_NGINX_TEMPLATE:-$deploy_dir/web/nginx-http.conf.template}"
    output="${TALENTMIND_NGINX_DIR:-$deploy_dir/nginx}/default.conf"
    server="${TALENTMIND_SERVER_NAME:-_}"
    secret="${TALENTMIND_TRUSTED_PROXY_SECRET:-}"
    if [[ -z "$secret" ]]; then
        printf 'TALENTMIND_TRUSTED_PROXY_SECRET is required\n' >&2
        return 1
    fi
    if [[ ! -f "$template" ]]; then
        printf 'nginx template not found: %s\n' "$template" >&2
        return 1
    fi
    python_bin="$(tm_python)"
    mkdir -p "$(dirname "$output")"
    "$python_bin" - "$template" "$output" "$server" "$secret" <<'PY'
from pathlib import Path
import sys

template, output, server, secret = sys.argv[1:5]
text = Path(template).read_text(encoding="utf-8")
text = text.replace("__SERVER_NAME__", server).replace("__PROXY_SECRET__", secret)
Path(output).write_text(text, encoding="utf-8")
PY
    chmod 600 "$output" 2>/dev/null || true
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    render_nginx
fi
