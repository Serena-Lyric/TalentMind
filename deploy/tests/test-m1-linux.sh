#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
image="talentmind-backend:test"
container="talentmind-m1-linux-$$"
log_dir="$(mktemp -d)"

cleanup() {
    docker rm -f "$container" >/dev/null 2>&1 || true
    rm -rf "$log_dir"
}
trap cleanup EXIT

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

printf '== build backend image ==\n'
if ! docker build --platform linux/amd64 -f deploy/backend/Dockerfile -t "$image" . \
    >"$log_dir/build.log" 2>&1; then
    tail -60 "$log_dir/build.log" >&2 || true
    fail 'backend image build failed'
fi

printf '== static browser/noVNC checks ==\n'
docker run --rm "$image" microsoft-edge-stable --version
docker run --rm "$image" sh -c 'command -v Xvfb && command -v x11vnc && command -v websockify'
docker run --rm "$image" sh -c 'test -f /usr/share/novnc/vnc.html'
docker run --rm "$image" sh -c 'find /usr/share/fonts -iname "*CJK*" -print -quit | grep -q .'

printf '== start container ==\n'
docker run -d --name "$container" --platform linux/amd64 \
    -p 127.0.0.1::6080 \
    -e MYSQL_URL="mysql+pymysql://user:pass@127.0.0.1:3306/talentmind" \
    -e NEO4J_URI="bolt://127.0.0.1:7687" \
    -e NEO4J_USER="neo4j" \
    -e NEO4J_PASSWORD="pass" \
    -e REDIS_URL="redis://127.0.0.1:6379/0" \
    -e OPENAI_API_KEY="x" \
    -e OPENAI_BASE_URL="https://example.com/v1" \
    "$image" >/dev/null

ready=0
for _ in $(seq 1 60); do
    if docker exec "$container" python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18000/health')" \
        >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 2
done
if [[ "$ready" -ne 1 ]]; then
    docker logs --tail=80 "$container" >&2 || true
    fail 'backend container did not become healthy'
fi
printf 'health ok\n'

# Git Bash rewrites bare /tmp/... arguments for native executables; keep the
# container path inside sh -c so it is never path-converted on Windows.
docker exec "$container" sh -c 'test -S /tmp/.X11-unix/X99'
printf 'Xvfb display socket ok\n'

published_novnc="$(docker port "$container" 6080/tcp | head -n 1)"
case "$published_novnc" in
    127.0.0.1:*) host_port="${published_novnc##*:}" ;;
    *) fail "unexpected noVNC mapping: ${published_novnc}" ;;
esac
if ! curl -fsS --noproxy '*' --max-time 10 \
    "http://127.0.0.1:${host_port}/vnc.html" >"$log_dir/vnc.html"; then
    fail 'noVNC page is not reachable on the mapped loopback port'
fi
if ! grep -qi 'novnc' "$log_dir/vnc.html"; then
    fail 'noVNC page content missing'
fi
printf 'noVNC page ok (host 127.0.0.1:%s)\n' "$host_port"

printf '== Edge CDP smoke (about:blank only) ==\n'
docker exec -i "$container" python - <<'PY'
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from app.collect import browser

root = Path(tempfile.mkdtemp(prefix='m1-edge-', dir='/tmp'))
profile = (root / 'profile').resolve()
pid = browser._launch_edge(profile, 'about:blank')
try:
    endpoint = None
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        endpoint = browser._owned_endpoint(profile, browser._edge_sessions())
        if endpoint:
            break
        time.sleep(0.5)
    if not endpoint:
        raise SystemExit('no owned Edge endpoint found for launched profile')

    with urllib.request.urlopen(endpoint + '/json/version', timeout=5) as response:
        version = json.loads(response.read())
    if not isinstance(version, dict) or not version.get('Browser'):
        raise SystemExit(f'unexpected /json/version payload: {version!r}')

    with urllib.request.urlopen(endpoint + '/json/list', timeout=5) as response:
        pages = json.loads(response.read())
    if not any(page.get('type') == 'page' for page in pages if isinstance(page, dict)):
        raise SystemExit(f'no page target in /json/list: {pages!r}')
    print('edge cdp ok:', version['Browser'], 'pid', pid)
finally:
    subprocess.run(['pkill', '-TERM', '-f', str(profile)], check=False)
    time.sleep(2)
    subprocess.run(['pkill', '-KILL', '-f', str(profile)], check=False)
PY

printf '== worker process group smoke ==\n'
docker exec -i "$container" python - <<'PY'
import os
import subprocess
import sys
import time

from app.collect import worker_process

leader_code = r'''
import signal
import subprocess
import sys
import time

child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])


def _stop(signum, frame):
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
    raise SystemExit(0)


signal.signal(signal.SIGTERM, _stop)
print(child.pid, flush=True)
time.sleep(300)
'''

process = worker_process.spawn(
    [sys.executable, '-c', leader_code],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
)
line = process.stdout.readline()
if not line:
    raise SystemExit('worker did not report its child pid')
child_pid = int(line.strip())
leader_pid = process.pid
worker_process.stop(process, timeout=10)


def gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


deadline = time.monotonic() + 5
while time.monotonic() < deadline and not (gone(leader_pid) and gone(child_pid)):
    time.sleep(0.1)
if not gone(leader_pid):
    raise SystemExit(f'worker leader {leader_pid} still exists')
if not gone(child_pid):
    raise SystemExit(f'worker child {child_pid} still exists')
print('worker group ok:', leader_pid, child_pid)
PY

printf 'M1 Linux container smoke checks passed\n'
