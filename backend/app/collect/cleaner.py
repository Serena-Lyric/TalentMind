import re
from datetime import datetime, timezone
from app.collect.schema import RawJD

# ── 杂讯剥离 ────────────────────────────────────────────

NOISE_LINE_PATTERNS = [
    r"^(Pay|Salary|Compensation|Wage)\s*:",
    r"^\$[\d,.\s]+(.+?(hour|year|month|week|annum))",
    r"^(Expected\s+)?[Hh]ours?\s*:",
    r"^(Benefits?|Perks)\s*:",
    r"^Schedule\s*:",
    r"^(Work\s+)?[Ll]ocation\s*:",
    r"^Job\s+[Tt]ype\s*:",
    r"^\$[\d,.]+\s*[-–to]+\s*\$?[\d,.]+",
    r"^https?://\S+$",
]

FUSED_PREFIXES = [
    "Job description",
    "Job Description",
    "Job Summary",
    "Job summary",
    "About the job",
    "About this job",
]


def _fix_fused_prefix(text: str) -> str:
    """修复粘连前缀：'Job descriptionA leading...' → 'A leading...'"""
    for prefix in FUSED_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix):
            next_char = text[len(prefix)]
            if next_char.isalpha() or (next_char.isascii() and not next_char.isspace()):
                text = text[len(prefix):]
                break
    return text


def _is_noise_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    for pat in NOISE_LINE_PATTERNS:
        if re.match(pat, line):
            return True
    return False


def _strip_noise(text: str) -> str:
    """剥离薪资/福利/工时/地点等杂讯行，修复粘连前缀。"""
    text = _fix_fused_prefix(text or "")
    lines = text.split("\n")
    kept = [ln for ln in lines if not _is_noise_line(ln)]
    return "\n".join(kept).strip()


# ── 职责提取 ────────────────────────────────────────────

DUTY_HEADER_PATTERN = re.compile(
    r"(?im)^(?:Key\s+)?Responsibilities?:?\s*$|"
    r"^Essential\s+Functions?:?\s*$|"
    r"^(?:Primary\s+)?Duties?:?\s*$|"
    r"^(?:职位描述|岗位职责|工作职责|工作内容)\s*:?[ \t]*$|"
    r"^What\s+You'?ll\s+Do:?\s*$|"
    r"^Role\s*:?\s*$"
)

# 职责段结束标志：下一个标题行（全大写或常见标题）
SECTION_BOUNDARY_PATTERN = re.compile(
    r"(?im)^(?:Qualifications?|Requirements?|Education|Experience|Skills?|"
    r"About\s+(?:Us|the\s+Company)|Benefits?|Compensation|"
    r"We\s+(?:Are|Offer|Value)|How\s+to\s+Apply|"
    r"Equal\s+Opportunity|Our\s+Company|任职要求|岗位要求|职位要求|"
    r"福利待遇|公司介绍|公司简介|工作地址)\s*:?"
)


def _extract_duties(text: str) -> str:
    """识别职责段落，截取至下一个标题或末尾。"""
    match = DUTY_HEADER_PATTERN.search(text or "")
    if not match:
        return ""
    start = match.end()
    remainder = text[start:]
    boundary = SECTION_BOUNDARY_PATTERN.search(remainder)
    if boundary:
        remainder = remainder[:boundary.start()]
    return remainder.strip()


_SOURCE_SECTION_HEADER = re.compile(
    r"(?im)(?:^|(?<=[\s。；;！？!?]))[ \t]*(?:"
    r"(?P<duties>(?:Key[ \t]+)?Responsibilities?|Essential[ \t]+Functions?|"
    r"(?:Primary[ \t]+)?Duties?|职位描述|岗位职责|工作职责|工作内容|What[ \t]+You'?ll[ \t]+Do|Role)|"
    r"(?P<requirements>Qualifications?|Requirements?|任职要求|岗位要求|职位要求|技能要求)|"
    r"Education|Experience|Skills?|About[ \t]+(?:Us|the[ \t]+Company)|Benefits?|Perks|Compensation|"
    r"We[ \t]+(?:Are|Offer|Value)|How[ \t]+to[ \t]+Apply|Equal[ \t]+Opportunity|Our[ \t]+Company|"
    r"福利(?:待遇)?|公司介绍|公司简介|工作地址)"
    r"(?:[ \t]*[:：][ \t]*|[ \t]*(?=\r?$))"
)


def source_sections(text: str | None) -> dict[str, str | None]:
    """只读展示：沿用职责/边界标题词表，切原文；不改变清洗或存储规则。"""
    text = text or ''
    result = {'duties': None, 'requirements': None, 'structure_source': None}
    headers = list(_SOURCE_SECTION_HEADER.finditer(text))
    for index, header in enumerate(headers):
        field = header.lastgroup
        if field and result[field] is None:
            end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
            result[field] = text[header.end():end].strip() or None
    if result['duties'] or result['requirements']:
        result['structure_source'] = '原文标题分段'
    return result


# ── 经验提取 ────────────────────────────────────────────

