#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/common.sh
source "$script_dir/common.sh"
tm_source_env

ok=1
for service in mysql backend web; do
    cid="$(tm_compose ps -q "$service" 2>/dev/null || true)"
    if [[ -z "$cid" ]]; then
        printf '%s: not running\n' "$service"
        ok=0
        continue
    fi
    state="$(docker inspect --format '{{.State.Status}}' "$cid" 2>/dev/null || printf 'unknown')"
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || printf 'unknown')"
    printf '%s: %s %s\n' "$service" "$state" "$health"
    [[ "$state" == "running" ]] || ok=0
    [[ "$health" == "healthy" || "$health" == "none" ]] || ok=0
done

printf 'data: %s\n' "$(tm_data_dir)"
df -h "$(tm_data_dir)" 2>/dev/null | tail -n 1 || true
printf 'ports:\n'
tm_compose ps --format '{{.Name}} {{.Ports}}' 2>/dev/null || true

if [[ "$ok" -eq 1 ]]; then
    exit 0
fi
exit 1
