#!/usr/bin/env bash
# Build the public code/images archives and the private data archive for the
# Ubuntu deployment. Reads private data but never prints secrets.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

version="$(date -u +%Y%m%d-%H%M%S)"
output_dir="data/local/deploy"
skip_images=0
skip_data=0
split_images=0
mysql_container="talentmind-mysql-1"
m2_config="data/local/m2-p1-review3-20261102/deepseek-flash-20261102.json"
m2_key="data/local/m2-p1-20261029/api-key.txt"
model_env_source="backend/.env"
python_cmd=""

log() {
    printf '[package] %s\n' "$*"
}

die() {
    printf '[package] ERROR: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'USAGE'
Usage: bash scripts/package-deploy.sh [options]

Options:
  --version V             Package version (default: UTC yyyyMMdd-HHmmss)
  --output-dir DIR        Output directory (default: data/local/deploy)
  --skip-images           Do not build or save Docker images
  --skip-data             Do not export MySQL/M2 data or private configs
  --split-images          Always emit a separate talentmind-images-<V>.tar.gz
  --mysql-container NAME  MySQL container (default: talentmind-mysql-1)
  --m2-config PATH        M2 processor config JSON
  --m2-key PATH           M2 processor API key file
  --model-env-source PATH Source for OPENAI_*/LLM_* model settings
  -h, --help              Show this help

Code archives are written to data/local/deploy/ unless --output-dir is given.
The data archive contains private data and must not be published.
USAGE
}

parse_args() {
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            --version) [[ "$#" -ge 2 ]] || die "--version needs a value"; version="$2"; shift 2 ;;
            --output-dir) [[ "$#" -ge 2 ]] || die "--output-dir needs a value"; output_dir="$2"; shift 2 ;;
            --skip-images) skip_images=1; shift ;;
            --skip-data) skip_data=1; shift ;;
            --split-images) split_images=1; shift ;;
            --mysql-container) [[ "$#" -ge 2 ]] || die "--mysql-container needs a value"; mysql_container="$2"; shift 2 ;;
            --m2-config) [[ "$#" -ge 2 ]] || die "--m2-config needs a value"; m2_config="$2"; shift 2 ;;
            --m2-key) [[ "$#" -ge 2 ]] || die "--m2-key needs a value"; m2_key="$2"; shift 2 ;;
            --model-env-source) [[ "$#" -ge 2 ]] || die "--model-env-source needs a value"; model_env_source="$2"; shift 2 ;;
            -h|--help) usage; exit 0 ;;
            *) die "unknown option: $1 (use --help)" ;;
        esac
    done
}

