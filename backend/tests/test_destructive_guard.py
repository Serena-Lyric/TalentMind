from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.integration import import_exchange, import_graph
from app.integration.destructive_guard import (
    AUTHORIZATION_ENV,
    DestructiveOperationDenied,
    authorize_destructive_operation,
    mysql_target_identity,
    neo4j_target_identity,
    target_fingerprint,
)


TARGET = {
    "kind": "mysql",
    "host": "127.0.0.1",
    "port": 23307,
    "database": "talentmind_isolated",
    "hostname": "isolated-container",
    "server_uuid": "00000000-1111-2222-3333-444444444444",
    "version": "8.0.46",
}


def write_authorization(
    path,
    *,
    operation="mysql.import_all",
    target=TARGET,
    expires_at=None,
    authorized_by="owner",
    purpose="isolated integration test",
):
    expires_at = expires_at or (
        datetime.now(timezone.utc) + timedelta(minutes=10)
    ).isoformat()
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operation": operation,
                "target": target,
                "target_fingerprint": target_fingerprint(target),
                "authorized_by": authorized_by,
                "purpose": purpose,
                "expires_at": expires_at,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_destructive_operation_requires_authorization_file(monkeypatch):
    monkeypatch.delenv(AUTHORIZATION_ENV, raising=False)

    with pytest.raises(DestructiveOperationDenied, match="authorization file"):
        authorize_destructive_operation(
            operation="mysql.import_all",
            target=TARGET,
        )


def test_integration_environment_switch_does_not_replace_authorization_file(
    monkeypatch,
):
    monkeypatch.setenv("TALENTMIND_ALLOW_INTEGRATION", "1")
    monkeypatch.delenv(AUTHORIZATION_ENV, raising=False)

    with pytest.raises(DestructiveOperationDenied, match="authorization file"):
        authorize_destructive_operation(
            operation="mysql.import_all",
            target=TARGET,
        )


def test_authorization_rejects_different_target(tmp_path):
    path = write_authorization(tmp_path / "authorization.json")
    changed = dict(TARGET, hostname="another-container")

    with pytest.raises(DestructiveOperationDenied, match="target fingerprint"):
        authorize_destructive_operation(
            operation="mysql.import_all",
            target=changed,
            authorization_file=path,
        )


def test_authorization_rejects_different_operation(tmp_path):
    path = write_authorization(
        tmp_path / "authorization.json",
        operation="mysql.import_skill_dict",
    )

    with pytest.raises(DestructiveOperationDenied, match="operation"):
        authorize_destructive_operation(
            operation="mysql.import_all",
            target=TARGET,
            authorization_file=path,
        )


def test_authorization_rejects_expired_authorization(tmp_path):
    path = write_authorization(
        tmp_path / "authorization.json",
        expires_at="2026-10-21T00:00:00+00:00",
    )

    with pytest.raises(DestructiveOperationDenied, match="expired"):
        authorize_destructive_operation(
            operation="mysql.import_all",
            target=TARGET,
            authorization_file=path,
            now=datetime(2026, 10, 22, tzinfo=timezone.utc),
        )


def test_authorization_accepts_matching_unexpired_target(tmp_path):
    path = write_authorization(
        tmp_path / "authorization.json",
        expires_at="2030-01-01T00:00:00+00:00",
    )

    result = authorize_destructive_operation(
        operation="mysql.import_all",
        target=TARGET,
        authorization_file=path,
        now=datetime(2026, 10, 22, tzinfo=timezone.utc),
    )

    assert result["operation"] == "mysql.import_all"
    assert result["target_fingerprint"] == target_fingerprint(TARGET)


class FakeMappingResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def one(self):
        return self._row


class FakeSqlSession:
    bind = None

    def __init__(self, row):
        self.row = row
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return FakeMappingResult(self.row)


def test_mysql_target_identity_uses_actual_server_and_database():
    session = FakeSqlSession(
        {
            "hostname": "isolated-container",
            "server_uuid": "00000000-1111-2222-3333-444444444444",
            "database_name": "talentmind_isolated",
            "port": 3306,
            "version": "8.0.46",
        }
    )

    identity = mysql_target_identity(session)

    assert identity == {
        "kind": "mysql",
        "host": None,
        "port": 3306,
        "database": "talentmind_isolated",
        "hostname": "isolated-container",
        "server_uuid": "00000000-1111-2222-3333-444444444444",
        "version": "8.0.46",
    }
    assert "hostname" in session.statements[0]
    assert "server_uuid" in session.statements[0]


class FakeNeo4jResult:
    def __init__(self, row):
        self.row = row

    def single(self):
        return self.row


class FakeNeo4jSession:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def run(self, query, **_):
        self.queries.append(query)
        if "db.info" in query:
            return FakeNeo4jResult(self.rows["db"])
        return FakeNeo4jResult(self.rows["components"])


