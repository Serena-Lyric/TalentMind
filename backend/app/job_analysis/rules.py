"""硬规则预筛 —— CJK 优化的乱码检测 + 去重。"""
import re
from app.job_analysis.models import JdRecord, RejectedItem

# CJK 统一汉字 + 扩展区
_CJK_RANGES = [
    (0x4E00, 0x9FFF),    # CJK Unified
    (0x3400, 0x4DBF),    # CJK Extension A
    (0x20000, 0x2A6DF),  # CJK Extension B
]
_CJK_PUNCTUATION = set("。，、；：「」！？…—～（）【】《》・　")
_ASCII_SYMBOLS = set(".,;:!?()[]{}/-_+=@#$%^&*\"'`~|\\")


def _is_readable_char(ch: str) -> bool:
    """判断字符是否为可读内容（非乱码）。"""
    cp = ord(ch)
    for lo, hi in _CJK_RANGES:
        if lo <= cp <= hi:
            return True
    if ch.isascii() and ch.isalpha():
        return True
    if ch.isdigit():
        return True
    if ch in _CJK_PUNCTUATION:
        return True
    if ch in _ASCII_SYMBOLS:
        return True
    if ch.isspace():
        return True
    return False


def _info_density(record: JdRecord) -> int:
    """计算 JD 的有效信息密度：去 HTML 标签 + 空白后的字符数。"""
    text = record.raw_text + record.duties
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"\s+", "", text)
    return len(text)


def apply_rules(
    records: list[JdRecord],
    garbled_ratio_threshold: float = 0.25,
    garbled_min_length: int = 30,
) -> tuple[list[JdRecord], list[RejectedItem]]:
    """
    硬规则预筛:
      1. 空字段: raw_text + duties 皆空 → 拒
      2. 乱码: 可读比例 < 阈值 且 长度 > 下限 → 拒
      3. 去重: 同 dup_group 保留最高 quality / 最高密度者
    """
    passed: list[JdRecord] = []
    rejected: list[RejectedItem] = []

    # ── 1. 空字段检测 ──
    non_empty: list[JdRecord] = []
    for r in records:
        has_content = bool(r.raw_text.strip()) or bool(r.duties.strip())
        if not has_content:
            rejected.append(RejectedItem(
                jd_id=r.id, rule_id="empty_fields",
                detail="raw_text and duties are both empty",
            ))
        else:
            non_empty.append(r)

    # ── 2. 乱码检测 ──
    not_garbled: list[JdRecord] = []
    for r in non_empty:
        text = r.raw_text
        total = len(text)
        if total == 0:
            rejected.append(RejectedItem(
                jd_id=r.id, rule_id="garbled",
                detail="raw_text is empty",
            ))
            continue
        if total < garbled_min_length:
            not_garbled.append(r)
            continue
        readable = sum(1 for ch in text if _is_readable_char(ch))
        ratio = readable / total
        if ratio < garbled_ratio_threshold:
            rejected.append(RejectedItem(
                jd_id=r.id, rule_id="garbled",
                detail=f"readable ratio {ratio:.2f} "
                       f"(threshold={garbled_ratio_threshold})",
            ))
        else:
            not_garbled.append(r)

    # ── 3. dup_group 去重 ──
    groups: dict[str, list[JdRecord]] = {}
    for r in not_garbled:
        if not r.dup_group.strip():
            passed.append(r)
        else:
            groups.setdefault(r.dup_group, []).append(r)

    for gid, group in groups.items():
        group.sort(key=lambda x: (x.quality, _info_density(x)), reverse=True)
        keeper = group[0]
        passed.append(keeper)
        for r in group[1:]:
            rejected.append(RejectedItem(
                jd_id=r.id, rule_id="duplicate",
                detail=f"dup_group={gid}, kept jd_id={keeper.id} "
                       f"(quality={keeper.quality})",
                kept_jd_id=keeper.id,
            ))

    return passed, rejected
