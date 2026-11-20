#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
# shellcheck source=deploy/scripts/common.sh
source deploy/scripts/common.sh

mini_sql="$repo_root/deploy/tests/fixtures/mini.sql"
tmp_a="$(mktemp -d)"
tmp_b="$(mktemp -d)"
project_a="talentmind-install-a-$$"
project_b="talentmind-install-b-$$"

path_win() {
    cygpath -m "$1" 2>/dev/null || printf '%s' "$1"
}

cleanup() {
    TALENTMIND_PROJECT="$project_a" tm_compose down -v --remove-orphans >/dev/null 2>&1 || true
    TALENTMIND_PROJECT="$project_b" tm_compose down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$tmp_a" "$tmp_b"
}
trap cleanup EXIT

setup_env() {
    local tmp="$1" project="$2" mode="$3" dump="$4"
    export TALENTMIND_ROOT="$tmp/root"
    export TALENTMIND_DEPLOY_DIR="$repo_root/deploy"
    export TALENTMIND_PROJECT="$project"
    export TALENTMIND_DATA_DIR="$(path_win "$tmp/data")"
    export TALENTMIND_ENV_FILE="$(path_win "$tmp/env")"
    export TALENTMIND_NGINX_DIR="$(path_win "$tmp/nginx")"
    export TALENTMIND_AUTH_DIR="$(path_win "$tmp/auth")"
    export TALENTMIND_TLS_DIR="$(path_win "$tmp/tls")"
    export TALENTMIND_HTTP_PORT=18080
    export TALENTMIND_HTTPS_PORT=18443
    export TALENTMIND_SERVER_NAME=127.0.0.1
    export TALENTMIND_TLS_MODE="$mode"
    export TALENTMIND_VERSION=test
    export TALENTMIND_SKIP_ROOT_CHECK=1
    export TALENTMIND_SKIP_DOCKER_INSTALL=1
    export TALENTMIND_MYSQL_DUMP="$dump"
    export TALENTMIND_ADMIN_USER=testuser
    export TALENTMIND_ADMIN_PASSWORD=testpass
    export TALENTMIND_TRUSTED_PROXY_SECRET=proxys3cret
    export MYSQL_ROOT_PASSWORD=rootpass
    export MYSQL_PASSWORD=apppass
    export NEO4J_PASSWORD=neo4jpass
    mkdir -p "$tmp/data/mysql" "$tmp/data/backend" "$tmp/nginx" "$tmp/auth" "$tmp/tls"
}

# Scenario A: import a dump, verify auth, reject a second install/import.
setup_env "$tmp_a" "$project_a" selfsigned "$(path_win "$tmp_a/mini.sql.gz")"
gzip -c "$mini_sql" > "$tmp_a/mini.sql.gz"
install_output="$(bash deploy/scripts/install.sh 2>&1)"
printf '%s\n' "$install_output" | grep -q 'TalentMind is running'
grep -q '^MYSQL_ROOT_PASSWORD=.\+' "$tmp_a/env"
grep -q '^MYSQL_PASSWORD=.\+' "$tmp_a/env"
grep -q '^TALENTMIND_TRUSTED_PROXY_SECRET=.\+' "$tmp_a/env"
[[ -f "$tmp_a/auth/htpasswd" ]]
[[ -f "$tmp_a/tls/fullchain.pem" ]]
if [[ "$(uname -s)" != MINGW* && "$(uname -s)" != MSYS* ]]; then
    [[ "$(stat -c %a "$tmp_a/env")" == "600" ]]
fi

# shellcheck disable=SC1090
set -a; . "$tmp_a/env"; set +a
rows="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B talentmind \
    -e 'SELECT COUNT(*) FROM job_definition')"
[[ "$rows" == "1" ]]
status="$(curl -ks -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" \
    "https://127.0.0.1:18443/api/collection/platforms")"
[[ "$status" == "200" ]]

touch "$tmp_a/data/install-marker"
if bash deploy/scripts/install.sh >/dev/null 2>&1; then
    printf 'second install unexpectedly succeeded\n' >&2
    exit 1
fi
[[ -f "$tmp_a/data/install-marker" ]]
if bash deploy/scripts/import-data.sh >/dev/null 2>&1; then
    printf 'second import unexpectedly succeeded\n' >&2
    exit 1
fi
rows="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B talentmind \
    -e 'SELECT COUNT(*) FROM job_definition')"
[[ "$rows" == "1" ]]
tm_compose down -v >/dev/null 2>&1 || true

# Scenario B: no dump, schema-only import.
setup_env "$tmp_b" "$project_b" off ""
install_output="$(bash deploy/scripts/install.sh 2>&1)"
printf '%s\n' "$install_output" | grep -q 'schema only'
# shellcheck disable=SC1090
set -a; . "$tmp_b/env"; set +a
tables="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B \
    -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='talentmind' AND table_name='job_definition'")"
[[ "$tables" == "1" ]]
rows="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B talentmind \
    -e 'SELECT COUNT(*) FROM job_definition')"
[[ "$rows" == "0" ]]
status="$(curl -s -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" \
    "http://127.0.0.1:18080/api/jobs?page=1&page_size=1")"
[[ "$status" == "200" ]]
status="$(curl -s -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" \
    "http://127.0.0.1:18080/api/m2/delivery/inputs?limit=1&offset=0")"
[[ "$status" == "200" ]]
status="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:18080/healthz")"
[[ "$status" == "200" ]]
tm_compose down -v >/dev/null 2>&1 || true

printf 'install checks passed\n'
