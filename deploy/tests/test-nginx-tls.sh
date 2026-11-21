#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
tmp="$(mktemp -d)"
project="talentmind-tls-test-$$"
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
export TALENTMIND_SERVER_NAME=127.0.0.1
export TALENTMIND_ADMIN_USER=testuser
export TALENTMIND_ADMIN_PASSWORD=testpass
export TALENTMIND_TRUSTED_PROXY_SECRET=proxys3cret
export TALENTMIND_TLS_MODE=selfsigned

# shellcheck disable=SC1091
source deploy/scripts/auth.sh
# shellcheck disable=SC1091
source deploy/scripts/render-nginx.sh
generate_basic_auth
render_nginx

openssl x509 -in "$tmp/tls/fullchain.pem" -noout -text | grep -Eq 'IP Address:127\.0\.0\.1|DNS:127\.0\.0\.1'

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
TALENTMIND_M2_CONFIG=/app/deploy/m2/config.json
TALENTMIND_M2_KEY_FILE=/app/deploy/m2/api-key.txt
TALENTMIND_TLS_MODE=selfsigned
TALENTMIND_SERVER_NAME=127.0.0.1
EOF

"${compose[@]}" --env-file "$envfile" up -d mysql backend web
https="https://127.0.0.1:18443"
http="http://127.0.0.1:18080"
ready=0
for _ in $(seq 1 60); do
    if curl -ks -o /dev/null "$https/"; then
        ready=1
        break
    fi
    sleep 2
done
if [[ "$ready" -ne 1 ]]; then
    "${compose[@]}" --env-file "$envfile" logs --tail=80 mysql backend web
    printf 'https web did not become ready\n' >&2
    exit 1
fi

status="$(curl -ks -o /dev/null -w '%{http_code}' "$https/")"
[[ "$status" == "401" ]] || { printf 'expected 401 over https without auth, got %s\n' "$status" >&2; exit 1; }
status="$(curl -ks -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" "$https/")"
[[ "$status" == "200" ]] || { printf 'expected 200 over https with auth, got %s\n' "$status" >&2; exit 1; }
status="$(curl -s -o /dev/null -w '%{http_code}' "$http/")"
[[ "$status" == "301" || "$status" == "308" ]] || { printf 'expected http redirect, got %s\n' "$status" >&2; exit 1; }

export TALENTMIND_TLS_MODE=off
render_nginx
if grep -Fq 'listen 443' "$tmp/nginx/default.conf"; then
    printf 'TLS_MODE=off still rendered an HTTPS listener\n' >&2
    exit 1
fi
"${compose[@]}" --env-file "$envfile" restart web >/dev/null
ready=0
for _ in $(seq 1 30); do
    if curl -s -o /dev/null "$http/"; then
        ready=1
        break
    fi
    sleep 2
done
[[ "$ready" -eq 1 ]]
status="$(curl -s -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" "$http/")"
[[ "$status" == "200" ]] || { printf 'expected 200 over http with TLS off, got %s\n' "$status" >&2; exit 1; }

export TALENTMIND_TLS_MODE=files
export TALENTMIND_TLS_DIR="$(cygpath -m "$tmp/missing-tls" 2>/dev/null || printf '%s' "$tmp/missing-tls")"
if render_nginx; then
    printf 'TLS_MODE=files accepted missing certificates\n' >&2
    exit 1
fi

printf 'nginx tls checks passed\n'
