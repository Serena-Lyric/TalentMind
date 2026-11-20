#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
tmp="$(mktemp -d)"
project="talentmind-backup-test-$$"
envfile_posix="$tmp/env"
envfile="$(cygpath -m "$envfile_posix" 2>/dev/null || printf '%s' "$envfile_posix")"
data_dir="$(cygpath -m "$tmp/data" 2>/dev/null || printf '%s' "$tmp/data")"
nginx_dir="$(cygpath -m "$tmp/nginx" 2>/dev/null || printf '%s' "$tmp/nginx")"
auth_dir="$(cygpath -m "$tmp/auth" 2>/dev/null || printf '%s' "$tmp/auth")"
tls_dir="$(cygpath -m "$tmp/tls" 2>/dev/null || printf '%s' "$tmp/tls")"
backup_dir="$tmp/backups"

# shellcheck source=deploy/scripts/common.sh
source deploy/scripts/common.sh

export TALENTMIND_ROOT="$tmp/root"
export TALENTMIND_DEPLOY_DIR="$repo_root/deploy"
export TALENTMIND_PROJECT="$project"
export TALENTMIND_DATA_DIR="$data_dir"
export TALENTMIND_ENV_FILE="$envfile"
export TALENTMIND_NGINX_DIR="$nginx_dir"
export TALENTMIND_AUTH_DIR="$auth_dir"
export TALENTMIND_TLS_DIR="$tls_dir"
export TALENTMIND_BACKUP_DIR="$backup_dir"
export TALENTMIND_HTTP_PORT=18080
export TALENTMIND_HTTPS_PORT=18443
export TALENTMIND_SERVER_NAME=127.0.0.1
export TALENTMIND_TLS_MODE=off
export TALENTMIND_VERSION=test
export TALENTMIND_SKIP_ROOT_CHECK=1
export TALENTMIND_SKIP_DOCKER_INSTALL=1
export TALENTMIND_MYSQL_DUMP="$(cygpath -m "$tmp/mini.sql.gz" 2>/dev/null || printf '%s' "$tmp/mini.sql.gz")"
export TALENTMIND_ADMIN_USER=testuser
export TALENTMIND_ADMIN_PASSWORD=testpass
export TALENTMIND_TRUSTED_PROXY_SECRET=proxys3cret
export MYSQL_ROOT_PASSWORD=rootpass
export MYSQL_PASSWORD=apppass
export NEO4J_PASSWORD=neo4jpass

mkdir -p "$tmp/data/mysql" "$tmp/data/backend" "$tmp/nginx" "$tmp/auth" "$tmp/tls"
gzip -c deploy/tests/fixtures/mini.sql > "$tmp/mini.sql.gz"

cleanup() {
    tm_compose down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$tmp"
}
trap cleanup EXIT

bash deploy/scripts/install.sh >/dev/null
# shellcheck disable=SC1090
set -a; . "$envfile_posix"; set +a

bash deploy/scripts/backup.sh >/dev/null
backup_path="$(find "$backup_dir" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"
[[ -n "$backup_path" ]]
for name in mysql.sql.gz backend.tar.gz deploy.tar.gz SHA256SUMS; do
    [[ -f "$backup_path/$name" ]]
done
(cd "$backup_path" && sha256sum -c SHA256SUMS >/dev/null)

bash deploy/scripts/stop.sh >/dev/null
rm -rf "$tmp/data/mysql"
bash deploy/scripts/restore.sh --yes "$backup_path" >/dev/null
# shellcheck disable=SC1090
set -a; . "$envfile_posix"; set +a
rows="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B talentmind \
    -e 'SELECT COUNT(*) FROM job_definition')"
[[ "$rows" == "1" ]]

# Restoring over a non-empty database with --yes must work too.
bash deploy/scripts/restore.sh --yes "$backup_path" >/dev/null
# shellcheck disable=SC1090
set -a; . "$envfile_posix"; set +a
rows="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B talentmind \
    -e 'SELECT COUNT(*) FROM job_definition')"
[[ "$rows" == "1" ]]

if bash deploy/scripts/restore.sh "$backup_path" >/dev/null 2>&1; then
    printf 'restore without --yes unexpectedly succeeded\n' >&2
    exit 1
fi

# Fresh-machine restore: reinitialize the datadir with new secrets, then restore
# the old backup. MySQL users and Nginx proxy config must be reconciled.
tm_compose down -v >/dev/null 2>&1 || true
rm -rf "$tmp/data/mysql" "$tmp/data/backend"
export MYSQL_ROOT_PASSWORD=newroot
export MYSQL_PASSWORD=newapp
export TALENTMIND_TRUSTED_PROXY_SECRET=newproxy
export TALENTMIND_ADMIN_PASSWORD=newpass
export TALENTMIND_MYSQL_DUMP=""
bash deploy/scripts/install.sh >/dev/null
bash deploy/scripts/restore.sh --yes "$backup_path" >/dev/null
# shellcheck disable=SC1090
set -a; . "$envfile_posix"; set +a
rows="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B talentmind \
    -e 'SELECT COUNT(*) FROM job_definition')"
[[ "$rows" == "1" ]]
status="$(curl -s -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" \
    "http://127.0.0.1:18080/api/collection/platforms")"
[[ "$status" == "200" ]]
status="$(curl -s -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" \
    -H 'X-TalentMind-Proxy-Secret: wrong' "http://127.0.0.1:18080/api/collection/raw/1")"
[[ "$status" != "403" ]]
status="$(curl -s -o /dev/null -w '%{http_code}' -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" \
    -H 'Sec-Fetch-Site: cross-site' "http://127.0.0.1:18080/api/collection/raw/1")"
[[ "$status" == "403" ]]

backups_before="$(find "$backup_dir" -mindepth 1 -maxdepth 1 -type d | wc -l)"
bash deploy/scripts/upgrade.sh >/dev/null
backups_after="$(find "$backup_dir" -mindepth 1 -maxdepth 1 -type d | wc -l)"
[[ "$backups_after" -gt "$backups_before" ]]
bash deploy/scripts/status.sh >/dev/null
printf 'backup/restore checks passed\n'
