"""Decode mysqldump value tokens without executing SQL or loading old M2 models."""

_SQL_ESCAPES = {
    "n": "\n", "r": "\r", "t": "\t", "0": "\0",
    "\\": "\\", "'": "'", '"': '"',
}


def split_sql_values(raw: str) -> list[str]:
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
