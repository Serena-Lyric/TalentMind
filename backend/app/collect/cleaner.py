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
    r"^What\s+You'?ll\s+Do:?\s*$|"
    r"^Role\s*:?\s*$"
)

# 职责段结束标志：下一个标题行（全大写或常见标题）
SECTION_BOUNDARY_PATTERN = re.compile(
    r"(?im)^(?:Qualifications?|Requirements?|Education|Experience|Skills?|"
    r"About\s+(?:Us|the\s+Company)|Benefits?|Compensation|"
    r"We\s+(?:Are|Offer|Value)|How\s+to\s+Apply|"
    r"Equal\s+Opportunity|Our\s+Company)\s*:?"
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
    }
