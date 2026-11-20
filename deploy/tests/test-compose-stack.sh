#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
tmp="$(mktemp -d)"
project="talentmind-test-$$"
envfile_posix="$tmp/test.env"
envfile="$(cygpath -m "$envfile_posix" 2>/dev/null || printf '%s' "$envfile_posix")"
compose=(docker compose -p "$project" -f deploy/compose.yml)

cleanup() {
    "${compose[@]}" --env-file "$envfile" down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$tmp"
}
trap cleanup EXIT

data_dir="$(cygpath -m "$tmp/data" 2>/dev/null || printf '%s' "$tmp/data")"
mkdir -p "$tmp/data/mysql" "$tmp/data/backend" "$repo_root/deploy/m2"
cat > "$envfile_posix" <<EOF
TALENTMIND_VERSION=test
TALENTMIND_DATA_DIR=$data_dir
TALENTMIND_ENV_FILE=$envfile
TALENTMIND_HTTP_PORT=18080
TALENTMIND_HTTPS_PORT=18443
MYSQL_ROOT_PASSWORD=rootpass
MYSQL_PASSWORD=apppass
TALENTMIND_TRUSTED_PROXY_SECRET=secret
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4jpass
TALENTMIND_M2_CONFIG=/app/deploy/m2/config.json
TALENTMIND_M2_KEY_FILE=/app/deploy/m2/api-key.txt
TALENTMIND_TLS_MODE=selfsigned
TALENTMIND_SERVER_NAME=_
EOF

compose=(docker compose -p "$project" --env-file "$envfile" --profile graph-db --profile cache -f deploy/compose.yml)
"${compose[@]}" config > "$tmp/config.yml"
"${compose[@]}" config --format json > "$tmp/config.json"

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -c 'import json' >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done
"$PYTHON_BIN" - "$tmp/config.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
services = data["services"]
assert "ports" not in services["mysql"], "mysql must not publish ports"
backend_ports = services["backend"].get("ports") or []
assert len(backend_ports) == 1, "backend must publish only noVNC"
novnc = backend_ports[0]
assert novnc.get("host_ip") == "127.0.0.1", "noVNC must bind host loopback only"
assert int(novnc.get("target")) == 6080, "noVNC target must be 6080"
assert str(novnc.get("published")) == "6080", "noVNC published port must be 6080"
assert novnc.get("protocol", "tcp") == "tcp"
assert services["web"]["ports"], "web must publish 80/443"
assert services["mysql"]["mem_limit"], "mysql mem_limit missing"
assert services["backend"]["mem_limit"], "backend mem_limit missing"
assert services["web"]["mem_limit"], "web mem_limit missing"
assert services["neo4j"]["profiles"] == ["graph-db"]
assert services["redis"]["profiles"] == ["cache"]
PY

grep -Fq 'innodb_buffer_pool_size=512M' deploy/mysql/my.cnf
grep -Fq 'performance_schema=OFF' deploy/mysql/my.cnf
grep -Fq -- '--workers", "1' deploy/backend/Dockerfile
grep -Fq 'mem_limit: 1g' deploy/compose.yml
grep -Fq 'mem_limit: 1500m' deploy/compose.yml
grep -Fq 'mem_limit: 128m' deploy/compose.yml

"${compose[@]}" up -d mysql backend
ready=0
for _ in $(seq 1 60); do
    if "${compose[@]}" exec -T backend python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18000/health')" >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 2
done
if [[ "$ready" -ne 1 ]]; then
    "${compose[@]}" logs --tail=50 mysql backend
    printf 'backend did not become healthy\n' >&2
    exit 1
fi

published_mysql="$("${compose[@]}" port mysql 3306 2>/dev/null || true)"
published_backend="$("${compose[@]}" port backend 18000 2>/dev/null || true)"
published_novnc="$("${compose[@]}" port backend 6080 2>/dev/null || true)"
if [[ -n "$published_mysql" && "$published_mysql" != ":0" ]]; then
    printf 'mysql publishes a host port: %s\n' "$published_mysql" >&2
    exit 1
fi
if [[ -n "$published_backend" && "$published_backend" != ":0" ]]; then
    printf 'backend publishes port 18000: %s\n' "$published_backend" >&2
    exit 1
fi
if [[ "$published_novnc" != "127.0.0.1:6080" ]]; then
    printf 'backend noVNC mapping is not loopback 6080: %s\n' "$published_novnc" >&2
    exit 1
fi
printf 'compose stack checks passed\n'
