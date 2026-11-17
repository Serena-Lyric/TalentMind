#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
tmp="$(mktemp -d)"
project="talentmind-auth-test-$$"
envfile_posix="$tmp/test.env"
envfile="$(cygpath -m "$envfile_posix" 2>/dev/null || printf '%s' "$envfile_posix")"
data_dir="$(cygpath -m "$tmp/data" 2>/dev/null || printf '%s' "$tmp/data")"
nginx_dir="$(cygpath -m "$tmp/nginx" 2>/dev/null || printf '%s' "$tmp/nginx")"
auth_dir="$(cygpath -m "$tmp/auth" 2>/dev/null || printf '%s' "$tmp/auth")"
tls_dir="$(cygpath -m "$tmp/tls" 2>/dev/null || printf '%s' "$tmp/tls")"
compose=(docker compose -p "$project" -f deploy/compose.yml)

cleanup() {
    "${compose[@]}" --env-file "$envfile" down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$tmp"
}
trap cleanup EXIT

mkdir -p "$tmp/data/mysql" "$tmp/data/backend" "$tmp/nginx" "$tmp/auth" "$tmp/tls" deploy/m2

export TALENTMIND_DEPLOY_DIR="$repo_root/deploy"
export TALENTMIND_NGINX_DIR="$nginx_dir"
export TALENTMIND_AUTH_DIR="$auth_dir"
export TALENTMIND_TLS_DIR="$tls_dir"
export TALENTMIND_SERVER_NAME=_
export TALENTMIND_ADMIN_USER=testuser
export TALENTMIND_ADMIN_PASSWORD=testpass
export TALENTMIND_TRUSTED_PROXY_SECRET=proxys3cret

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
MYSQL_ROOT_PASSWORD=rootpass
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
TALENTMIND_TLS_MODE=selfsigned
TALENTMIND_SERVER_NAME=_
EOF

"${compose[@]}" --env-file "$envfile" up -d mysql backend web
base="http://127.0.0.1:18080"
ready=0
for _ in $(seq 1 60); do
    if curl -s -o /dev/null "$base/healthz"; then
        ready=1
        break
    fi
    sleep 2
done
if [[ "$ready" -ne 1 ]]; then
    "${compose[@]}" --env-file "$envfile" logs --tail=80 mysql backend web
    printf 'web did not become ready\n' >&2
    exit 1
fi

status="$(curl -s -o /dev/null -w '%{http_code}' "$base/")"
[[ "$status" == "401" ]] || { printf 'expected 401 without auth, got %s\n' "$status" >&2; exit 1; }
status="$(curl -s -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" "$base/")"
[[ "$status" == "200" ]] || { printf 'expected 200 with auth, got %s\n' "$status" >&2; exit 1; }

payload="$(curl -s -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" "$base/api/collection/platforms")"
python_bin=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -c 'import json' >/dev/null 2>&1; then
        python_bin="$candidate"
        break
    fi
done
"$python_bin" -c 'import json,sys; assert json.loads(sys.argv[1])["code"] == 0' "$payload"

status="$(curl -s -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" \
    -H 'X-TalentMind-Proxy-Secret: wrong' "$base/api/collection/raw/1")"
[[ "$status" != "403" ]] || { printf 'nginx did not overwrite proxy secret\n' >&2; exit 1; }

status="$(curl -s -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" \
    -H 'Sec-Fetch-Site: cross-site' "$base/api/collection/raw/1")"
[[ "$status" == "403" ]] || { printf 'cross-site request was not rejected: %s\n' "$status" >&2; exit 1; }

[[ -f "$tmp/auth/htpasswd" ]]
if [[ "$(uname -s)" != MINGW* && "$(uname -s)" != MSYS* ]]; then
    mode="$(stat -c %a "$tmp/auth/.credentials")"
    [[ "$mode" == "600" ]] || { printf 'credentials mode is %s, expected 600\n' "$mode" >&2; exit 1; }
fi
printf 'nginx auth checks passed\n'
