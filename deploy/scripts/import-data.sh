#!/usr/bin/env bash
# Import the MySQL dump (or schema-only DDL) into a fresh database.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/common.sh
source "$script_dir/common.sh"

source_env() {
    local env_file
    env_file="$(tm_env_file)"
    [[ -f "$env_file" ]] || tm_die "missing env file: $env_file"
    set -a
    # shellcheck disable=SC1090
    . "$env_file"
    set +a
}

mysql_is_empty() {
    local count
    count="$(tm_compose exec -T -e MYSQL_PWD="${MYSQL_ROOT_PASSWORD:-}" mysql mysql -uroot -N -B \
        -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='talentmind'" 2>/dev/null || printf '0')"
    [[ "$count" == "0" ]]
}

import_data() {
    local force=0 dump ddl repo_root tables rows
    if [[ "${1:-}" == "--force" ]]; then
        force=1
    fi
    source_env
    if ! mysql_is_empty && [[ "$force" -eq 0 ]]; then
        tm_log "database talentmind is not empty; refusing to import (use --force to override)"
        return 1
    fi

    repo_root="$(cd "$(tm_deploy_dir)/.." && pwd)"
    if [[ -n "${TALENTMIND_MYSQL_DUMP:-}" ]]; then
        dump="$TALENTMIND_MYSQL_DUMP"
    elif [[ -f "$(tm_deploy_dir)/data/mysql/talentmind.sql.gz" ]]; then
        dump="$(tm_deploy_dir)/data/mysql/talentmind.sql.gz"
    else
        dump=""
    fi

    if [[ -n "$dump" ]]; then
        [[ -f "$dump" ]] || { tm_log "dump not found: $dump"; return 1; }
        gunzip -c "$dump" | tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" \
            mysql mysql -uroot talentmind
        tm_log "imported MySQL dump: $dump"
    else
        ddl="$repo_root/backend/app/contracts/ddl.sql"
        [[ -f "$ddl" ]] || { tm_log "schema file not found: $ddl"; return 1; }
        tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" \
            mysql mysql -uroot talentmind < "$ddl"
        tm_log "schema only: no data dump found; imported ddl.sql"
    fi

    tables="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B \
        -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='talentmind' AND table_name='job_definition'" 2>/dev/null || printf '0')"
    if [[ "$tables" == "1" ]]; then
        rows="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql -uroot -N -B \
            -e "SELECT COUNT(*) FROM talentmind.job_definition" 2>/dev/null || printf '0')"
        tm_log "job_definition rows: $rows"
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    import_data "$@"
fi