resolve_path() {
    local path="$1"
    case "$path" in
        /*) printf '%s' "$path" ;;
        [A-Za-z]:*) printf '%s' "$path" ;;
        *) printf '%s/%s' "$repo_root" "$path" ;;
    esac
}

host_path() {
    cygpath -m "$1" 2>/dev/null || printf '%s' "$1"
}

find_python() {
    local candidate
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 \
            && "$candidate" -c 'import sys, sqlite3' >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    return 1
}

check_prerequisites() {
    command -v git >/dev/null 2>&1 || die "missing required command: git"
    command -v tar >/dev/null 2>&1 || die "missing required command: tar"
    command -v gzip >/dev/null 2>&1 || die "missing required command: gzip"
    command -v sha256sum >/dev/null 2>&1 || die "missing required command: sha256sum"
    python_cmd="$(find_python)" || die "missing required command: python3/python with sqlite3"
    if [[ "$skip_images" -eq 0 || "$skip_data" -eq 0 ]]; then
        command -v docker >/dev/null 2>&1 || die "missing required command: docker"
        docker compose version >/dev/null 2>&1 || die "docker compose is not available"
    fi
    if [[ "$split_images" -eq 1 && "$skip_images" -eq 1 ]]; then
        die "--split-images cannot be combined with --skip-images"
    fi
}

prepare_output() {
    if [[ "$skip_images" -eq 1 && "$skip_data" -eq 1 ]]; then
        log "code-only run: images and data are skipped"
    fi
    if [[ -n "$(git status --porcelain)" ]]; then
        log "WARNING: working tree has uncommitted changes; packages come from HEAD only"
    fi
    output_dir="$(resolve_path "$output_dir")"
    mkdir -p "$output_dir"
    output_dir="$(cd "$output_dir" && pwd)"
    m2_config="$(resolve_path "$m2_config")"
    m2_key="$(resolve_path "$m2_key")"
    model_env_source="$(resolve_path "$model_env_source")"
}

stage_code_tree() {
    mkdir -p "$stage_code/app"
    log "exporting git HEAD to the code staging tree"
    git archive HEAD | tar -x -C "$stage_code/app"
    mkdir -p "$stage_code/app/deploy/images"
}

save_image() {
    local image="$1"
    local name="$2"
    local destination="$stage_code/app/deploy/images/$name.tar"
    log "saving image $image -> deploy/images/$name.tar"
    docker save -o "$(host_path "$destination")" "$image"
    [[ -s "$destination" ]] || die "saved image archive is empty: $destination"
}

ensure_base_image() {
    local image="$1"
    if ! docker image inspect "$image" >/dev/null 2>&1; then
        log "pulling base image $image"
        docker pull --platform linux/amd64 "$image"
    fi
}

stage_images() {
    log "building talentmind-backend:$version (linux/amd64)"
    docker build --platform linux/amd64 -f deploy/backend/Dockerfile \
        -t "talentmind-backend:$version" .
    log "building talentmind-web:$version (linux/amd64)"
    docker build --platform linux/amd64 -f deploy/web/Dockerfile \
        -t "talentmind-web:$version" .
    ensure_base_image mysql:8.0
    ensure_base_image neo4j:5-community
    ensure_base_image redis:7-alpine
    save_image "talentmind-backend:$version" backend
    save_image "talentmind-web:$version" web
    save_image mysql:8.0 mysql
    save_image neo4j:5-community neo4j
    save_image redis:7-alpine redis
}

write_package_env() {
    printf 'TALENTMIND_VERSION=%s\n' "$version" \
        > "$stage_code/app/deploy/package.env"
}

ensure_mysql_running() {
    docker inspect "$mysql_container" >/dev/null 2>&1 \
        || die "MySQL container not found: $mysql_container"
    if [[ "$(docker inspect --format '{{.State.Running}}' "$mysql_container")" != "true" ]]; then
        log "starting MySQL container $mysql_container"
        docker start "$mysql_container" >/dev/null
    fi
    local deadline=$((SECONDS + 120))
    while (( SECONDS < deadline )); do
        if docker exec "$mysql_container" bash -c \
            'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqladmin ping -uroot --silent' >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    die "MySQL container $mysql_container did not become ready"
}

mysql_exec() {
    local container="$1"
    shift
    docker exec "$container" bash -c \
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot "$@"' mysql "$@"
}

dump_mysql() {
    local destination="$1"
    log "dumping MySQL database talentmind (single transaction)"
    docker exec "$mysql_container" bash -c \
        'set -o pipefail; MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --routines --triggers --events --no-tablespaces talentmind | gzip -9' \
        > "$destination"
    [[ -s "$destination" ]] || die "MySQL dump is empty"
    chmod 600 "$destination" 2>/dev/null || true
}

query_mysql_rows() {
    local destination="$1"
    local tables=(jd_pool job_definition job_change_log job_skill signal skill_dict resume talent_raw)
    local table query=""
    for table in "${tables[@]}"; do
        query+="SELECT '$table', COUNT(*) FROM \`$table\` UNION ALL "
    done
    query="${query% UNION ALL }"
    mysql_exec "$mysql_container" -N -B talentmind -e "$query" > "$destination"
}

backup_sqlite() {
    local source="$1"
    local destination="$2"
    [[ -f "$source" ]] || die "SQLite database not found: $source"
    mkdir -p "$(dirname "$destination")"
    "$python_cmd" - "$(host_path "$source")" "$(host_path "$destination")" <<'PY'
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(newline="\n")
source_path, destination_path = sys.argv[1], sys.argv[2]
uri = Path(source_path).resolve().as_uri() + "?mode=ro"
source = sqlite3.connect(uri, uri=True)
target = sqlite3.connect(destination_path)
try:
    source.backup(target)
finally:
    target.close()
    source.close()

check = sqlite3.connect(destination_path)
try:
    rows = [str(row[0]) for row in check.execute("PRAGMA integrity_check")]
finally:
    check.close()
if rows != ["ok"]:
    print("; ".join(rows))
    sys.exit(1)
print("ok")
PY
}

copy_m2_product() {
    local source_dir="$1"
    local destination_dir="$2"
    local name
    for name in runs graphs native-reports; do
        [[ -d "$source_dir/$name" ]] || die "missing M2 directory: $source_dir/$name"
    done
    mkdir -p "$destination_dir"
    ( cd "$source_dir" && tar --exclude='*.lock' --exclude='*-wal' --exclude='*-shm' \
        -cf - runs graphs native-reports ) | tar -C "$destination_dir" -xf -
}

copy_state_dirs() {
    local source_root="$1"
    local destination_root="$2"
    local run
    for run in sequence-head-final dev-head-final; do
        [[ -d "$source_root/$run/state" ]] \
            || die "missing M2 state directory: $source_root/$run/state"
        mkdir -p "$destination_root/$run"
        ( cd "$source_root/$run" && tar --exclude='*.lock' --exclude='*-wal' --exclude='*-shm' \
            -cf - state ) | tar -C "$destination_root/$run" -xf -
    done
}

write_model_env() {
    local destination="$1"
    local key value
    : > "$destination"
    if [[ ! -f "$model_env_source" ]]; then
        log "WARNING: model env source not found: $model_env_source; deploy/model.env is empty"
    else
        for key in OPENAI_API_KEY OPENAI_BASE_URL LLM_API_KEY LLM_BASE_URL; do
            value="$(grep -E "^${key}=" "$model_env_source" | tail -n 1 | cut -d= -f2- || true)"
            if [[ -n "$value" ]]; then
                printf '%s=%s\n' "$key" "$value" >> "$destination"
            else
                log "WARNING: $key missing in $model_env_source"
            fi
        done
    fi
    chmod 600 "$destination" 2>/dev/null || true
}

copy_m2_config() {
    local destination_dir="$1"
    [[ -f "$m2_config" ]] || die "M2 config not found: $m2_config"
    [[ -f "$m2_key" ]] || die "M2 key file not found: $m2_key"
    mkdir -p "$destination_dir"
    cp "$m2_config" "$destination_dir/config.json"
    cp "$m2_key" "$destination_dir/api-key.txt"
    chmod 600 "$destination_dir/config.json" "$destination_dir/api-key.txt" 2>/dev/null || true
}

write_manifest() {
    local analysis_integrity="$1"
    local workflow_integrity="$2"
    local manifest="$stage_data/MANIFEST.json"
    "$python_cmd" - "$(host_path "$manifest")" "$version" "$created_at" \
        "$(host_path "$dump_path")" "$(host_path "$analysis_path")" \
        "$(host_path "$workflow_path")" "$(host_path "$rows_path")" \
        "$analysis_integrity" "$workflow_integrity" <<'PY'
import hashlib
import json
import os
import sys

(manifest_path, version, created_at, dump_path, analysis_path,
 workflow_path, rows_path, analysis_integrity, workflow_integrity) = sys.argv[1:10]

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

tables = {}
with open(rows_path, encoding="utf-8") as handle:
    for line in handle:
        if not line.strip():
            continue
        name, count = line.rstrip("\n").split("\t", 1)
        tables[name] = int(count)

manifest = {
    "format": 1,
    "version": version,
    "created_at": created_at,
    "mysql": {
        "database": "talentmind",
        "dump": {
            "path": "app/deploy/data/mysql/talentmind.sql.gz",
            "size": os.path.getsize(dump_path),
            "sha256": sha256(dump_path),
        },
        "tables": tables,
    },
    "sqlite": {
        "analysis.sqlite3": {
            "path": "app/deploy/seed/backend/m2-product/analysis.sqlite3",
            "size": os.path.getsize(analysis_path),
            "sha256": sha256(analysis_path),
            "integrity_check": analysis_integrity,
        },
        "workflow.sqlite3": {
            "path": "app/deploy/seed/backend/m2-product/workflow.sqlite3",
            "size": os.path.getsize(workflow_path),
            "sha256": sha256(workflow_path),
            "integrity_check": workflow_integrity,
        },
    },
}
with open(manifest_path, "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY
}

stage_data_tree() {
    local product_source="$repo_root/data/local/m2-product"
    local state_source="$repo_root/data/local/m2-p5-p6-20261107"
    local seed="$stage_data/app/deploy/seed/backend"
    mkdir -p "$stage_data/app/deploy/data/mysql" "$seed/m2-product" \
        "$seed/m2-p5-p6-20261107" "$seed/m2-delivery" "$stage_data/app/deploy/m2"
    [[ -d "$product_source" ]] || die "M2 product data not found: $product_source"
    [[ -d "$state_source" ]] || die "M2 historical state not found: $state_source"

    ensure_mysql_running
    dump_path="$stage_data/app/deploy/data/mysql/talentmind.sql.gz"
    dump_mysql "$dump_path"
    rows_path="$stage_root/mysql-rows.tsv"
    query_mysql_rows "$rows_path"

    analysis_path="$seed/m2-product/analysis.sqlite3"
    workflow_path="$seed/m2-product/workflow.sqlite3"
    analysis_integrity="$(backup_sqlite "$product_source/analysis.sqlite3" "$analysis_path")" \
        || die "analysis.sqlite3 backup or integrity check failed"
    workflow_integrity="$(backup_sqlite "$product_source/workflow.sqlite3" "$workflow_path")" \
        || die "workflow.sqlite3 backup or integrity check failed"
    copy_m2_product "$product_source" "$seed/m2-product"
    copy_state_dirs "$state_source" "$seed/m2-p5-p6-20261107"
    write_model_env "$stage_data/app/deploy/model.env"
    copy_m2_config "$stage_data/app/deploy/m2"
    write_manifest "$analysis_integrity" "$workflow_integrity"
}

create_archive() {
    local source_dir="$1"
    local destination="$2"
    local partial="$destination.partial"
    partials+=("$partial")
    log "creating $(basename "$destination")"
    tar -czf "$partial" -C "$source_dir" .
    mv "$partial" "$destination"
}

size_bytes() {
    wc -c < "$1" | tr -d '[:space:]'
}

sha256_file() {
    sha256sum "$1" | awk '{print $1}'
}

finalize_archives() {
    local code_partial="$code_tar.partial"
    local split="$split_images"
    local code_size
    partials+=("$code_partial")
    log "creating $(basename "$code_tar")"
    tar -czf "$code_partial" -C "$stage_code" .

    if [[ "$skip_images" -eq 0 ]]; then
        code_size="$(size_bytes "$code_partial")"
        if [[ "$split" -eq 0 ]] && (( code_size > 2147483648 )); then
            log "code archive is $code_size bytes (> 2 GiB); splitting image archives"
            split=1
        fi
        if [[ "$split" -eq 1 ]]; then
            mkdir -p "$stage_images/app/deploy"
            mv "$stage_code/app/deploy/images" "$stage_images/app/deploy/images"
            log "rebuilding code archive without images"
            rm -f "$code_partial"
            tar -czf "$code_partial" -C "$stage_code" .
        fi
    fi
    mv "$code_partial" "$code_tar"

    if [[ "$split" -eq 1 ]]; then
        create_archive "$stage_images" "$images_tar"
    fi
    if [[ "$skip_data" -eq 0 ]]; then
        create_archive "$stage_data" "$data_tar"
    fi
    write_checksums
}

write_checksums() {
    local sums="$output_dir/SHA256SUMS"
    local partial="$sums.partial"
    local archive
    local archives=("$code_tar")
    if [[ -f "$images_tar" ]]; then
        archives+=("$images_tar")
    fi
    if [[ -f "$data_tar" ]]; then
        archives+=("$data_tar")
    fi
    partials+=("$partial")
    : > "$partial"
    for archive in "${archives[@]}"; do
        printf '%s  %s\n' "$(sha256_file "$archive")" "$(basename "$archive")" >> "$partial"
    done
    mv "$partial" "$sums"
    for archive in "${archives[@]}"; do
        log "package: $archive"
        log "  size: $(size_bytes "$archive") bytes"
        log "  sha256: $(sha256_file "$archive")"
    done
    log "checksums: $sums"
}

main() {
    parse_args "$@"
    [[ "$version" =~ ^[A-Za-z0-9._-]+$ ]] \
        || die "invalid version '$version' (allowed: letters, digits, dot, underscore, dash)"
    check_prerequisites
    prepare_output

    created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    code_tar="$output_dir/talentmind-code-$version.tar.gz"
    images_tar="$output_dir/talentmind-images-$version.tar.gz"
    data_tar="$output_dir/talentmind-data-$version.tar.gz"

    stage_root="$(mktemp -d "$output_dir/.stage.XXXXXX")"
    stage_code="$stage_root/code"
    stage_data="$stage_root/data"
    stage_images="$stage_root/images"
    partials=()
    cleanup() {
        rm -rf "$stage_root"
        local partial
        for partial in "${partials[@]}"; do
            rm -f "$partial"
        done
    }
    trap cleanup EXIT

    stage_code_tree
    write_package_env
    if [[ "$skip_images" -eq 0 ]]; then
        stage_images
    fi
    if [[ "$skip_data" -eq 0 ]]; then
        log "staging private data"
        stage_data_tree
    fi
    finalize_archives
}

main "$@"
