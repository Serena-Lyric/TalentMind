#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
script="$repo_root/deploy/scripts/install-docker.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

failures=0
check() {
    local label="$1"
    shift
    if "$@"; then
        printf 'PASS %s\n' "$label"
    else
        printf 'FAIL %s\n' "$label"
        failures=$((failures + 1))
    fi
}

json_assert() {
    "$PYTHON_BIN" - "$1" "$2" <<'PY'
import json
import sys

path, code = sys.argv[1], sys.argv[2]
data = json.load(open(path, encoding="utf-8"))
assert eval(code, {"data": data, "json": json})
PY
}

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -c 'import json' >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done
if [[ -z "$PYTHON_BIN" ]]; then
    printf 'FAIL no working Python interpreter\n'
    exit 1
fi

if [[ ! -f "$script" ]]; then
    printf 'FAIL install-docker.sh missing\n'
    exit 1
fi
# shellcheck disable=SC1090
source "$script"

TALENTMIND_DOCKER_CONFIG_DIR="$tmp/docker-empty"
write_daemon_config
check "default mirror" json_assert "$TALENTMIND_DOCKER_CONFIG_DIR/daemon.json" \
    'data["registry-mirrors"] == ["https://mirror.ccs.tencentyun.com"]'
check "log rotation" json_assert "$TALENTMIND_DOCKER_CONFIG_DIR/daemon.json" \
    'data["log-opts"] == {"max-size": "20m", "max-file": "3"}'

mkdir -p "$tmp/docker-existing"
printf '%s\n' '{"log-driver":"json-file","live-restore":true}' > "$tmp/docker-existing/daemon.json"
TALENTMIND_DOCKER_CONFIG_DIR="$tmp/docker-existing" write_daemon_config
check "merge keeps existing keys" json_assert "$tmp/docker-existing/daemon.json" \
    'data["live-restore"] is True'
check "merge adds mirror" json_assert "$tmp/docker-existing/daemon.json" \
    'data["registry-mirrors"] == ["https://mirror.ccs.tencentyun.com"]'

mkdir -p "$tmp/docker-override"
TALENTMIND_DOCKER_CONFIG_DIR="$tmp/docker-override" \
TALENTMIND_REGISTRY_MIRROR="https://registry.example.test" \
    write_daemon_config
check "mirror override" json_assert "$tmp/docker-override/daemon.json" \
    'data["registry-mirrors"] == ["https://registry.example.test"]'

TALENTMIND_SYSCTL_DIR="$tmp/sysctl" configure_swappiness
check "swappiness" grep -Fq 'vm.swappiness=10' "$tmp/sysctl/99-talentmind.conf"

mkdir -p "$tmp/bin"
printf '#!/bin/sh\nexit 0\n' > "$tmp/bin/docker"
chmod +x "$tmp/bin/docker"
check "docker_available" env PATH="$tmp/bin:$PATH" bash -c 'source "$1"; docker_available' _ "$script"

check "syntax" bash -n "$script"

if [[ "$failures" -ne 0 ]]; then
    printf '%s failure(s)\n' "$failures"
    exit 1
fi
printf 'all install-docker checks passed\n'
