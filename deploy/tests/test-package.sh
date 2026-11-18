#!/usr/bin/env bash
# Verify the deployment archives and optionally run an isolated install smoke
# test with temporary project name, paths and ports.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
# shellcheck source=deploy/scripts/common.sh
source deploy/scripts/common.sh

package_dir="${TALENTMIND_PACKAGE_DIR:-$repo_root/data/local/deploy}"
install_smoke="${TALENTMIND_PACKAGE_INSTALL:-1}"
require_images="${TALENTMIND_PACKAGE_REQUIRE_IMAGES:-1}"
code_arg="${1:-}"
data_arg="${2:-}"
images_arg="${3:-${TALENTMIND_PACKAGE_IMAGES:-}}"
python_cmd=""

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

note() {
    printf '[package-test] %s\n' "$*"
}

usage() {
    cat <<'USAGE'
Usage: bash deploy/tests/test-package.sh [code.tar.gz [data.tar.gz [images.tar.gz]]]

Without arguments the newest talentmind-code-*.tar.gz in data/local/deploy is
used together with its matching data/images archives. Missing packages print
SKIP and exit 0. Set TALENTMIND_PACKAGE_INSTALL=0 for validation-only runs and
TALENTMIND_PACKAGE_REQUIRE_IMAGES=0 to allow code-only archives.
USAGE
}

