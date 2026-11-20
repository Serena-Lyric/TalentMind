#!/usr/bin/env bash
# First-run installer: secrets, TLS, Nginx, images, MySQL import and health.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/common.sh
source "$script_dir/common.sh"
# shellcheck source=deploy/scripts/auth.sh
source "$script_dir/auth.sh"
# shellcheck source=deploy/scripts/render-nginx.sh
source "$script_dir/render-nginx.sh"

if [[ "${TALENTMIND_SKIP_ROOT_CHECK:-0}" != "1" ]]; then
    tm_require_root
fi

if tm_is_initialized; then
    tm_die "existing TalentMind data found in $(tm_data_dir); refusing to overwrite. Use start.sh/status.sh or an explicit restore."
fi

if command -v docker >/dev/null 2>&1; then
    project="${TALENTMIND_PROJECT:-talentmind}"
    existing="$(docker ps -a --filter "label=com.docker.compose.project=$project" --format '{{.Names}}' 2>/dev/null | head -n 1 || true)"
    if [[ -n "$existing" ]]; then
        tm_die "existing TalentMind containers found for project $project ($existing); refusing to overwrite. Use start.sh/status.sh or an explicit restore."
    fi
fi

if [[ "${TALENTMIND_SKIP_DOCKER_INSTALL:-0}" != "1" ]]; then
    # shellcheck source=deploy/scripts/install-docker.sh
    source "$script_dir/install-docker.sh"
    ensure_docker
    write_daemon_config
    configure_swappiness
    systemctl restart docker
fi

deploy_dir="$(tm_deploy_dir)"
data_dir="$(tm_data_dir)"
env_file="$(tm_env_file)"
nginx_dir="${TALENTMIND_NGINX_DIR:-$deploy_dir/nginx}"
auth_dir="${TALENTMIND_AUTH_DIR:-$deploy_dir/auth}"
tls_dir="${TALENTMIND_TLS_DIR:-$deploy_dir/tls}"

mkdir -p "$data_dir/mysql" "$data_dir/backend" "$deploy_dir/m2" \
    "$nginx_dir" "$auth_dir" "$tls_dir" "$(dirname "$env_file")"
chmod 644 "$deploy_dir/mysql/my.cnf" 2>/dev/null || true
chown -R 999:999 "$data_dir/mysql" 2>/dev/null || true
chown -R 1000:1000 "$data_dir/backend" "$deploy_dir/m2" 2>/dev/null || true

root_password="${MYSQL_ROOT_PASSWORD:-$(openssl rand -hex 24)}"
app_password="${MYSQL_PASSWORD:-$(openssl rand -hex 24)}"
proxy_secret="${TALENTMIND_TRUSTED_PROXY_SECRET:-$(openssl rand -hex 24)}"
admin_user="${TALENTMIND_ADMIN_USER:-admin}"
admin_password="${TALENTMIND_ADMIN_PASSWORD:-$(openssl rand -hex 24)}"
neo4j_password="${NEO4J_PASSWORD:-$(openssl rand -hex 24)}"

