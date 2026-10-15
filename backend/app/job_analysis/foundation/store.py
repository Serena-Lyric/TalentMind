"""Append-only snapshots and attempts in a dedicated, exclusively owned SQLite file."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

APP_ID = 0x4D324641


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_destination(path: Path | str) -> Path:
    path = Path(path).resolve()
    root = Path(__file__).resolve().parents[4]
    if path.is_relative_to(root) and not path.is_relative_to(root / "data" / "local"):
        raise ValueError("repository outputs must be under data/local")
    return path


class AnalysisStore:
    def __init__(self, path: Path | str):
        self.path = safe_destination(path)
        if self.path.suffix not in (".db", ".sqlite", ".sqlite3"):
            raise ValueError("explicit SQLite filename required")
        if self.path.exists() and self.path.stat().st_nlink > 1:
            raise ValueError("hardlinked state files are not supported")
        existed = self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = self.path.with_suffix(self.path.suffix + ".lock").open("a+b")
        try:
            self._lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock.close()
            raise ValueError("analysis store already owned by another process") from None
        try:
            self.conn = sqlite3.connect(self.path)
            self.conn.row_factory = sqlite3.Row
            if self.path.stat().st_nlink > 1:
                raise ValueError("hardlinked state files are not supported")
            app = self.conn.execute("PRAGMA application_id").fetchone()[0]
            version = self.conn.execute("PRAGMA user_version").fetchone()[0]
            if existed and (app != APP_ID or version != 1):
                raise ValueError("not a stage A analysis store; no automatic migration")
            self.conn.execute("PRAGMA foreign_keys=ON")
            # REPLACE's implicit DELETE must also invoke immutable-history guards.
            self.conn.execute("PRAGMA recursive_triggers=ON")
            self.conn.executescript(f"""
                PRAGMA application_id={APP_ID};
                PRAGMA user_version=1;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, namespace TEXT NOT NULL, input_path TEXT NOT NULL,
                    input_sha256 TEXT NOT NULL, input_bytes BLOB NOT NULL, status TEXT NOT NULL,
                    started_at TEXT NOT NULL, finished_at TEXT, error TEXT,
                    version_id TEXT REFERENCES versions(id), force INTEGER NOT NULL DEFAULT 0,
                    aggregate_id TEXT, aggregate_revision TEXT NOT NULL DEFAULT 'v1');
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY, namespace TEXT NOT NULL, jd_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(namespace,jd_id,fingerprint));
                CREATE TABLE IF NOT EXISTS heads (
                    namespace TEXT NOT NULL, jd_id TEXT NOT NULL,
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    PRIMARY KEY(namespace,jd_id));
                CREATE TABLE IF NOT EXISTS observations (
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    crawled_at TEXT, PRIMARY KEY(run_id,snapshot_id));
                CREATE TABLE IF NOT EXISTS versions (id TEXT PRIMARY KEY, manifest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    version_id TEXT NOT NULL REFERENCES versions(id), status TEXT NOT NULL,
                    started_at TEXT NOT NULL, finished_at TEXT, error TEXT, coverage TEXT);
                CREATE INDEX IF NOT EXISTS attempt_lookup ON attempts(snapshot_id,version_id,id);
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY, attempt_id INTEGER NOT NULL REFERENCES attempts(id),
                    ordinal INTEGER NOT NULL, body TEXT NOT NULL, UNIQUE(attempt_id,ordinal));
                CREATE TABLE IF NOT EXISTS tasks (
                    run_id TEXT NOT NULL REFERENCES runs(id), snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    attempt_id INTEGER REFERENCES attempts(id), reused INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(run_id,snapshot_id));
                CREATE TABLE IF NOT EXISTS aggregates (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
                    manifest TEXT NOT NULL, business TEXT NOT NULL, business_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS attempts_terminal BEFORE UPDATE ON attempts
                    WHEN OLD.status != 'running' BEGIN SELECT RAISE(ABORT,'immutable terminal attempt'); END;
                CREATE TRIGGER IF NOT EXISTS attempts_identity BEFORE UPDATE OF run_id,snapshot_id,version_id ON attempts
                    BEGIN SELECT RAISE(ABORT,'immutable attempt identity'); END;
                CREATE TRIGGER IF NOT EXISTS attempts_delete BEFORE DELETE ON attempts
                    BEGIN SELECT RAISE(ABORT,'immutable attempt'); END;
                CREATE TRIGGER IF NOT EXISTS facts_insert BEFORE INSERT ON facts
                    WHEN (SELECT status FROM attempts WHERE id=NEW.attempt_id) IS NOT 'running'
                    BEGIN SELECT RAISE(ABORT,'cannot append facts to terminal attempt'); END;
            """)
            for table in ("snapshots", "versions", "facts", "aggregates"):
                for operation in ("UPDATE", "DELETE"):
                    self.conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} BEFORE {operation} ON {table} "
                                      "BEGIN SELECT RAISE(ABORT,'immutable analysis history'); END")
            # The OS lock proves the previous owner has exited; committed terminal facts stay intact.
            self.conn.execute("UPDATE attempts SET status='retryable',error='process_interrupted',finished_at=? WHERE status='running'", (now(),))
            self.conn.execute("UPDATE runs SET status='interrupted',error='process_interrupted' WHERE status='running'")
            self.conn.commit()
        except BaseException:
            if hasattr(self, "conn"):
                self.conn.close()
            self._lock.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.conn.close()
        self._lock.close()

    def ingest(self, batch, version=None, force=False, aggregate_revision="v1") -> str:
        run_id = uuid4().hex
        with self.conn:
            self.conn.execute("INSERT INTO runs(id,namespace,input_path,input_sha256,input_bytes,status,started_at) VALUES (?,?,?,?,?,'pending',?)",
                (run_id, batch.namespace, str(batch.path), batch.digest, batch.raw_bytes, now()))
            for record in batch.records:
                self.conn.execute("INSERT OR IGNORE INTO snapshots(namespace,jd_id,fingerprint,payload) VALUES (?,?,?,?)",
                    (record.namespace, record.jd_id, record.fingerprint, record.payload_json))
                snapshot = self.conn.execute("SELECT id FROM snapshots WHERE namespace=? AND jd_id=? AND fingerprint=?",
                    (record.namespace, record.jd_id, record.fingerprint)).fetchone()[0]
                self.conn.execute("INSERT INTO heads VALUES (?,?,?) ON CONFLICT(namespace,jd_id) DO UPDATE SET snapshot_id=excluded.snapshot_id",
                    (record.namespace, record.jd_id, snapshot))
                self.conn.execute("INSERT INTO observations VALUES (?,?,?)", (run_id, snapshot, record.observation))
            if version:
                self.conn.execute("INSERT OR IGNORE INTO versions VALUES (?,?)", (version.key, version.manifest_json))
                self.conn.execute("UPDATE runs SET version_id=?,force=?,aggregate_revision=? WHERE id=?", (version.key, int(force), aggregate_revision, run_id))
                # Freeze the complete dataset scope, including identities absent from this incremental file.
                self.conn.execute("INSERT INTO tasks(run_id,snapshot_id) SELECT ?,snapshot_id FROM heads WHERE namespace=?", (run_id, batch.namespace))
        return run_id

    def heads(self, namespace):
        return [dict(row) | {"payload": json.loads(row["payload"])} for row in self.conn.execute(
            "SELECT s.* FROM heads h JOIN snapshots s ON s.id=h.snapshot_id WHERE h.namespace=? ORDER BY h.jd_id", (namespace,))]

    def observations(self, namespace, jd_id):
        return [dict(row) for row in self.conn.execute("""SELECT o.* FROM observations o
            JOIN snapshots s ON s.id=o.snapshot_id WHERE s.namespace=? AND s.jd_id=? ORDER BY o.rowid""", (namespace, jd_id))]

    def run(self, run_id):
        row = self.conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def attempt(self, attempt_id):
        row = self.conn.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
        if row is None:
            return None
        facts = [json.loads(f[0]) | {"fact_id": f[1]} for f in self.conn.execute(
            "SELECT body,id FROM facts WHERE attempt_id=? ORDER BY ordinal", (attempt_id,))]
        return dict(row) | {"facts": facts}
