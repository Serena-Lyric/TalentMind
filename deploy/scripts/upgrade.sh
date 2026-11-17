#!/usr/bin/env bash
# Back up, load any bundled images, and restart the stack.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/common.sh
source "$script_dir/common.sh"
tm_source_env

bash "$script_dir/backup.sh"
deploy_dir="$(tm_deploy_dir)"
shopt -s nullglob
for archive in "$deploy_dir"/images/*.tar; do
    tm_log "loading image archive: $archive"
    docker load -i "$archive"
done
shopt -u nullglob
tm_compose up -d
tm_wait_healthy 120
tm_log "upgrade/restart complete"
