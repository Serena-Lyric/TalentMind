#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/common.sh
source "$script_dir/common.sh"
tm_source_env

follow=1
if [[ "${1:-}" == "--no-follow" ]]; then
    follow=0
    shift
fi
args=(logs --tail=200)
if [[ "$follow" -eq 1 ]]; then
    args+=(-f)
fi
tm_compose "${args[@]}" "$@"