EXPERIENCE_LINE_RE = re.compile(
    r"(?im)^Experience\s*:\s*(.{0,255})"  # 单行描述无换行时 (.+)$ 会捕获整段，超 VARCHAR(255) 列宽；提取层截断至契约上限
)


def _extract_experience(text: str, fallback: str) -> str:
    """列优先，空时正则回退。

    jd_pool.experience 为 VARCHAR(255)（D33 扩容）；捕获长度限制在 255 内，
    避免单行 JD 描述中 "Experience:" 后整段被捕获导致 DataError(1406)。
    """
    if fallback and fallback.strip():
        return fallback.strip()
    match = EXPERIENCE_LINE_RE.search(text or "")
    if match:
        return match.group(1).strip()[:255]
    return ""


# ── 入库前有效性判定 ────────────────────────────────────

def is_valid_jd(row: dict) -> bool:
    """三平台入库前的保守规则；只判定，不改写原文或依赖质量分/字数。"""
    title = (row.get("job_title") or "").strip()
    if not title:
        return False
    text = row.get("raw_text") or ""
    job_headers = r"职位描述|岗位职责|工作职责|工作内容|任职要求|岗位要求|职位要求|技能要求"
    job_boundary = rf"(?:{job_headers})(?:\s*[:：]|\s+)"
    # 适配器追加的公司介绍，以及描述内的介绍段，都不能充当岗位内容。
    text = re.sub(
        rf"(?m)(?:^|(?<=[。；;！？!?：:]))[ \t]*(?:公司简介|公司介绍|企业简介|关于我们)"
        rf"(?:[ \t]*[:：]|[ \t]*\n)[\s\S]*?(?={job_boundary}|\Z)",
        "", text,
    )
    text = re.sub(
        r"(?m)^\s*(?:公司|公司规模|公司阶段|行业|薪资|薪酬|工资|地点|地区|工作地址|"
        rf"经验|学历|福利(?:待遇)?|薪资待遇)\s*[:：][^\n]*?(?={job_boundary}|\n|$)", "", text,
    )
    # 任职要求与职责不要求同时出现；岗位技能标签也可提供实质信息。
    text = re.sub(rf"(?:{job_headers}|技能标签)\s*[:：]?", "", text)
    text = re.sub(
        r"暂无(?:描述|信息)?|详情面议|面议|待补充|详见详情|欢迎加入我们|欢迎加入|"
        r"五险一金|六险一金|周末双休|双休|带薪年假|节日福利|包吃包住|"
        r"经验不限|不限经验|学历不限|应届生|在校生|本科|大专|硕士|博士|高中|中专|"
        r"\d+\s*(?:[-~至]\s*\d+)?\s*年(?:以上)?", "", text,
    )
    # 只排除完整匹配的宣传/联系/元信息片段，不从正文中删词或要求技能白名单。
    non_job_clause = (
        r"详情请咨询|招聘中|欢迎投递(?:简历)?|(?:岗位)?长期招聘|"
        r"投递简历请联系\s*HR|待遇优厚|工作轻松|"
        r"\d+(?:\.\d+)?\s*(?:[-~至]\s*\d+(?:\.\d+)?)?\s*(?:K|千|万)(?:元)?(?:[/／](?:月|年))?|"
        r"(?:北京|上海|广州|深圳|杭州|成都)(?:市)?"
    )
    text = "\n".join(
        part.strip() for part in re.split(r"[，,。；;！!\n]", text)
        if part.strip(" \t\r\n：:") != title
        and not re.fullmatch(non_job_clause, part.strip(), re.IGNORECASE)
    )
    if not re.search(r"[\w\u4e00-\u9fff]", text):
        return False
    # 不把“广告算法”“岗前培训”等正常岗位词汇列为黑名单。
    ad_pattern = (
        r"扫码领|扫码加群|加微信咨询|限时促销|欢迎购买|培训招生|包就业|刷单返佣|招商加盟|"
        r"非招聘信息|无招聘意图|暂无招聘计划|仅供产品宣传"
    )
    if re.search(ad_pattern, text):
        # 促销句里的“参与”等动词不能反过来证明存在岗位内容。
        content = "\n".join(
            part for part in re.split(r"[，,。；;！!\n]", text)
            if not re.search(ad_pattern, part)
        )
        if not re.search(r"(?:熟悉|熟练|掌握|具备|负责|参与|承担|协助)\s*[^\W\d_]", content):
            return False
    # shortcut: 未识别的剩余文本保守放行；有人工误判样例后再收紧规则。
    return True


# ── clean() 主函数 ─────────────────────────────────────

def clean(raw: RawJD) -> dict:
    text = raw.raw_html or ""
    return {
        "source": raw.source,
        "source_detail": raw.source_detail or "",
        "job_title": raw.job_title.strip(),
        "raw_text": _strip_noise(text),
        "duties": _extract_duties(text),
        "experience": _extract_experience(text, raw.experience),
        "crawled_at": datetime.now(timezone.utc),
        "status": "cleaned",
        "identity_status": raw.identity_status or "unknown",
        "content_eligible": raw.content_eligible,
        "identity_evidence": raw.identity_evidence or "",
        "observation_key": raw.observation_key or "",
    }
