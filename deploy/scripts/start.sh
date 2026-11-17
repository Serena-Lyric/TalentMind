#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/common.sh
source "$script_dir/common.sh"

tm_compose up -d
tm_wait_healthy
tm_log "TalentMind is running; use status.sh for details"