path_win() {
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

resolve_archive() {
    local path="$1"
    [[ -f "$path" ]] || return 1
    printf '%s/%s' "$(cd "$(dirname "$path")" && pwd)" "$(basename "$path")"
}

find_latest_code() {
    ls -1t "$package_dir"/talentmind-code-*.tar.gz 2>/dev/null | head -n 1 || true
}

select_archives() {
    if [[ -z "$code_arg" ]]; then
        code_arg="$(find_latest_code)"
        if [[ -z "$code_arg" ]]; then
            printf 'SKIP: no deployment packages found in %s\n' "$package_dir"
            exit 0
        fi
    fi
    code_tar="$(resolve_archive "$code_arg")" || fail "code archive not found: $code_arg"
    archive_dir="$(dirname "$code_tar")"
    code_name="$(basename "$code_tar")"
    [[ "$code_name" =~ ^talentmind-code-(.+)\.tar\.gz$ ]] \
        || fail "unexpected code archive name: $code_name"
    version="${BASH_REMATCH[1]}"

    if [[ -z "$data_arg" ]]; then
        data_arg="$archive_dir/talentmind-data-$version.tar.gz"
    fi
    if [[ ! -f "$data_arg" ]]; then
        printf 'SKIP: matching data archive not found: %s\n' "$data_arg"
        exit 0
    fi
    data_tar="$(resolve_archive "$data_arg")" || fail "data archive not found: $data_arg"

    if [[ -z "$images_arg" ]]; then
        images_arg="$archive_dir/talentmind-images-$version.tar.gz"
    fi
    if [[ -f "$images_arg" ]]; then
        images_tar="$(resolve_archive "$images_arg")" || fail "images archive not found: $images_arg"
    else
        images_tar=""
    fi
    [[ "$install_smoke" == "0" || "$install_smoke" == "1" ]] \
        || fail "TALENTMIND_PACKAGE_INSTALL must be 0 or 1"
    [[ "$require_images" == "0" || "$require_images" == "1" ]] \
        || fail "TALENTMIND_PACKAGE_REQUIRE_IMAGES must be 0 or 1"
}

list_archive() {
    tar -tzf "$1" > "$2"
}

has_path() {
    local list="$1"
    local path="$2"
    path="${path#./}"
    path="${path%/}"
    grep -Eq "(^|/)${path//./\\.}(/|$)" "$list"
}

check_checksums() {
    local log="$tmp_dir/sha256.log"
    if ! ( cd "$archive_dir" && sha256sum -c SHA256SUMS ) > "$log" 2>&1; then
        tail -20 "$log" >&2 || true
        fail "SHA256SUMS verification failed"
    fi
    note "SHA256SUMS verified"
}

check_code_archive() {
    code_list="$tmp_dir/code.list"
    list_archive "$code_tar" "$code_list"
    local required=(
        app/deploy/scripts/install.sh
        app/deploy/compose.yml
        app/deploy/package.env
        app/backend/app/contracts/ddl.sql
        app/backend/app/main.py
    )
    local path
    for path in "${required[@]}"; do
        has_path "$code_list" "$path" || fail "code archive missing $path"
    done
    local forbidden='^(\./)?(data/|app/backend/\.env(/|$)|app/deploy/\.env(/|$)|app/deploy/model\.env(/|$)|app/deploy/(m2|auth|tls|data|seed|backups)/)'
    if grep -Eq "$forbidden" "$code_list"; then
        fail "code archive contains forbidden path: $(grep -E "$forbidden" "$code_list" | head -n 1)"
    fi
    # The repository tracks only data/local/README.md under app/data.
    if grep -E '^(\./)?app/data/' "$code_list" \
        | grep -vE '^(\./)?app/data/(local/)?$|^(\./)?app/data/local/README\.md$' | grep -q .; then
        fail "code archive contains private data under app/data/: $(grep -E '^(\./)?app/data/' "$code_list" | grep -vE '^(\./)?app/data/(local/)?$|^(\./)?app/data/local/README\.md$' | head -n 1)"
    fi
    if grep -Eiq '(^|/)(browser_profiles|Cookies)(/|$)' "$code_list"; then
        fail "code archive contains browser profile or cookie data"
    fi
    code_has_images=0
    if grep -Eq '(^|/)app/deploy/images/.+\.tar$' "$code_list"; then
        code_has_images=1
    fi
    note "code archive content checks passed"
}

check_images_archive() {
    if [[ -n "$images_tar" ]]; then
        images_list="$tmp_dir/images.list"
        list_archive "$images_tar" "$images_list"
        if ! grep -Eq '(^|/)app/deploy/images/.+\.tar$' "$images_list"; then
            fail "images archive has no app/deploy/images/*.tar entries"
        fi
        if grep -Ev '^(\./)?$|^(\./)?app/?$|^(\./)?app/deploy/?$|^(\./)?app/deploy/images/' \
            "$images_list" | grep -q .; then
            fail "images archive contains entries outside app/deploy/images"
        fi
        note "images archive content checks passed"
    elif [[ "$require_images" -eq 1 && "$code_has_images" -eq 0 ]]; then
        fail "no image archives found; pass TALENTMIND_PACKAGE_IMAGES or set TALENTMIND_PACKAGE_REQUIRE_IMAGES=0"
    fi
}

check_data_archive() {
    data_list="$tmp_dir/data.list"
    list_archive "$data_tar" "$data_list"
    local required=(
        app/deploy/data/mysql/talentmind.sql.gz
        app/deploy/seed/backend/m2-product/analysis.sqlite3
        app/deploy/seed/backend/m2-product/workflow.sqlite3
        app/deploy/seed/backend/m2-product/runs
        app/deploy/seed/backend/m2-product/graphs
        app/deploy/seed/backend/m2-product/native-reports
        app/deploy/seed/backend/m2-p5-p6-20261107/sequence-head-final/state
        app/deploy/seed/backend/m2-p5-p6-20261107/dev-head-final/state
        app/deploy/seed/backend/m2-delivery
        app/deploy/model.env
        app/deploy/m2/config.json
        app/deploy/m2/api-key.txt
    )
    local path
    for path in "${required[@]}"; do
        has_path "$data_list" "$path" || fail "data archive missing $path"
    done
    if grep -Eq '(^|/)[^/]*\.lock$|(^|/)[^/]*-wal$|(^|/)[^/]*-shm$' "$data_list"; then
        fail "data archive contains lock/WAL/SHM files"
    fi
    if grep -Eiq '(^|/)(browser_profiles|Cookies)(/|$)|(^|/)frequency\.sqlite3$' "$data_list"; then
        fail "data archive contains browser profiles, cookies or a collection frequency ledger"
    fi
    if grep -Eq '^(\./)?data/' "$data_list"; then
        fail "data archive must use the app/deploy/seed layout, not a top-level data/ directory"
    fi
    if grep -Eq '(^|/)\.env$' "$data_list"; then
        fail "data archive must not contain deploy/.env"
    fi
    note "data archive content checks passed"
}

extract_packages() {
    mkdir -p "$root"
    tar -xzf "$code_tar" -C "$root"
    if [[ -n "$images_tar" ]]; then
        tar -xzf "$images_tar" -C "$root"
    fi
    tar -xzf "$data_tar" -C "$root"
}

check_versions() {
    local package_version
    package_version="$(sed -n 's/^TALENTMIND_VERSION=//p' "$root/app/deploy/package.env" | tail -n 1)"
    [[ "$package_version" == "$version" ]] \
        || fail "package.env TALENTMIND_VERSION '$package_version' does not match '$version'"
    note "package.env version matches archive name"
}

check_extracted_images() {
    if [[ "$require_images" -eq 0 && -z "$images_tar" && "$code_has_images" -eq 0 ]]; then
        note "image archives not required for this run"
        return 0
    fi
    if [[ -z "$(find "$root/app/deploy/images" -maxdepth 1 -name '*.tar' -size +0c -print -quit 2>/dev/null)" ]]; then
        fail "extracted image archives are missing or empty in app/deploy/images"
    fi
    note "extracted image archives are present"
}

verify_manifest() {
    local analysis="$root/app/deploy/seed/backend/m2-product/analysis.sqlite3"
    local workflow="$root/app/deploy/seed/backend/m2-product/workflow.sqlite3"
    "$python_cmd" - "$(path_win "$root/MANIFEST.json")" \
        "$(path_win "$analysis")" "$(path_win "$workflow")" "$version" <<'PY'
import json
import sqlite3
import sys

manifest_path, analysis_path, workflow_path, version = sys.argv[1:5]
with open(manifest_path, encoding="utf-8") as handle:
    manifest = json.load(handle)
if manifest.get("version") != version:
    sys.exit(f"manifest version {manifest.get('version')!r} != {version!r}")
for name, path in (("analysis.sqlite3", analysis_path),
                   ("workflow.sqlite3", workflow_path)):
    connection = sqlite3.connect(path)
    try:
        rows = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
    finally:
        connection.close()
    if rows != ["ok"]:
        sys.exit(f"{name} integrity_check failed: {'; '.join(rows)}")
    entry = manifest.get("sqlite", {}).get(name, {})
    if entry.get("integrity_check") != "ok":
        sys.exit(f"{name} manifest integrity_check is not ok")
expected_tables = {
    "jd_pool", "job_definition", "job_change_log", "job_skill",
    "signal", "skill_dict", "resume", "talent_raw",
}
tables = manifest.get("mysql", {}).get("tables", {})
missing = expected_tables - set(tables)
if missing:
    sys.exit(f"manifest is missing table counts: {', '.join(sorted(missing))}")
for name, count in tables.items():
    if not isinstance(count, int) or count < 0:
        sys.exit(f"manifest has invalid row count for {name}")
print("manifest and SQLite checks passed")
PY
    note "manifest and SQLite checks passed"
}

manifest_table_lines() {
    "$python_cmd" - "$(path_win "$root/MANIFEST.json")" <<'PY'
import json
import sys

sys.stdout.reconfigure(newline="\n")
with open(sys.argv[1], encoding="utf-8") as handle:
    tables = json.load(handle).get("mysql", {}).get("tables", {})
for name in sorted(tables):
    print(f"{name}\t{tables[name]}")
PY
}

verify_installed_backend() {
    local backend="$root/data/backend"
    local name
    for name in analysis.sqlite3 workflow.sqlite3; do
        [[ -f "$backend/m2-product/$name" ]] \
            || fail "seeded backend data is missing m2-product/$name"
    done
    [[ -d "$backend/m2-delivery" ]] || fail "seeded backend data is missing m2-delivery"
    [[ -d "$backend/m2-p5-p6-20261107/sequence-head-final/state" ]] \
        || fail "seeded backend data is missing sequence-head-final/state"
    [[ -d "$backend/m2-p5-p6-20261107/dev-head-final/state" ]] \
        || fail "seeded backend data is missing dev-head-final/state"
    "$python_cmd" - "$(path_win "$backend/m2-product/analysis.sqlite3")" \
        "$(path_win "$backend/m2-product/workflow.sqlite3")" <<'PY'
import sqlite3
import sys

for path in sys.argv[1:]:
    connection = sqlite3.connect(path)
    try:
        rows = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
    finally:
        connection.close()
    if rows != ["ok"]:
        sys.exit(f"{path} integrity_check failed: {'; '.join(rows)}")
print("installed SQLite integrity checks passed")
PY
    note "seeded backend data and SQLite integrity checks passed"
}

verify_installed_mysql() {
    local table expected actual
    while IFS=$'\t' read -r table expected; do
        [[ "$table" =~ ^[A-Za-z0-9_]+$ ]] || fail "invalid table name in manifest: $table"
        actual="$(tm_compose exec -T -e MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql mysql \
            -uroot -N -B talentmind -e "SELECT COUNT(*) FROM \`$table\`")"
        actual="${actual//[[:space:]]/}"
        [[ "$actual" == "$expected" ]] \
            || fail "row count mismatch for $table: expected $expected, got $actual"
    done < <(manifest_table_lines)
    note "installed MySQL row counts match MANIFEST.json"
}

check_http() {
    local url="$1"
    local auth="$2"
    local status
    if [[ "$auth" -eq 1 ]]; then
        status="$(curl -s -o /dev/null -w '%{http_code}' \
            -u "$TALENTMIND_ADMIN_USER:$TALENTMIND_ADMIN_PASSWORD" "$url")"
    else
        status="$(curl -s -o /dev/null -w '%{http_code}' "$url")"
    fi
    [[ "$status" == "200" ]] || fail "GET $url returned $status (expected 200)"
}

run_install_smoke() {
    local base="http://127.0.0.1:18080"
    export TALENTMIND_ROOT="$root"
    export TALENTMIND_DEPLOY_DIR="$root/app/deploy"
    export TALENTMIND_DATA_DIR="$(path_win "$root/data")"
    export TALENTMIND_ENV_FILE="$(path_win "$tmp_dir/env")"
    export TALENTMIND_NGINX_DIR="$(path_win "$tmp_dir/nginx")"
    export TALENTMIND_AUTH_DIR="$(path_win "$tmp_dir/auth")"
    export TALENTMIND_TLS_DIR="$(path_win "$tmp_dir/tls")"
    export TALENTMIND_PROJECT="$project"
    export TALENTMIND_HTTP_PORT=18080
    export TALENTMIND_HTTPS_PORT=18443
    export TALENTMIND_SERVER_NAME=127.0.0.1
    export TALENTMIND_TLS_MODE=off
    export TALENTMIND_SKIP_ROOT_CHECK=1
    export TALENTMIND_SKIP_DOCKER_INSTALL=1
    export TALENTMIND_ADMIN_USER=testuser
    export TALENTMIND_ADMIN_PASSWORD=testpass
    export TALENTMIND_TRUSTED_PROXY_SECRET=proxys3cret
    export MYSQL_ROOT_PASSWORD=rootpass
    export MYSQL_PASSWORD=apppass
    export NEO4J_PASSWORD=neo4jpass
    unset TALENTMIND_MYSQL_DUMP TALENTMIND_MODEL_ENV TALENTMIND_VERSION

    mkdir -p "$tmp_dir/nginx" "$tmp_dir/auth" "$tmp_dir/tls"
    # POSIX ownership is meaningless for Docker Desktop bind mounts, and MSYS
    # chown -R over the 1.4GB seed tree takes hours. The real Ubuntu install
    # still performs the chown.
    case "$(uname -s)" in
        MINGW*|MSYS*)
            mkdir -p "$tmp_dir/bin"
            printf '#!/bin/sh\nexit 0\n' > "$tmp_dir/bin/chown"
            chmod +x "$tmp_dir/bin/chown"
            export PATH="$tmp_dir/bin:$PATH"
            ;;
    esac
    note "running isolated install smoke test (project $project, ports 18080/18443)"
    if ! bash "$root/app/deploy/scripts/install.sh" > "$tmp_dir/install.log" 2>&1; then
        tail -80 "$tmp_dir/install.log" >&2 || true
        fail "install.sh failed"
    fi
    verify_installed_mysql
    verify_installed_backend
    check_http "$base/healthz" 0
    check_http "$base/" 1
    check_http "$base/api/collection/platforms" 1
    check_http "$base/api/jobs?page=1&page_size=1" 1
    check_http "$base/api/m2/delivery/inputs?limit=1&offset=0" 1
    tm_compose down -v --remove-orphans > "$tmp_dir/down.log" 2>&1 || true
    note "install smoke test passed; containers and volumes removed"
}

main() {
    if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
        usage
        exit 0
    fi
    select_archives
    python_cmd="$(find_python)" || fail "python3/python with sqlite3 is required"
    tmp_dir="$(mktemp -d)"
    root="$tmp_dir/root"
    project="pkg-test-$$"
    cleanup() {
        if [[ -n "${TALENTMIND_ENV_FILE:-}" && -f "${TALENTMIND_ENV_FILE:-}" ]]; then
            TALENTMIND_PROJECT="${TALENTMIND_PROJECT:-$project}" \
                tm_compose down -v --remove-orphans >/dev/null 2>&1 || true
        fi
        rm -rf "$tmp_dir"
    }
    trap cleanup EXIT

    note "code: $code_tar"
    note "data: $data_tar"
    if [[ -n "$images_tar" ]]; then
        note "images: $images_tar"
    fi
    check_checksums
    check_code_archive
    check_images_archive
    check_data_archive
    extract_packages
    check_versions
    check_extracted_images
    verify_manifest

    if [[ "$install_smoke" -eq 1 ]]; then
        run_install_smoke
    else
        note "install smoke test skipped (TALENTMIND_PACKAGE_INSTALL=0)"
    fi
    printf 'package checks passed (host Docker smoke test; not a fresh cloud host)\n'
}

main "$@"
