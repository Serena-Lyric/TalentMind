#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
docker build --platform linux/amd64 --target test -f deploy/web/Dockerfile -t talentmind-web-test:test .
printf 'frontend container tests passed\n'
