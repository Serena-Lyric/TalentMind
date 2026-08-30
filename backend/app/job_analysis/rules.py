"""硬规则预筛 —— CJK 优化的乱码检测 + 去重。"""
import re
from .models import JdRecord, RejectedItem

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


# ── 分层切割（L0 顺路产出，供 LLM 阶段消费）──
# 按标题行分段（真实 JD 常无空行分隔；标题=短行且匹配关键词模式）
_REQUIRE_HEAD = re.compile(
    r"^(qualifications?|requirements?|what you.{0,20}(do|need|bring)|"
    r"responsibilities|skills?( and experience)?|experience with|"
    r"任职要求|岗位要求|职位要求|职责|岗位职责|工作内容|技能要求)"
    r"[:：]?\s*$", re.I)
_JUNK_HEAD = re.compile(
    r"^(about (us|the company|skf|\w+)|our (culture|story|values)|"
    r"benefits|why (join|work)|equal opportunity|diversity|inclusion|"
    r"company (profile|overview)|who we are|"
    r"公司简介|公司介绍|福利待遇|五险一金|关于我们)"
    r"[:：]?\s*$", re.I)
_HEAD_MAX_LEN = 60


_INLINE_REQ_RE = re.compile(
    r"(candidates? (must|should|will)|you (must|will|should|need)|"
    r"requirements? (include|:)|experience with|proficient|knowledge of|"
    r"familiarity with|expertise in|hands-?on (experience )?with|"
    r"working knowledge|background in|degree in|"
    r"任职|精通|熟悉|具备|经验优先|年以上)", re.I)
_INLINE_JUNK_RE = re.compile(
    r"(benefits|salary|equal opportunity|diversity|inclusion|culture|"
    r"we are|our |competitive|perks|insurance|401|pto|"
    r"福利|薪资|待遇|五险一金|双休|年终奖)", re.I)
# 技能守卫：垃圾段若含真实技能词则不删（防误伤）
_SKILL_GUARD_RE = re.compile(
    r"\b(python|java|javascript|sql|aws|azure|gcp|docker|kubernetes|"
    r"k8s|react|typescript|terraform|salesforce|sap|oracle|tableau|"
    r"\.net|flask|django|linux|machine learning|data (science|"
    r"engineering|analytics)|cloud|api|excel|power ?bi)\b", re.I)


def segment_text(record: JdRecord) -> dict:
    """把 JD 切成 A 层（喂 LLM 的文本）。删除式策略，宁松勿紧：

    1. 短文本（<=4000）全保留
    2. 长文本：删 C 层（公司简介/福利/合规，除非含技能守卫词），其余全保留
    3. 删后仍 >6000：句级打分截断（需求句 +2、技能词 +1、垃圾词 -2）
    """
    text = record.raw_text
    if len(text) <= 4000:
        return {"a_text": text, "has_skills_section": True}

    # ── 标题段分层 ──
    sections: list[tuple[str, list[str]]] = []
    current_head, current_body = "", []
    for line in text.split("\n"):
        line_stripped = line.strip()
        is_head = (line_stripped and len(line_stripped) <= _HEAD_MAX_LEN
                   and (_REQUIRE_HEAD.match(line_stripped)
                        or _JUNK_HEAD.match(line_stripped)))
        if is_head:
            if current_head or current_body:
                sections.append((current_head, current_body))
            current_head, current_body = line_stripped, []
        else:
            current_body.append(line)
    if current_head or current_body:
        sections.append((current_head, current_body))

    if sections:
        kept_blobs = []
        for head, body in sections:
            blob = "\n".join(body).strip()
            if not blob:
                continue
            if head and _JUNK_HEAD.match(head) and not _SKILL_GUARD_RE.search(blob):
                continue                  # C 层删除（技能守卫防误伤）
            kept_blobs.append(blob)
        a_text = "\n\n".join(kept_blobs).strip()
    else:
        # 无标题行：句级删 JUNK 句
        kept = [s for s in _split_sentences(text)
                if not (_INLINE_JUNK_RE.search(s)
                        and not _SKILL_GUARD_RE.search(s))]
        a_text = "\n".join(kept).strip()

    if not a_text:
        return {"a_text": text[:2000] + "\n...[truncated]...\n"
                + text[-2000:], "has_skills_section": False}

    # ── 超长截断：句级打分 ──
    if len(a_text) > 6000:
        sents = _split_sentences(a_text)
        ranked = sorted(sents, key=_sent_score, reverse=True)
        out, size = [], 0
        for s in ranked:
            if size + len(s) > 6000:
                break
            out.append(s)
            size += len(s)
        a_text = "\n".join(out) + "\n...[truncated]..."

    return {"a_text": a_text, "has_skills_section": True}


def _sent_score(sent: str) -> int:
    score = 0
    if _INLINE_REQ_RE.search(sent):
        score += 2
    if _SKILL_GUARD_RE.search(sent):
        score += 1
    if _INLINE_JUNK_RE.search(sent):
        score -= 2
    return score


def _split_sentences(text: str) -> list[str]:
    """按句号/换行切句，兼容句号后无空格紧跟大写字母的写法。"""
    parts = re.split(r"(?<=[.!?。！？])(?=\s*[A-Z一-鿿])", text)
    out = []
    for p in parts:
        out.extend(l for l in p.split("\n") if l.strip())
    return out
