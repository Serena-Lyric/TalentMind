"""Explicit, read-only M1 sample export. Never creates clients on import."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

TABLES = ("jd_pool", "signal", "skill_dict", "job_definition", "job_skill", "job_change_log", "resume", "talent_raw")


def validate_destination(path):
    path = Path(path).resolve()
    root = Path(__file__).resolve().parents[3]
    if path.exists() or (path.is_relative_to(root) and not path.is_relative_to(root / "data/local")):
        raise ValueError("destination must be new and private (data/local inside repository)")
    return path


def export_sample(env, output, per_platform=40):
    from dotenv import dotenv_values
    import pymysql
    from sqlalchemy.engine import make_url
    output = validate_destination(output)
    if not 1 <= per_platform <= 100:
        raise ValueError("per-platform must be 1..100 for this bounded export")
    url = make_url(dotenv_values(env)["MYSQL_URL"])
    connection = pymysql.connect(host=url.host, port=url.port or 3306, user=url.username,
        password=url.password, database=url.database, charset="utf8mb4", autocommit=False,
        cursorclass=pymysql.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")
            def counts():
                result = {}
                for table in TABLES:
                    cursor.execute(f"SELECT COUNT(*) AS n FROM `{table}`")
                    result[table] = cursor.fetchone()["n"]
                return result
            before = counts()
            rows = []
            for source in ("boss", "zhaopin", "liepin"):
                cursor.execute("SELECT * FROM jd_pool WHERE source=%s ORDER BY id LIMIT %s", (source, per_platform))
                rows.extend(cursor.fetchall())
            after = counts()
            if before != after:
                raise ValueError("read transaction counts changed")
    finally:
        connection.rollback()
        connection.close()
    # Snapshot DATETIME values retain the original local text, without invented timezone.
    for row in rows:
        if row.get("crawled_at") is not None:
            row["crawled_at"] = str(row["crawled_at"])
        for field in ("duties", "experience"):
            if row.get(field) is None:
                row.pop(field, None)
    output.mkdir(parents=True)
    data = (json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    (output / "input.json").write_bytes(data)
    provenance = dict(schema_version="m1-readonly-sample-1", transaction="START TRANSACTION READ ONLY; ROLLBACK",
        selection="boss,zhaopin,liepin; ORDER BY id ASC; fixed per-platform LIMIT", per_platform=per_platform,
        input_sha256=hashlib.sha256(data).hexdigest(), counts_by_source=dict(Counter(r["source"] for r in rows)),
        table_counts_before=before, table_counts_after=after,
        identities=[dict(id=r["id"], source=r["source"]) for r in rows])
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return provenance


def export_sql(sql_path, output, per_platform=40, *, offset=0):
    """Read only the named table in a mysqldump; never execute SQL."""
    from ..job_analysis.db import _split_sql_values
    output = validate_destination(output)
    if not 1 <= per_platform <= 100:
        raise ValueError("per-platform must be 1..100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a nonnegative integer")
    data = Path(sql_path).read_bytes()
    text = data.decode("utf-8-sig")
    create = re.search(r"CREATE TABLE `jd_pool` \((.*?)\n\)", text, re.S)
    if create is None:
        raise ValueError("jd_pool schema missing")
    columns = re.findall(r"^\s*`([^`]+)`", create[1], re.M)
    literal = re.compile(r"'(?:\\.|''|[^'\\])*'|NULL|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
    rows = []
    for line in text.splitlines():
        if not line.startswith("INSERT INTO `jd_pool` VALUES "):
            continue
        values = line[len("INSERT INTO `jd_pool` VALUES "):].rstrip(";")
        # Tokens delimit tuples; SQL-looking content inside a quoted token stays data.
        pos = 0
        while pos < len(values):
            if values[pos] != "(":
                raise ValueError("unsupported mysqldump tuple")
            pos += 1
            fields = []
            while True:
                match = literal.match(values, pos)
                if not match:
                    raise ValueError("unsupported mysqldump literal")
                token = match[0]
                value = _split_sql_values(token)[0] if token.startswith("'") else None if token == "NULL" else float(token) if any(c in token for c in ".eE") else int(token)
                fields.append(value)
                pos = match.end()
                delimiter = values[pos:pos + 1]
                pos += 1
                if delimiter == ")":
                    break
                if delimiter != ",":
                    raise ValueError("unsupported mysqldump delimiter")
            if len(fields) != len(columns):
                raise ValueError("mysqldump column mismatch")
            rows.append(dict(zip(columns, fields)))
            if pos < len(values):
                if values[pos] != ",":
                    raise ValueError("unsupported mysqldump tuple separator")
                pos += 1
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("empty or duplicate jd_pool identities")
    selected = [r for platform in ("boss", "zhaopin", "liepin") for r in sorted((r for r in rows if r["source"] == platform), key=lambda r: r["id"])[offset:offset + per_platform]]
    output.mkdir(parents=True)
    encoded = (json.dumps(selected, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    (output / "input.json").write_bytes(encoded)
    provenance = dict(schema_version="m1-readonly-sample-1", source_kind="preserved_mysqldump_not_live_database",
        source_sha256=hashlib.sha256(data).hexdigest(), source_filename=Path(sql_path).name,
        selection="boss,zhaopin,liepin; ORDER BY id ASC; fixed per-platform OFFSET/LIMIT", per_platform=per_platform, offset=offset,
        available_counts=dict(Counter(r["source"] for r in rows)), available_total=len(rows),
        counts_by_source=dict(Counter(r["source"] for r in selected)), input_sha256=hashlib.sha256(encoded).hexdigest(),
        identities=[dict(id=r["id"], source=r["source"]) for r in selected])
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    origin = parser.add_mutually_exclusive_group(required=True)
    origin.add_argument("--env", type=Path)
    origin.add_argument("--sql", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-platform", type=int, default=40)
    parser.add_argument("--offset", type=int, default=0, help="SQL-only disjoint per-platform ID window")
    args = parser.parse_args()
    if args.offset and not args.sql:
        parser.error("offset requires --sql")
    result = export_sql(args.sql, args.output, args.per_platform, offset=args.offset) if args.sql else export_sample(args.env, args.output, args.per_platform)
    print(json.dumps({k: v for k, v in result.items() if k != "identities"}, ensure_ascii=True))


if __name__ == "__main__":
    main()
