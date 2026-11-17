#!/usr/bin/env bash
# Consistent MySQL + backend data + deploy secrets backup.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/common.sh
source "$script_dir/common.sh"
# shellcheck source=deploy/scripts/import-data.sh
source "$script_dir/import-data.sh"

source_env

backup_root="${TALENTMIND_BACKUP_DIR:-$(tm_root)/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
destination="$backup_root/$timestamp"
data_dir="$(tm_data_dir)"
deploy_dir="$(tm_deploy_dir)"
data_dir_tar="$(cygpath -u "$data_dir" 2>/dev/null || printf '%s' "$data_dir")"
backend_was_running=0
[[ -n "$(tm_compose ps -q backend 2>/dev/null || true)" ]] && backend_was_running=1

restore_backend() {
    if [[ "$backend_was_running" -eq 1 ]]; then
        tm_compose start backend >/dev/null 2>&1 || true
        tm_wait_service_healthy backend 60 >/dev/null 2>&1 || true
    fi
}

mkdir -p "$destination"
chmod 700 "$destination" 2>/dev/null || true
trap restore_backend EXIT

tm_compose up -d mysql >/dev/null
tm_wait_service_healthy mysql 120
if [[ "$backend_was_running" -eq 1 ]]; then
    tm_compose stop backend >/dev/null
fi

tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysqldump -uroot \
    --single-transaction --routines --triggers --events --no-tablespaces talentmind \
    | gzip > "$destination/mysql.sql.gz"

if [[ -d "$data_dir_tar/backend" ]]; then
    tar -czf "$destination/backend.tar.gz" -C "$data_dir_tar" backend
else
    tar -czf "$destination/backend.tar.gz" -T /dev/null
fi

deploy_items=()
for item in .env auth tls m2; do
    [[ -e "$deploy_dir/$item" ]] && deploy_items+=("$item")
done
if [[ "${#deploy_items[@]}" -eq 0 ]]; then
    tm_die "no deploy files to back up in $deploy_dir"
fi
tar -czf "$destination/deploy.tar.gz" -C "$deploy_dir" "${deploy_items[@]}"

(
    cd "$destination"
    sha256sum mysql.sql.gz backend.tar.gz deploy.tar.gz > SHA256SUMS
)
chmod 600 "$destination"/* 2>/dev/null || true
tm_log "backup written to $destination"
