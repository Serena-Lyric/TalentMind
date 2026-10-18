"""Run a Python command with synthetic service settings and inherited network denial.

Example from repo root:
  python docs/research/m3-p2-0/verify_offline.py -- -m pytest -m "not integration" -q
Use an interpreter containing the project and/or research requirements.
The child runs in backend/. Temporary guard/log/pytest files are removed on exit.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


GUARD = '''import os, socket, sys
from pathlib import Path
log = Path(os.environ["M3_OFFLINE_AUDIT"])
def record(event):
    with log.open("a", encoding="utf-8") as stream:
        stream.write(str(os.getpid()) + " " + event + "\\n")
record("loaded")
def audit(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.bind", "socket.sendto", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
        frame = sys._getframe()
        while frame:
            if frame.f_code is socket.socketpair.__code__:
                record("internal_socketpair")
                return
            frame = frame.f_back
        record("blocked:" + event)
        raise RuntimeError("offline guard denied " + event)
sys.addaudithook(audit)
'''


def main():
    args = sys.argv[1:]
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        raise SystemExit("Pass a Python command after -- (e.g. -m pytest -m 'not integration' -q)")
    root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory(prefix="talentmind-m3-check-") as temporary:
        area = Path(temporary)
        (area / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
        environment = dict(os.environ,
            PYTHONPATH=os.pathsep.join([str(area), str(root / "backend"), os.environ.get("PYTHONPATH", "")]),
            PYTHONIOENCODING="utf-8", PYTHONUTF8="1", M3_OFFLINE_AUDIT=str(area / "audit.log"),
            MYSQL_URL="mysql+pymysql://synthetic:synthetic@127.0.0.1:1/synthetic_test",
            NEO4J_URI="bolt://127.0.0.1:1", NEO4J_USER="synthetic", NEO4J_PASSWORD="synthetic",
            REDIS_URL="redis://127.0.0.1:1/15", OPENAI_API_KEY="synthetic-test-key",
            OPENAI_BASE_URL="http://127.0.0.1:1/v1", LLM_API_KEY="synthetic-test-key",
            LLM_BASE_URL="http://127.0.0.1:1/v1", DS_API_KEY="synthetic-test-key", DS_BASE_URL="http://127.0.0.1:1/v1")
        if args[:2] == ["-m", "pytest"]:
            args += ["--basetemp", str(area / "pytest")]
        result = subprocess.run([sys.executable, *args], cwd=root / "backend", env=environment)
        lines = (area / "audit.log").read_text(encoding="utf-8").splitlines() if (area / "audit.log").exists() else []
        blocked = [line for line in lines if "blocked:" in line]
        summary = dict(child_exit=result.returncode, python_processes=sum(line.endswith(" loaded") for line in lines),
                       blocked_network_attempts=len(blocked), internal_socketpair_events=sum("internal_socketpair" in line for line in lines))
    summary["temporary_directory_removed"] = not area.exists()
    print(json.dumps(summary))
    raise SystemExit(result.returncode or int(bool(blocked)) or int(not summary["python_processes"]))


if __name__ == "__main__":
    main()