class FakeNeo4jDriver:
    def __init__(self, rows):
        self.neo_session = FakeNeo4jSession(rows)

    def session(self, **_):
        return self.neo_session


def test_neo4j_target_identity_uses_database_identity_and_server_version():
    driver = FakeNeo4jDriver(
        {
            "db": {"id": "db-id", "name": "neo4j", "creationDate": "2026-07-22"},
            "components": {
                "versions": ["5.26.28"],
                "edition": "community",
            },
        }
    )

    identity = neo4j_target_identity(
        driver,
        uri="bolt://user:secret@127.0.0.1:7688",
    )

    assert identity["kind"] == "neo4j"
    assert identity["uri"] == "bolt://127.0.0.1:7688"
    assert identity["database_id"] == "db-id"
    assert identity["database"] == "neo4j"
    assert identity["creation_date"] == "2026-07-22"
    assert identity["version"] == "5.26.28"
    assert identity["edition"] == "community"
    assert "secret" not in json.dumps(identity)


class DeniedSession:
    def __init__(self):
        self.commands = []

    def execute(self, statement):
        self.commands.append(str(statement))
        raise AssertionError("destructive statement must not run")

    def commit(self):
        raise AssertionError("commit must not run")

    def rollback(self):
        return None


def test_import_all_denial_happens_before_mysql_write(monkeypatch):
    session = DeniedSession()

    def deny(*_args, **_kwargs):
        raise DestructiveOperationDenied("denied")

    monkeypatch.setattr(
        import_exchange,
        "require_mysql_destructive_authorization",
        deny,
    )

    with pytest.raises(DestructiveOperationDenied, match="denied"):
        import_exchange.import_all(session=session)

    assert session.commands == []


@pytest.mark.parametrize("operation", ("skill", "definitions", "skills"))
def test_mysql_rebuild_entries_deny_before_write(
    monkeypatch, tmp_path, operation
):
    session = DeniedSession()
    empty_json = tmp_path / "empty.json"
    empty_json.write_text("[]", encoding="utf-8")

    def deny(*_args, **_kwargs):
        raise DestructiveOperationDenied("denied")

    monkeypatch.setattr(
        import_exchange,
        "require_mysql_destructive_authorization",
        deny,
    )
    functions = {
        "skill": lambda: import_exchange.import_skill_dict(
            path=empty_json,
            session=session,
        ),
        "definitions": lambda: import_exchange.import_job_definitions(
            path=empty_json,
            session=session,
        ),
        "skills": lambda: import_exchange.import_job_skills(
            path=empty_json,
            session=session,
        ),
    }

    with pytest.raises(DestructiveOperationDenied, match="denied"):
        functions[operation]()

    assert session.commands == []


def test_default_change_log_rebuild_denies_before_write(
    monkeypatch, tmp_path
):
    session = DeniedSession()
    monkeypatch.setattr(
        import_exchange,
        "load_return_package",
        lambda _path: {"change_logs": []},
    )

    def deny(*_args, **_kwargs):
        raise DestructiveOperationDenied("denied")

    monkeypatch.setattr(
        import_exchange,
        "require_mysql_destructive_authorization",
        deny,
    )

    with pytest.raises(DestructiveOperationDenied, match="denied"):
        import_exchange.import_change_logs(
            package_dir=tmp_path,
            session=session,
        )

    assert session.commands == []


def test_explicit_change_log_append_denies_before_write(
    monkeypatch, tmp_path
):
    session = DeniedSession()
    logs_path = tmp_path / "change-logs.json"
    logs_path.write_text(
        json.dumps([{"job_id": "job-1", "change_type": "added"}]),
        encoding="utf-8",
    )

    def deny(*_args, **_kwargs):
        raise DestructiveOperationDenied("denied")

    monkeypatch.setattr(
        import_exchange,
        "require_mysql_destructive_authorization",
        deny,
    )

    with pytest.raises(DestructiveOperationDenied, match="denied"):
        import_exchange.import_change_logs(
            path=logs_path,
            session=session,
        )

    assert session.commands == []


def test_import_graph_denial_happens_before_neo4j_delete(
    monkeypatch, tmp_path
):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps({"nodes": [], "edges": []}),
        encoding="utf-8",
    )
    session = DeniedSession()

    class Driver:
        def session(self):
            return session

    monkeypatch.setattr(import_graph, "get_neo4j", lambda: Driver())

    def deny(*_args, **_kwargs):
        raise DestructiveOperationDenied("denied")

    monkeypatch.setattr(
        import_graph,
        "require_neo4j_destructive_authorization",
        deny,
    )

    with pytest.raises(DestructiveOperationDenied, match="denied"):
        import_graph.import_graph(graph_path)

    assert session.commands == []
