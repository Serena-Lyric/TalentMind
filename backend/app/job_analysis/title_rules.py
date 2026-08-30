"""L2 前置硬规则 —— 标题/职业强判定（本地、零 LLM）。

新一代信息技术筛选的守门员：标题明确是强非技术职业的直接拒绝，
不依赖 LLM 语义判断（防长文本截断导致误放行）。
"""
import re

# 强非技术职业词（标题命中即拒）——医疗/护理/法务/教育/零售/餐饮/建筑等
_STRONG_NONTECH = re.compile(
    r"\b(nurse|registered nurse|rn\b|physician|doctor\b|therapist|"
    r"counselor|psychologist|pharmacist|dentist|veterinar|"
    r"teacher|professor|instructor|tutor|principal\b|"
    r"lawyer|attorney|paralegal|legal assistant|"
    r"cashier|server\b|bartender|barista|cook\b|chef\b|host\b|hostess|"
    r"waitress|waiter|housekeeper|cleaner\b|janitor|"
    r"driver\b|trucker|delivery|warehouse|forklift|"
    r"accountant|bookkeeper|auditor\b|teller\b|loan officer|"
    r"realtor|real estate|insurance agent|"
    r"sales associate|store manager|retail|merchandis|"
    r"护士|医生|医师|教师|老师|教授|律师|会计|出纳|收银|服务员|"
    r"保洁|保安|司机|销售|店长|仓库|厨师)\b",
    re.I)

# 强技术职业词（标题命中即强放行，防 LLM 误杀）
_STRONG_TECH = re.compile(
    r"\b(software|backend|frontend|fullstack|full-stack|devops|sre\b|"
    r"data engineer|data scientist|machine learning|ml engineer|"
    r"ai engineer|cloud|cybersecurity|security engineer|"
    r"embedded|firmware|mobile developer|ios|android|"
    r"qa engineer|test automation|platform engineer|site reliability|"
    r"工程师|开发|程序员|算法|运维|架构|数据分析|测试)\b",
    re.I)


def title_verdict(job_title: str) -> str | None:
    """标题硬判定。返回 'reject' / 'pass' / None（无法判定）。"""
    if not job_title:
        return None
    if _STRONG_NONTECH.search(job_title):
        return "reject"
    if _STRONG_TECH.search(job_title):
        return "pass"
    return None
