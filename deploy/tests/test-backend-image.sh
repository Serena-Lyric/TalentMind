#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
image="talentmind-backend:test"

docker build --platform linux/amd64 -f deploy/backend/Dockerfile -t "$image" .

run() {
    docker run --rm "$@"
}

run \
    -e MYSQL_URL="mysql+pymysql://user:pass@127.0.0.1:3306/talentmind" \
    -e NEO4J_URI="bolt://127.0.0.1:7687" \
    -e NEO4J_USER="neo4j" \
    -e NEO4J_PASSWORD="pass" \
    -e REDIS_URL="redis://127.0.0.1:6379/0" \
    -e OPENAI_API_KEY="x" \
    -e OPENAI_BASE_URL="https://example.com/v1" \
    "$image" python -c "import app.main"

test "$(run "$image" id -u)" = "1000"
run "$image" sh -c 'test -d /app/backend/app'
run "$image" sh -c 'test -d /app/data/local'
run "$image" sh -c 'test ! -e /app/backend/.env'
run "$image" sh -c 'test ! -e /app/data/local/m2-product'
printf 'backend image checks passed\n'