model_env="${TALENTMIND_MODEL_ENV:-$deploy_dir/model.env}"
if [[ -f "$model_env" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "$model_env"
    set +a
fi

export TALENTMIND_DEPLOY_DIR="$deploy_dir"
export TALENTMIND_DATA_DIR="$data_dir"
export TALENTMIND_ENV_FILE="$env_file"
export TALENTMIND_NGINX_DIR="$nginx_dir"
export TALENTMIND_AUTH_DIR="$auth_dir"
export TALENTMIND_TLS_DIR="$tls_dir"
export TALENTMIND_SERVER_NAME="${TALENTMIND_SERVER_NAME:-_}"
export TALENTMIND_TLS_MODE="${TALENTMIND_TLS_MODE:-selfsigned}"
export TALENTMIND_HTTP_PORT="${TALENTMIND_HTTP_PORT:-80}"
export TALENTMIND_HTTPS_PORT="${TALENTMIND_HTTPS_PORT:-443}"
export TALENTMIND_ADMIN_USER="$admin_user"
export TALENTMIND_ADMIN_PASSWORD="$admin_password"
export TALENTMIND_TRUSTED_PROXY_SECRET="$proxy_secret"
export MYSQL_ROOT_PASSWORD="$root_password"
export MYSQL_PASSWORD="$app_password"
export NEO4J_PASSWORD="$neo4j_password"

cat > "$env_file" <<EOF
TALENTMIND_VERSION=${TALENTMIND_VERSION:-dev}
TALENTMIND_DATA_DIR=$data_dir
TALENTMIND_ENV_FILE=$env_file
TALENTMIND_NGINX_DIR=$nginx_dir
TALENTMIND_AUTH_DIR=$auth_dir
TALENTMIND_TLS_DIR=$tls_dir
TALENTMIND_HTTP_PORT=${TALENTMIND_HTTP_PORT}
TALENTMIND_HTTPS_PORT=${TALENTMIND_HTTPS_PORT}
TALENTMIND_SERVER_NAME=${TALENTMIND_SERVER_NAME}
TALENTMIND_TLS_MODE=${TALENTMIND_TLS_MODE}
TALENTMIND_ADMIN_USER=$admin_user
TALENTMIND_ADMIN_PASSWORD=$admin_password
MYSQL_ROOT_PASSWORD=$root_password
MYSQL_PASSWORD=$app_password
TALENTMIND_TRUSTED_PROXY_SECRET=$proxy_secret
NEO4J_URI=${NEO4J_URI:-bolt://neo4j:7687}
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=$neo4j_password
REDIS_URL=${REDIS_URL:-redis://redis:6379/0}
OPENAI_API_KEY=${OPENAI_API_KEY:-}
OPENAI_BASE_URL=${OPENAI_BASE_URL:-https://api.deepseek.com/v1}
LLM_API_KEY=${LLM_API_KEY:-}
LLM_BASE_URL=${LLM_BASE_URL:-https://api.deepseek.com/v1}
TALENTMIND_M2_CONFIG=/app/deploy/m2/config.json
TALENTMIND_M2_KEY_FILE=/app/deploy/m2/api-key.txt
TALENTMIND_REGISTRY_MIRROR=${TALENTMIND_REGISTRY_MIRROR:-https://mirror.ccs.tencentyun.com}
EOF
chmod 600 "$env_file" 2>/dev/null || true

generate_basic_auth
render_nginx

shopt -s nullglob
for archive in "$deploy_dir"/images/*.tar; do
    tm_log "loading image archive: $archive"
    docker load -i "$archive"
done
shopt -u nullglob

if ! docker image inspect mysql:8.0 >/dev/null 2>&1; then
    if declare -F verify_docker_pull >/dev/null 2>&1; then
        verify_docker_pull mysql:8.0 || tm_die "mysql:8.0 is missing and Docker Hub pull failed; load deploy/images or fix the registry mirror"
    else
        tm_die "mysql:8.0 is missing; load deploy/images or install Docker Hub access"
    fi
fi

tm_compose up -d mysql
if ! tm_wait_service_healthy mysql 120; then
    tm_compose logs --tail=50 mysql || true
    tm_die "MySQL did not become healthy"
fi

if [[ -n "${TALENTMIND_MYSQL_DUMP:-}" ]]; then
    export TALENTMIND_MYSQL_DUMP
elif [[ -f "$deploy_dir/data/mysql/talentmind.sql.gz" ]]; then
    export TALENTMIND_MYSQL_DUMP="$deploy_dir/data/mysql/talentmind.sql.gz"
else
    unset TALENTMIND_MYSQL_DUMP
fi
if ! bash "$script_dir/import-data.sh"; then
    tm_compose logs --tail=50 mysql || true
    tm_die "first-run data import failed"
fi

tm_compose up -d backend web
if ! tm_wait_healthy 120; then
    tm_compose logs --tail=80 backend web || true
    tm_die "backend/web did not become healthy"
fi

scheme="https"
port="$TALENTMIND_HTTPS_PORT"
if [[ "$TALENTMIND_TLS_MODE" == "off" ]]; then
    scheme="http"
    port="$TALENTMIND_HTTP_PORT"
fi
server="$TALENTMIND_SERVER_NAME"
if [[ "$server" == "_" ]]; then
    server="$(hostname -I 2>/dev/null | awk '{print $1}')"
    [[ -n "$server" ]] || server="127.0.0.1"
fi
tm_log "TalentMind is running: ${scheme}://${server}:${port}/"
tm_log "Basic Auth username: $admin_user"
tm_log "Basic Auth password: $admin_password"
tm_log "Credentials are also stored in $auth_dir/.credentials (mode 600)."
