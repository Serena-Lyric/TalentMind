"""SQL 解析器 —— 从 mysqldump 中提取 jd_pool 记录。"""
import re
from .models import JdRecord

# jd_pool 表的列顺序（对应 INSERT 语句的列）
_COLUMNS = ["id", "source", "job_title", "raw_text", "duties", "experience",
            "quality", "dup_group", "crawled_at", "status"]


# SQL 转义解码表（mysqldump 标准：\n \r \t \\ \' \" 等）
_SQL_ESCAPES = {
    "n": "\n", "r": "\r", "t": "\t", "0": "\0",
    "\\": "\\", "'": "'", '"': '"',
}


def _unescape_sql(s: str) -> str:
    """解码 SQL 转义序列（\n → 换行 等）。

    注意：parse_jd_pool 的字段扫描已内建解码，此函数仅供
    含反斜杠转义的独立字符串使用（与解析器行为一致）。
    """
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] in _SQL_ESCAPES:
            out.append(_SQL_ESCAPES[s[i + 1]])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _split_sql_values(raw: str) -> list[str]:
    """
    将 SQL VALUES 元组内容按字段切分。
    处理引号内的逗号、转义引号。
    raw 不含外层括号，如：1020,'dataset','title','text','duties','exp',0.31,'grp','2026-07-24','cleaned'
    """
    fields = []
    i = 0
    n = len(raw)

    while i < n:
        # 跳过前导空白
        while i < n and raw[i] in (" ", "\t", "\n", "\r"):
            i += 1
        if i >= n:
            break

        ch = raw[i]
        if ch == "'":
            # 单引号字符串：找到闭合引号（处理 '' 转义和 \ 转义）
            i += 1  # 跳过起始引号
            buf = []
            while i < n:
                if raw[i] == "\\":
                    # SQL 转义序列：解码为实际字符
                    if i + 1 < n and raw[i + 1] in _SQL_ESCAPES:
                        buf.append(_SQL_ESCAPES[raw[i + 1]])
                        i += 2
                    else:
                        # 未知转义：保留原字符
                        buf.append(raw[i + 1] if i + 1 < n else "")
                        i += 2 if i + 1 < n else 1
                    continue
                if raw[i] == "'":
                    if i + 1 < n and raw[i + 1] == "'":
                        # SQL 转义：两个单引号 = 一个单引号
                        buf.append("'")
                        i += 2
                        continue
                    # 字符串结束
                    i += 1
                    break
                buf.append(raw[i])
                i += 1
            fields.append("".join(buf))
        elif ch == '"':
            # 双引号字符串
            i += 1
            buf = []
            while i < n:
                if raw[i] == "\\":
                    if i + 1 < n and raw[i + 1] in _SQL_ESCAPES:
                        buf.append(_SQL_ESCAPES[raw[i + 1]])
                        i += 2
                    else:
                        buf.append(raw[i + 1] if i + 1 < n else "")
                        i += 2 if i + 1 < n else 1
                    continue
                if raw[i] == '"':
                    i += 1
                    break
                buf.append(raw[i])
                i += 1
            fields.append("".join(buf))
        elif ch == ",":
            # 空字段
            fields.append("")
            i += 1
        else:
            # 无引号值（数字、NULL 等）
            j = i
            while j < n and raw[j] not in (",", " ", "\t", "\n", "\r"):
                j += 1
            val = raw[i:j]
            fields.append(val)
            i = j

        # 跳过逗号分隔符
        while i < n and raw[i] in (" ", "\t", "\n", "\r"):
            i += 1
        if i < n and raw[i] == ",":
            i += 1

    return fields


def parse_jd_pool(path: str) -> list[JdRecord]:
    """
    解析 seed_jd_pool.sql，返回所有 JdRecord。
    每行一个 INSERT INTO jd_pool VALUES (...);
    """
    records: list[JdRecord] = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or not line.upper().startswith("INSERT"):
                continue
            if "jd_pool" not in line:
                continue

            # 提取 VALUES (...) 部分
            # 格式: INSERT INTO `jd_pool` (...) VALUES (...);
            m = re.search(r"VALUES\s*\((.+)\)\s*;?\s*$", line, re.IGNORECASE)
            if not m:
                continue

            raw_values = m.group(1)
            fields = _split_sql_values(raw_values)

            if len(fields) < len(_COLUMNS):
                continue

            row = dict(zip(_COLUMNS, fields[:len(_COLUMNS)]))
            try:
                records.append(JdRecord(
                    id=int(row["id"]),
                    source=row["source"],
                    job_title=row["job_title"],
                    raw_text=row["raw_text"],
                    duties=row["duties"],
                    experience=row["experience"],
                    quality=float(row["quality"]),
                    dup_group=row["dup_group"],
                    crawled_at=row["crawled_at"],
                    status=row["status"],
                ))
            except (ValueError, TypeError):
                pass

    return records


def parse_records_by_ids(path: str, ids: set[int]) -> list[JdRecord]:
    """只加载指定 ID 的记录，用于单层调试。"""
    all_records = parse_jd_pool(path)
    return [r for r in all_records if r.id in ids]
