#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
tmp="$(mktemp -d)"
project="talentmind-lifecycle-test-$$"
envfile_posix="$tmp/test.env"
envfile="$(cygpath -m "$envfile_posix" 2>/dev/null || printf '%s' "$envfile_posix")"
data_dir="$(cygpath -m "$tmp/data" 2>/dev/null || printf '%s' "$tmp/data")"
nginx_dir="$(cygpath -m "$tmp/nginx" 2>/dev/null || printf '%s' "$tmp/nginx")"
auth_dir="$(cygpath -m "$tmp/auth" 2>/dev/null || printf '%s' "$tmp/auth")"
tls_dir="$(cygpath -m "$tmp/tls" 2>/dev/null || printf '%s' "$tmp/tls")"

export TALENTMIND_ROOT="$tmp/root"
export TALENTMIND_DEPLOY_DIR="$repo_root/deploy"
export TALENTMIND_ENV_FILE="$envfile"
export TALENTMIND_DATA_DIR="$data_dir"
export TALENTMIND_PROJECT="$project"
export TALENTMIND_HTTP_PORT=18080
export TALENTMIND_HTTPS_PORT=18443
export TALENTMIND_NGINX_DIR="$nginx_dir"
export TALENTMIND_AUTH_DIR="$auth_dir"
export TALENTMIND_TLS_DIR="$tls_dir"
export TALENTMIND_TLS_MODE=off
export TALENTMIND_SERVER_NAME=127.0.0.1
export TALENTMIND_ADMIN_USER=testuser
export TALENTMIND_ADMIN_PASSWORD=testpass
export TALENTMIND_TRUSTED_PROXY_SECRET=proxys3cret
MYSQL_ROOT_PASSWORD=rootpass

mkdir -p "$tmp/data/mysql" "$tmp/data/backend" "$tmp/nginx" "$tmp/auth" "$tmp/tls" deploy/m2

# shellcheck disable=SC1091
source deploy/scripts/common.sh
# shellcheck disable=SC1091
source deploy/scripts/auth.sh
# shellcheck disable=SC1091
source deploy/scripts/render-nginx.sh
generate_basic_auth
render_nginx

cat > "$envfile_posix" <<EOF
TALENTMIND_VERSION=test
TALENTMIND_DATA_DIR=$data_dir
TALENTMIND_ENV_FILE=$envfile
TALENTMIND_NGINX_DIR=$nginx_dir
TALENTMIND_AUTH_DIR=$auth_dir
TALENTMIND_TLS_DIR=$tls_dir
TALENTMIND_HTTP_PORT=18080
TALENTMIND_HTTPS_PORT=18443
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
MYSQL_PASSWORD=apppass
TALENTMIND_TRUSTED_PROXY_SECRET=proxys3cret
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4jpass
REDIS_URL=redis://redis:6379/0
OPENAI_API_KEY=x
OPENAI_BASE_URL=https://example.com/v1
TALENTMIND_M2_CONFIG=/app/deploy/m2/config.json
TALENTMIND_M2_KEY_FILE=/app/deploy/m2/api-key.txt
TALENTMIND_TLS_MODE=off
TALENTMIND_SERVER_NAME=127.0.0.1
EOF

cleanup() {
    tm_compose down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$tmp"
}
trap cleanup EXIT

bash deploy/scripts/start.sh
bash deploy/scripts/start.sh
# Start/status must load ports/TLS/data dir from deploy/.env when the shell has none.
env -u TALENTMIND_HTTP_PORT -u TALENTMIND_HTTPS_PORT -u TALENTMIND_TLS_MODE -u TALENTMIND_DATA_DIR \
    bash deploy/scripts/start.sh
status_output="$(env -u TALENTMIND_HTTP_PORT -u TALENTMIND_HTTPS_PORT -u TALENTMIND_TLS_MODE -u TALENTMIND_DATA_DIR \
    bash deploy/scripts/status.sh)"
printf '%s\n' "$status_output" | grep -q mysql
printf '%s\n' "$status_output" | grep -q backend
printf '%s\n' "$status_output" | grep -q web
printf '%s\n' "$status_output" | grep -qi healthy

bash deploy/scripts/stop.sh
if bash deploy/scripts/status.sh >/dev/null 2>&1; then
    printf 'status succeeded after stop\n' >&2
    exit 1
fi
[[ -d "$tmp/data/backend" ]]

bash deploy/scripts/start.sh

tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot talentmind -e \
    "CREATE TABLE IF NOT EXISTS job_definition (id INT PRIMARY KEY); INSERT IGNORE INTO job_definition VALUES (1);"
count_before="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B talentmind -e 'SELECT COUNT(*) FROM job_definition')"
tm_compose restart backend mysql >/dev/null
tm_wait_healthy
count_after="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B talentmind -e 'SELECT COUNT(*) FROM job_definition')"
[[ "$count_before" == "$count_after" ]]
[[ "$count_after" == "1" ]]
bash deploy/scripts/status.sh >/dev/null

log_output="$(bash deploy/scripts/logs.sh --no-follow)"
[[ -n "$log_output" ]]
printf 'lifecycle checks passed\n'
