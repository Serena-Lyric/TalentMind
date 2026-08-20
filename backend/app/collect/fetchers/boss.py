"""BOSS 直聘岗位结果的纯函数归一化。"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.collect.schema import RawJD

BOSS_ORIGIN = "https://www.zhipin.com"


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _list(value) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    return [_clean(value)] if _clean(value) else []


def normalize_url(value: str) -> str:
    """只保留岗位 URL 的稳定部分，避免搜索跟踪参数导致重复。"""
    url = urljoin(BOSS_ORIGIN, value or "")
    parts = urlsplit(url)
    if not re.fullmatch(r"/job_detail/[^/]+", parts.path):
        return ""
    return urlunsplit((parts.scheme or "https", parts.netloc or "www.zhipin.com", parts.path, "", ""))


def _pick_experience(tags: list[str]) -> str:
    for tag in tags:
        if "年" in tag or tag in {"应届生", "经验不限", "在校生", "不限经验"}:
            return tag
    return ""


def _pick_degree(tags: list[str]) -> str:
    degrees = ("初中", "中专", "高中", "大专", "本科", "硕士", "博士", "学历不限")
    return next((tag for tag in tags if any(item in tag for item in degrees)), "")


def _metadata_text(raw: dict, detail: dict) -> str:
    fields = [
        ("公司", detail.get("company") or raw.get("company")),
        ("薪资", detail.get("salary") or raw.get("salary")),
        ("地点", detail.get("location") or raw.get("location")),
        ("经验", detail.get("experience") or raw.get("experience")),
        ("学历", detail.get("degree") or raw.get("degree")),
        ("公司规模", raw.get("company_scale")),
        ("公司阶段", raw.get("company_stage")),
        ("行业", raw.get("industry")),
        ("技能标签", "、".join(_list(raw.get("tags")))),
        ("福利", "、".join(_list(raw.get("welfare")))),
    ]
    return "\n".join(f"{key}: {_clean(value)}" for key, value in fields if _clean(value))


def normalize_boss_job(raw: dict, detail: dict | None = None) -> RawJD | None:
    """把列表卡片和详情页字段转换成当前 M1 的 RawJD 契约。"""
    detail = detail or {}
    url = normalize_url(str(raw.get("url") or detail.get("url") or ""))
    title = _clean(raw.get("title") or detail.get("title"))
    if not url or not title:
        return None

    tags = _list(raw.get("tags"))
    experience = _clean(detail.get("experience") or raw.get("experience") or _pick_experience(tags))
    degree = _clean(detail.get("degree") or raw.get("degree") or _pick_degree(tags))
    # 采集器会把详情字段合并回列表记录；这里同时兼容独立 detail 参数和合并后的 raw。
    detail_text = _clean(detail.get("description") or raw.get("description"))
    company_info = _clean(detail.get("company_info") or raw.get("company_info"))
    metadata = _metadata_text({**raw, "experience": experience, "degree": degree}, detail)
    chunks = [
        metadata,
        f"职位描述:\n{detail_text}" if detail_text else "",
        f"公司简介: {company_info}" if company_info else "",
    ]
    raw_text = "\n\n".join(chunk for chunk in chunks if chunk)

    return RawJD(
        source="boss",
        job_title=title[:128],
        raw_html=raw_text,
        experience=experience[:255],
        source_detail=url[:128],
    )


def merge_job(existing: dict, incoming: dict) -> dict:
    """同一 URL 多次出现时保留更完整的详情。"""
    merged = dict(existing)
    for key, value in incoming.items():
        if value and (not merged.get(key) or key in {"tags"}):
            merged[key] = value
    if incoming.get("tags"):
        merged["tags"] = list(dict.fromkeys(_list(existing.get("tags")) + _list(incoming["tags"])))
    return merged


def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for job in jobs:
        url = normalize_url(str(job.get("url") or ""))
        if not url:
            continue
        job = {**job, "url": url}
        by_url[url] = merge_job(by_url[url], job) if url in by_url else job
    return list(by_url.values())
