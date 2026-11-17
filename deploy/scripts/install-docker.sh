#!/usr/bin/env bash
# Install Docker Engine and configure the Tencent Cloud registry mirror.
# Safe to source; the main routine only runs when executed directly.
set -euo pipefail

DEFAULT_REGISTRY_MIRROR="https://mirror.ccs.tencentyun.com"
DOCKER_CE_REPO="https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu"
DOCKER_CE_KEY="$DOCKER_CE_REPO/gpg"

tm_log() {
    printf '[talentmind] %s\n' "$*"
}

tm_die() {
    printf '[talentmind] ERROR: %s\n' "$*" >&2
    exit 1
}

docker_available() {
    command -v docker >/dev/null 2>&1 || return 1
    docker compose version >/dev/null 2>&1 || docker-compose version >/dev/null 2>&1
}

tm_python() {
    local candidate
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 \
            && "$candidate" -c 'import json' >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    printf 'python3'
}

write_daemon_config() {
    local dir="${TALENTMIND_DOCKER_CONFIG_DIR:-/etc/docker}"
    local mirror="${TALENTMIND_REGISTRY_MIRROR:-$DEFAULT_REGISTRY_MIRROR}"
    local python_bin
    python_bin="$(tm_python)"
    mkdir -p "$dir"
    "$python_bin" - "$dir/daemon.json" "$mirror" <<'PY'
import json
import sys

path, mirror = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
except FileNotFoundError:
    data = {}
except json.JSONDecodeError as exc:
    raise SystemExit(f"invalid daemon.json: {exc}")
if not isinstance(data, dict):
    raise SystemExit("daemon.json must contain an object")
data["registry-mirrors"] = [mirror]
data["log-driver"] = "json-file"
log_opts = data.get("log-opts")
if not isinstance(log_opts, dict):
    log_opts = {}
log_opts["max-size"] = "20m"
log_opts["max-file"] = "3"
data["log-opts"] = log_opts
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
PY
}

configure_swappiness() {
    local dir="${TALENTMIND_SYSCTL_DIR:-/etc/sysctl.d}"
    mkdir -p "$dir"
    printf 'vm.swappiness=10\n' > "$dir/99-talentmind.conf"
    if [[ "$dir" == /etc/sysctl.d && "$(id -u)" -eq 0 ]]; then
        sysctl --system >/dev/null 2>&1 || true
    fi
}

install_docker_packages() {
    local sudo_cmd=()
    if [[ "$(id -u)" -ne 0 ]]; then
        sudo_cmd=(sudo)
    fi
    if ! command -v apt-get >/dev/null 2>&1; then
        tm_die "apt-get is required on Ubuntu 24.04"
    fi
    "${sudo_cmd[@]}" apt-get update
    if install -d -m 0755 /etc/apt/keyrings 2>/dev/null \
        && curl -fsSL "$DOCKER_CE_KEY" -o /tmp/talentmind-docker.gpg 2>/dev/null; then
        "${sudo_cmd[@]}" install -m 0755 -d /etc/apt/keyrings
        "${sudo_cmd[@]}" gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg /tmp/talentmind-docker.gpg 2>/dev/null || true
        if [[ -s /etc/apt/keyrings/docker.gpg ]]; then
            . /etc/os-release
            printf 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] %s %s stable\n' \
                "$DOCKER_CE_REPO" "${VERSION_CODENAME:-noble}" \
                | "${sudo_cmd[@]}" tee /etc/apt/sources.list.d/docker.list >/dev/null
            if "${sudo_cmd[@]}" apt-get update \
                && "${sudo_cmd[@]}" apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin; then
                tm_log "installed Docker CE from Tencent mirror"
            else
                tm_log "Docker CE mirror install failed; falling back to Ubuntu packages"
                "${sudo_cmd[@]}" apt-get install -y docker.io docker-compose-v2
            fi
        fi
    fi
    if ! command -v docker >/dev/null 2>&1; then
        "${sudo_cmd[@]}" apt-get install -y docker.io docker-compose-v2
    fi
    "${sudo_cmd[@]}" systemctl enable --now docker
    rm -f /tmp/talentmind-docker.gpg
}

ensure_docker() {
    if docker_available; then
        return 0
    fi
    install_docker_packages
    docker_available || tm_die "Docker or Compose is still unavailable after install"
}

verify_docker_pull() {
    local image="${1:-mysql:8.0}"
    tm_log "verifying Docker Hub access with $image"
    docker pull "$image"
}

main() {
    if [[ "$(id -u)" -ne 0 ]]; then
        tm_die "run as root (or use sudo) to install/configure Docker"
    fi
    ensure_docker
    write_daemon_config
    configure_swappiness
    systemctl restart docker
    if ! verify_docker_pull "${1:-mysql:8.0}"; then
        tm_log "docker pull failed. Check DNS for registry-1.docker.io and the mirror setting:"
        tm_log "  ${TALENTMIND_REGISTRY_MIRROR:-$DEFAULT_REGISTRY_MIRROR}"
        tm_log "Bundled images can still be loaded with: docker load -i deploy/images/*.tar"
        exit 1
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
