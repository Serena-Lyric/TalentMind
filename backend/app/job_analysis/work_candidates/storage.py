"""Dedicated SQLite append-only snapshots; SQLite serializes competing writers."""
from copy import deepcopy
import sqlite3
from pathlib import Path
from uuid import uuid4

from ..foundation.inputs import canonical, digest, parse_json
from ..foundation.store import safe_destination

APP_ID = 0x4D325733


class CandidateStore:
    def __init__(self, path, *, create=False):
        self.path = safe_destination(path)
        if self.path.suffix not in {".db", ".sqlite", ".sqlite3"}:
            raise ValueError("explicit SQLite filename required")
        exists = self.path.exists()
        if not exists and not create:
            raise ValueError("registry does not exist; use init")
        if exists and self.path.stat().st_nlink > 1:
            raise ValueError("hardlinked registry prohibited")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        try:
            self.conn.execute("PRAGMA recursive_triggers=ON")
            self.conn.execute("PRAGMA synchronous=FULL")
            self.conn.execute("BEGIN IMMEDIATE")
            app = self.conn.execute("PRAGMA application_id").fetchone()[0]
            version = self.conn.execute("PRAGMA user_version").fetchone()[0]
            if app == APP_ID and version == 1:
                self.read()
            elif exists or not create or app or version:
                raise ValueError("not a P3 registry; no automatic migration")
            else:
                self.conn.execute(f"PRAGMA application_id={APP_ID}")
                self.conn.execute("PRAGMA user_version=1")
                self.conn.execute("CREATE TABLE sources(kind TEXT, sha256 TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,sha256))")
                self.conn.execute("CREATE TABLE batches(revision INTEGER PRIMARY KEY, batch_id TEXT UNIQUE NOT NULL, request_sha256 TEXT NOT NULL, body TEXT NOT NULL, sha256 TEXT NOT NULL)")
                for table in ("sources", "batches"):
                    for operation in ("UPDATE", "DELETE"):
                        self.conn.execute(f"CREATE TRIGGER {table}_{operation} BEFORE {operation} ON {table} "
                                          "BEGIN SELECT RAISE(ABORT,'immutable P3 history'); END")
                initial = dict(schema_version="m2-work-state-1", registry_id=uuid4().hex, revision=0,
                               candidates={}, relations={}, analysis_sha256s=[], report={}, formal_roles=[], content_groups=[],
                               counts=dict(linked_jd_identities=0, unique_content_groups=0,
                                           independent_evidence=None, vacancies=None))
                self.append("registry-init", digest({}), initial)
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            self.conn.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.conn.close()

    def read(self, revision=None):
        row = (self.conn.execute("SELECT body,sha256 FROM batches ORDER BY revision DESC LIMIT 1").fetchone()
               if revision is None else self.conn.execute("SELECT body,sha256 FROM batches WHERE revision=?", (revision,)).fetchone())
        if row is None:
            raise ValueError("unknown registry revision")
        value = parse_json(row[0])
        if digest(value) != row[1]:
            raise ValueError("registry digest mismatch")
        value["binding"] = dict(registry_id=value["registry_id"], revision=value["revision"], sha256=row[1])
        return value

    def source(self, kind, sha256):
        row = self.conn.execute("SELECT body FROM sources WHERE kind=? AND sha256=?", (kind, sha256)).fetchone()
        if row is None:
            raise ValueError("unknown source reference")
        value = parse_json(row[0])
        if digest(value) != sha256:
            raise ValueError("source digest mismatch")
        return value

    def put_source(self, kind, value):
        sha = digest(value)
        self.conn.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?)", (kind, sha, canonical(value)))
        if self.source(kind, sha) != value:
            raise ValueError("source identity collision")
        return sha

    def append(self, batch_id, request_sha, state):
        value = deepcopy(state)
        value.pop("binding", None)
        self.conn.execute("INSERT INTO batches VALUES(?,?,?,?,?)",
                          (value["revision"], batch_id, request_sha, canonical(value), digest(value)))

    def history(self, candidate_id):
        result = []
        for (revision,) in self.conn.execute("SELECT revision FROM batches ORDER BY revision"):
            state = self.read(revision)
            candidate = state["candidates"].get(candidate_id)
            if candidate and (not result or result[-1]["candidate"] != candidate):
                result.append(dict(binding=state["binding"], candidate=candidate))
        if not result:
            raise ValueError("unknown candidate")
        return result
