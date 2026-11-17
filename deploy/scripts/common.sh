#!/usr/bin/env bash
# Shared paths and Compose helpers for deployment scripts.
set -euo pipefail

tm_log() {
    printf '[talentmind] %s\n' "$*"
}

tm_die() {
    printf '[talentmind] ERROR: %s\n' "$*" >&2
    exit 1
}

tm_script_dir() {
    cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

tm_root() {
    printf '%s' "${TALENTMIND_ROOT:-/opt/talentmind}"
}

tm_deploy_dir() {
    if [[ -n "${TALENTMIND_DEPLOY_DIR:-}" ]]; then
        printf '%s' "$TALENTMIND_DEPLOY_DIR"
    elif [[ -f "$PWD/deploy/compose.yml" ]]; then
        printf '%s/deploy' "$PWD"
    else
        cd "$(tm_script_dir)/.." && pwd
    fi
}

tm_env_file() {
    printf '%s' "${TALENTMIND_ENV_FILE:-$(tm_deploy_dir)/.env}"
}

tm_data_dir() {
    printf '%s' "${TALENTMIND_DATA_DIR:-$(tm_root)/data}"
}

tm_compose() {
    local project="${TALENTMIND_PROJECT:-talentmind}"
    local env_file
    local compose_file
    env_file="$(tm_env_file)"
    compose_file="$(tm_deploy_dir)/compose.yml"
    if docker compose version >/dev/null 2>&1; then
        docker compose -p "$project" --env-file "$env_file" -f "$compose_file" "$@"
    elif command -v docker-compose >/dev/null 2>&1; then
        docker-compose -p "$project" --env-file "$env_file" -f "$compose_file" "$@"
    else
        tm_die "docker compose is not available"
    fi
}

tm_wait_healthy() {
    local timeout="${1:-90}"
    local http_port="${TALENTMIND_HTTP_PORT:-80}"
    local deadline=$((SECONDS + timeout))
    local mysql_cid mysql_health
    while (( SECONDS < deadline )); do
        mysql_cid="$(tm_compose ps -q mysql 2>/dev/null || true)"
        if [[ -n "$mysql_cid" ]]; then
            mysql_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$mysql_cid" 2>/dev/null || printf 'unknown')"
        else
            mysql_health="missing"
        fi
        if [[ "$mysql_health" == "healthy" ]] \
            && tm_compose exec -T backend python -c \
                "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18000/health')" \
                >/dev/null 2>&1 \
            && curl -fsS "http://127.0.0.1:${http_port}/healthz" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    tm_log "services did not become healthy within ${timeout}s"
    return 1
}

tm_require_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        tm_die "run as root (or use sudo)"
    fi
}

tm_is_initialized() {
    local data_dir
    data_dir="$(tm_data_dir)"
    [[ -d "$data_dir" ]] && find "$data_dir" -mindepth 1 -print -quit | grep -q .
}
