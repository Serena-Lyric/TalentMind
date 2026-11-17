#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
image="talentmind-web:test"

docker build --platform linux/amd64 -f deploy/web/Dockerfile -t "$image" .
docker run --rm "$image" nginx -t
docker run --rm "$image" sh -c 'test -f /usr/share/nginx/html/index.html'
docker run --rm "$image" sh -c 'test -f /usr/share/nginx/html/graph-artifacts/historical.json'
printf 'web image checks passed\n'
