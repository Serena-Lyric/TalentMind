#!/usr/bin/env bash
# Restore a backup produced by backup.sh. Destructive: requires --yes.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/common.sh
source "$script_dir/common.sh"
# shellcheck source=deploy/scripts/import-data.sh
source "$script_dir/import-data.sh"

confirm=0
if [[ "${1:-}" == "--yes" ]]; then
    confirm=1
    shift
fi
backup_dir="${1:-}"
if [[ -z "$backup_dir" || ! -d "$backup_dir" ]]; then
    tm_die "usage: restore.sh --yes <backup-directory>"
fi
if [[ "$confirm" -ne 1 ]]; then
    tm_die "restore overwrites the database and deploy secrets; pass --yes to confirm"
fi
for name in mysql.sql.gz backend.tar.gz deploy.tar.gz SHA256SUMS; do
    [[ -f "$backup_dir/$name" ]] || tm_die "backup is missing $name"
done
(
    cd "$backup_dir"
    sha256sum -c SHA256SUMS >/dev/null
)

source_env
data_dir="$(tm_data_dir)"
deploy_dir="$(tm_deploy_dir)"
data_dir_tar="$(cygpath -u "$data_dir" 2>/dev/null || printf '%s' "$data_dir")"

tm_compose stop backend web >/dev/null 2>&1 || true
tm_compose up -d mysql >/dev/null
tm_wait_service_healthy mysql 120

if ! mysql_is_empty; then
    tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot \
        -e "DROP DATABASE IF EXISTS talentmind; CREATE DATABASE talentmind CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
fi
gunzip -c "$backup_dir/mysql.sql.gz" | tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" \
    mysql mysql -uroot talentmind

rm -rf "$data_dir_tar/backend"
mkdir -p "$data_dir_tar"
tar -xzf "$backup_dir/backend.tar.gz" -C "$data_dir_tar"
tar -xzf "$backup_dir/deploy.tar.gz" -C "$deploy_dir"
chmod 600 "$(tm_env_file)" 2>/dev/null || true
[[ -f "$deploy_dir/auth/.credentials" ]] && chmod 600 "$deploy_dir/auth/.credentials" 2>/dev/null || true
[[ -f "$deploy_dir/tls/privkey.pem" ]] && chmod 600 "$deploy_dir/tls/privkey.pem" 2>/dev/null || true
source_env

tm_compose up -d backend web
tm_wait_healthy 120
tm_log "restore complete from $backup_dir"
