"""SQL 解析器 —— 从 mysqldump 中提取 jd_pool 记录。"""
import re
from app.job_analysis.models import JdRecord

# jd_pool 表的列顺序（对应 INSERT 语句的列）
_COLUMNS = ["id", "source", "job_title", "raw_text", "duties", "experience",
            "quality", "dup_group", "crawled_at", "status"]


def _unescape_sql(s: str) -> str:
    """反转义 SQL 字符串中的特殊字符。"""
    s = s.replace("\\'", "'")
    s = s.replace('\\"', '"')
    s = s.replace("\\n", "\n")
    s = s.replace("\\r", "\r")
    s = s.replace("\\t", "\t")
    s = s.replace("\\\\", "\\")
    return s


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
            # 单引号字符串：找到闭合引号（处理 '' 转义和 \' 转义）
            i += 1  # 跳过起始引号
            buf = []
            while i < n:
                if raw[i] == "\\":
                    # 转义字符：保留下一个字符
                    i += 1
                    if i < n:
                        buf.append(raw[i])
                        i += 1
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
                    i += 1
                    if i < n:
                        buf.append(raw[i])
                        i += 1
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
                    source=_unescape_sql(row["source"]),
                    job_title=_unescape_sql(row["job_title"]),
                    raw_text=_unescape_sql(row["raw_text"]),
                    duties=_unescape_sql(row["duties"]),
                    experience=_unescape_sql(row["experience"]),
                    quality=float(row["quality"]),
                    dup_group=_unescape_sql(row["dup_group"]),
                    crawled_at=row["crawled_at"],
                    status=_unescape_sql(row["status"]),
                ))
            except (ValueError, TypeError):
                pass

    return records


def parse_records_by_ids(path: str, ids: set[int]) -> list[JdRecord]:
    """只加载指定 ID 的记录，用于单层调试。"""
    all_records = parse_jd_pool(path)
    return [r for r in all_records if r.id in ids]
