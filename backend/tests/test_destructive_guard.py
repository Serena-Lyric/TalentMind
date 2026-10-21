from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.engine import URL

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
    "connection_port": 23307,
    "server_port": 3306,
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


def test_authorization_requires_file_even_with_integration_env(monkeypatch):
    monkeypatch.setenv("TALENTMIND_ALLOW_INTEGRATION", "1")
    monkeypatch.delenv(AUTHORIZATION_ENV, raising=False)

    with pytest.raises(DestructiveOperationDenied, match="authorization file"):
        authorize_destructive_operation(
            operation="mysql.import_all",
            target=TARGET,
        )


@pytest.mark.parametrize(
    "change,message",
    [
        ({"operation": "mysql.import_skill_dict"}, "operation"),
        ({"target": dict(TARGET, hostname="another-container")}, "fingerprint"),
        ({"expires_at": "2026-10-21T00:00:00+00:00"}, "expired"),
    ],
)
def test_authorization_rejects_wrong_operation_target_or_expiry(
    tmp_path, change, message
):
    path = write_authorization(tmp_path / "authorization.json", **change)
    with pytest.raises(DestructiveOperationDenied, match=message):
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
        self.row = row

    def mappings(self):
        return self

    def one(self):
        return self.row


class IdentitySession:
    def __init__(self, connection_port=23307, server_port=3306):
        self.bind = type(
            "Bind",
            (),
            {
                "url": URL.create(
                    "mysql+pymysql",
                    host="127.0.0.1",
                    port=connection_port,
                )
            },
        )()
        self.server_port = server_port
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return FakeMappingResult(
            {
                "hostname": "isolated-container",
                "server_uuid": "00000000-1111-2222-3333-444444444444",
                "database_name": "talentmind_isolated",
                "server_port": self.server_port,
                "version": "8.0.46",
            }
        )


def test_mysql_identity_uses_live_server_and_database():
    session = IdentitySession()

    assert mysql_target_identity(session) == TARGET
    assert "@@hostname" in session.statements[0]
    assert "@@server_uuid" in session.statements[0]
    assert "DATABASE()" in session.statements[0]


def test_same_mysql_clone_on_different_host_ports_has_distinct_fingerprint():
    first = mysql_target_identity(IdentitySession(connection_port=23307))
    second = mysql_target_identity(IdentitySession(connection_port=23308))

    assert first["hostname"] == second["hostname"]
    assert first["server_uuid"] == second["server_uuid"]
    assert first["server_port"] == second["server_port"] == 3306
    assert first["connection_port"] == 23307
    assert second["connection_port"] == 23308
    assert target_fingerprint(first) != target_fingerprint(second)


def test_authorization_for_one_host_port_rejects_same_clone_on_another(tmp_path):
    first = mysql_target_identity(IdentitySession(connection_port=23307))
    second = mysql_target_identity(IdentitySession(connection_port=23308))
    path = write_authorization(tmp_path / "authorization.json", target=first)

    with pytest.raises(DestructiveOperationDenied, match="fingerprint"):
        authorize_destructive_operation(
            operation="mysql.import_all",
            target=second,
            authorization_file=path,
        )


class FakeNeo4jResult:
    def __init__(self, row):
        self.row = row

    def single(self):
        return self.row


class FakeNeo4jSession:
    def __init__(self):
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def run(self, query, **_):
        self.queries.append(query)
        if "db.info" in query:
            return FakeNeo4jResult(
                {"id": "db-id", "name": "neo4j", "creationDate": "2026-07-22"}
            )
        return FakeNeo4jResult(
            {"versions": ["5.26.28"], "edition": "community"}
        )


class FakeNeo4jDriver:
    def __init__(self):
        self.fake_session = FakeNeo4jSession()

    def session(self, **_):
        return self.fake_session


def test_neo4j_identity_omits_credentials():
    identity = neo4j_target_identity(
        FakeNeo4jDriver(),
        uri="bolt://user:secret@127.0.0.1:7688",
    )

    assert identity["uri"] == "bolt://127.0.0.1:7688"
    assert identity["database_id"] == "db-id"
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

    def close(self):
        return None


def deny(*_args, **_kwargs):
    raise DestructiveOperationDenied("denied")


def test_import_all_denial_happens_before_mysql_write(monkeypatch, tmp_path):
    session = DeniedSession()
    monkeypatch.setattr(
        import_exchange,
        "load_return_package",
        lambda _path: {
            "definitions": [],
            "skills": [],
            "change_logs": [],
        },
    )
    monkeypatch.setattr(
        import_exchange, "_load_skill_dict", lambda: (set(), {})
    )
    monkeypatch.setattr(
        import_exchange,
        "require_mysql_destructive_authorization",
        deny,
    )

    with pytest.raises(DestructiveOperationDenied, match="denied"):
        import_exchange.import_all(package_dir=tmp_path, session=session)

    assert session.commands == []


@pytest.mark.parametrize("operation", ("skill", "definitions", "skills", "logs"))
def test_mysql_rebuild_entries_deny_before_write(monkeypatch, tmp_path, operation):
    session = DeniedSession()
    empty_json = tmp_path / "empty.json"
    empty_json.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        import_exchange,
        "require_mysql_destructive_authorization",
        deny,
    )
    functions = {
        "skill": lambda: import_exchange.import_skill_dict(
            path=empty_json, session=session
        ),
        "definitions": lambda: import_exchange.import_job_definitions(
            path=empty_json, session=session
        ),
        "skills": lambda: import_exchange.import_job_skills(
            path=empty_json, session=session
        ),
        "logs": lambda: import_exchange.import_change_logs(
            path=empty_json, session=session
        ),
    }

    with pytest.raises(DestructiveOperationDenied, match="denied"):
        functions[operation]()

    assert session.commands == []


def test_import_graph_denial_happens_before_neo4j_delete(monkeypatch, tmp_path):
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
    monkeypatch.setattr(
        import_graph,
        "require_neo4j_destructive_authorization",
        deny,
    )

    with pytest.raises(DestructiveOperationDenied, match="denied"):
        import_graph.import_graph(graph_path)

    assert session.commands == []
