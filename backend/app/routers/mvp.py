"""TalentMind unified API for the full M2 catalog, graph and resume matching."""
from __future__ import annotations

import io
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, File, Form, Query, UploadFile
from fastapi.responses import Response as FastResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.db.neo4j import get_neo4j
from app.matching.canonical import to_canonical
from app.matching.matcher import quick_match_weighted
from app.matching.resume_parser import parse_resume
from app.response import BizError, ok

router = APIRouter()
JOB_SOURCES = ("boss", "zhaopin", "liepin", "linkedin", "hn")
PLATFORM_LABELS = {"boss": "BOSS", "zhaopin": "智联", "liepin": "猎聘", "linkedin": "LinkedIn", "hn": "Hacker News"}
_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESUME_MAX_BYTES = 10 * 1024 * 1024


def _parse_json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _parse_json_object(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _catalog_rows(keyword: str = "", platform: str = "", category: str = "", page: int = 1, page_size: int = 10):
    db = SessionLocal()
    try:
        like = f"%{keyword}%"
        params = {"kw": keyword, "like": like, "platform": platform, "category": category,
                  "source_like": f'%"{platform}"%', "limit": page_size,
                  "offset": (page - 1) * page_size}
        where = """
            (:kw = '' OR job_name LIKE :like OR name_en LIKE :like OR job_name_zh LIKE :like OR category LIKE :like
             OR core_duties LIKE :like OR required_skills LIKE :like OR bonus_skills LIKE :like)
            AND (:platform = '' OR source LIKE :source_like)
            AND (:category = '' OR category = :category)
        """
        rows = db.execute(text(f"""
            SELECT id, job_name, name_en, job_name_zh, category, category_review, m2_job_id,
                   core_duties, required_skills, bonus_skills, scenarios,
                   source, quality, is_emerging, evolution, first_seen, collected_at, updated_at,
                   source_jd_count
            FROM job_definition WHERE {where}
            -- 岗位目录展示排序：按 id 的确定性伪随机散列打乱，新一代/现有整体约 55 开、翻页稳定（2026-09-03 用户需求）
            ORDER BY CRC32(CONCAT('job-', CAST(id AS CHAR))), id
            LIMIT :limit OFFSET :offset
        """), params).mappings().all()
        total = db.execute(text(f"SELECT COUNT(*) FROM job_definition WHERE {where}"), params).scalar()
        return rows, int(total or 0)
    finally:
        db.close()


def _catalog_to_item(row: dict) -> dict:
    sources = [str(item) for item in _parse_json_list(row.get("source"))]
    labels = [PLATFORM_LABELS.get(source, source) for source in sources]
    required = [str(item) for item in _parse_json_list(row.get("required_skills"))]
    bonus = [str(item) for item in _parse_json_list(row.get("bonus_skills"))]
    updated = row.get("updated_at") or row.get("collected_at") or ""
    return {
        "id": str(row["id"]), "title": row.get("job_name_zh") or row.get("job_name") or "未命名岗位",
        "name_en": row.get("name_en") or row.get("job_name") or "", "job_name_zh": row.get("job_name_zh") or row.get("job_name") or "",
        "m2_job_id": row.get("m2_job_id") or "", "category": row.get("category") or "", "category_review": row.get("category_review") or "",
        "company": "", "city": "",
        "type": "/".join(labels) or "中文平台", "platform": sources[0] if len(sources) == 1 else "multi",
        "platform_label": "/".join(labels) or "中文平台", "source": sources,
        "salary": "", "experience": "", "status": "open",
        "skills": list(dict.fromkeys(required + bonus)), "required_skills": required, "bonus_skills": bonus,
        "core_duties": row.get("core_duties") or "", "scenarios": _parse_json_list(row.get("scenarios")),
        "updated": str(updated), "collected_at": str(row.get("collected_at") or ""),
        "quality": float(row.get("quality") or 0), "source_jd_count": int(row.get("source_jd_count") or 0),
        "track": "", "kind": "job", "evolution": _parse_json_object(row.get("evolution")),
    }


def _raw_pool_to_item(row: dict) -> dict:
    source = str(row.get("source") or "")
    crawled = row.get("crawled_at") or ""
    return {
        "id": str(row["id"]), "title": row.get("job_title") or "未命名岗位", "name_en": row.get("job_title") or "",
        "company": "", "city": "", "type": PLATFORM_LABELS.get(source, source), "platform": source,
        "platform_label": PLATFORM_LABELS.get(source, source), "source": [source] if source else [],
        "salary": "", "experience": row.get("experience") or "", "status": row.get("status") or "cleaned",
        "skills": [], "required_skills": [], "bonus_skills": [], "core_duties": row.get("duties") or "",
        "scenarios": [], "updated": str(crawled), "collected_at": str(crawled), "quality": float(row.get("quality") or 0),
        "source_detail": row.get("source_detail") or "", "track": "", "kind": "job",
        "evolution": {"added": [], "removed": [], "changed": []},
    }


@router.get("/jobs")
def list_jobs(keyword: str = Query(""), platform: str = Query(""), category: str = Query(""), page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    rows, total = _catalog_rows(keyword, platform, category, page, page_size)
    return ok({"list": [_catalog_to_item(dict(row)) for row in rows], "total": total, "page": page, "pageSize": page_size})


@router.get("/jobs/platform-stats")
def jobs_platform_stats():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT source, name_en, job_name, COALESCE(updated_at, collected_at) AS collected_at FROM job_definition")).mappings().all()
    finally:
        db.close()
    by_source = {source: {"count": 0, "unique_titles": set(), "latest_collected_at": None} for source in JOB_SOURCES}
    for row in rows:
        for source in _parse_json_list(row.get("source")):
            if source not in by_source:
                continue
            item = by_source[source]
            item["count"] += 1
            item["unique_titles"].add(row.get("name_en") or row.get("job_name") or "")
            latest = row.get("collected_at")
            if latest and (item["latest_collected_at"] is None or latest > item["latest_collected_at"]):
                item["latest_collected_at"] = latest
    return ok([{"platform": source, "label": PLATFORM_LABELS[source], "count": item["count"],
                "unique_titles": len(item["unique_titles"]),
                "latest_crawled_at": item["latest_collected_at"].isoformat() if hasattr(item["latest_collected_at"], "isoformat") else None}
               for source, item in by_source.items()])


@router.get("/graph/jobs")
def graph_jobs():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, job_name, source FROM job_definition ORDER BY job_name")).mappings().all()
        return ok([{"value": str(row["id"]), "label": row["job_name"], "name_en": row["job_name"], "source": _parse_json_list(row["source"])} for row in rows])
    finally:
        db.close()


@router.get("/graph/years")
def graph_years():
    return ok(["2026"])


@router.get("/graph/data")
def graph_data(year: str = "", focus_job: str = ""):
    driver = get_neo4j()
    with driver.session() as session:
        node_recs = session.run("MATCH (n) RETURN n.node_id AS node_id, n.name AS name, labels(n) AS labels, properties(n) AS props").data()
        edge_recs = session.run("MATCH (a)-[r]->(b) RETURN a.node_id AS source, b.node_id AS target, type(r) AS kind, properties(r) AS props").data()
    nodes = []
    for record in node_recs:
        node_id = record.get("node_id") or record.get("name")
        name = record.get("name") or node_id
        labels = set(record.get("labels") or [])
        props = record.get("props") or {}
        if not node_id:
            continue
        if "Job" in labels:
            sources = _parse_json_list(props.get("source"))
            nodes.append({"id": node_id, "label": props.get("name_zh") or name, "name_en": props.get("name_en") or name, "kind": "job",
                          "size": max(12, min(32, int(props.get("jd_count") or 18))), "color": "#4da6ff",
                          "status": "emerging" if props.get("is_emerging") else "stable", "jobs": int(props.get("jd_count") or 1),
                          "source": sources, "platform_label": "/".join(PLATFORM_LABELS.get(str(item), str(item)) for item in sources),
                          "category": props.get("category") or "", "is_emerging": bool(props.get("is_emerging")),
                          "evolution": _parse_json_object(props.get("evolution")), "core_duties": props.get("core_duties") or "",
                          "required_skills": _parse_json_list(props.get("required_skills")), "bonus_skills": _parse_json_list(props.get("bonus_skills")),
                          "scenarios": _parse_json_list(props.get("scenarios"))})
        elif "Skill" in labels:
            nodes.append({"id": node_id, "label": props.get("display_name") or name, "name_en": name, "kind": "skill",
                          "size": max(7, min(24, int(props.get("job_count") or 8))), "color": "#2ee66b", "status": "stable",
                          "jobs": int(props.get("job_count") or 0), "canonical_name": name})
        elif "Industry" in labels:
            nodes.append({"id": node_id, "label": props.get("display_name") or name, "name_en": name, "kind": "industry",
                          "size": max(8, min(24, int(props.get("job_count") or 4))), "color": "#c77dff", "status": "stable",
                          "jobs": int(props.get("job_count") or 0)})
    edges = [{"source": row["source"], "target": row["target"], "kind": str(row["kind"]).lower(), **(row.get("props") or {})} for row in edge_recs if row.get("source") and row.get("target")]
    return ok({"nodes": nodes, "edges": edges, "stats": {"totalNodes": len(nodes), "totalEdges": len(edges), "added": 0, "removed": 0, "changed": 0}})


def _extract_file_text(filename: str, data: bytes) -> str:
    """Extract resume text without persisting the upload."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    if name.endswith(".docx"):
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        from zipfile import ZipFile
        with ZipFile(io.BytesIO(data)) as archive:
            if sum(entry.file_size for entry in archive.infolist()) > 40 * 1024 * 1024:
                raise ValueError("DOCX 解压内容过大")
        doc = docx.Document(io.BytesIO(data))
        lines = []

        def read_body(parent):
            container = parent.element.body if isinstance(parent, docx.document.Document) else parent._tc
            seen = set()
            for child in container.iterchildren():
                if child.tag.endswith('}p'):
                    lines.append(Paragraph(child, parent).text)
                elif child.tag.endswith('}tbl'):
                    for row in Table(child, parent).rows:
                        for cell in row.cells:
                            if cell._tc not in seen:
                                seen.add(cell._tc)
                                read_body(cell)

        read_body(doc)
        return "\n".join(lines)
    if name.endswith(".doc"):
        raise ValueError("旧版 DOC 请先另存为 DOCX 或 PDF")
    if not name.endswith(".txt"):
        raise ValueError("仅支持 PDF、DOCX、TXT")
    content = data.decode("utf-8-sig")
    if any(ord(c) < 32 and c not in '\t\n\r' for c in content):
        raise ValueError("文本文件包含二进制控制字符")
    return content


def _resume_skills(content: str) -> list[str]:
    from app.matching.skill_extractor import extract_skills
    parsed = parse_resume(content) or {}
    source = parsed.get("skills") or extract_skills(content)
    return list(dict.fromkeys(to_canonical(str(skill)) for skill in source if str(skill).strip()))


@router.post("/resume/upload")
async def resume_upload(file: UploadFile | None = File(None), content: str = Form(""), target_job_id: str = Form("")):
    raw = await file.read(_RESUME_MAX_BYTES + 1) if file is not None else None
    filename = (file.filename or "") if file is not None else ""
    return await run_in_threadpool(_process_resume_upload, filename, raw, content, target_job_id)


def _process_resume_upload(filename: str, raw: bytes | None, content: str, target_job_id: str):
    # Parsing, matching and the complete SQL session stay in the same worker.
    if raw is not None:
        if len(raw) > _RESUME_MAX_BYTES:
            raise BizError(4002, "文件超过 10MB 上限")
        if Path(filename).suffix.lower() == '.doc':
            raise BizError(4002, "旧版 DOC 请先另存为 DOCX 或 PDF")
        if Path(filename).suffix.lower() not in {'.pdf', '.docx', '.txt'}:
            raise BizError(4002, "仅支持 PDF、DOCX、TXT 文件")
        try:
            content = (content + "\n" + _extract_file_text(filename, raw)).strip()
        except Exception as exc:
            raise BizError(4002, "文件解析失败，请使用可读取的 PDF、DOCX 或 UTF-8 文本") from exc
    if len(content.encode('utf-8')) > _RESUME_MAX_BYTES:
        raise BizError(4002, "简历内容超过 10MB 上限")
    if not content.strip():
        raise BizError(4001, "未提取到简历文字；扫描件请先转为可复制文字的文件")
    parsed = parse_resume(content) or {}
    info = parsed.get("personal_info", {}) or {}
    resume_skills = list(dict.fromkeys(to_canonical(s) for s in parsed.get('skills', [])))
    edu_list = parsed.get("education") or []
    works = parsed.get("work_experience") or []
    degree_order = {'博士': 5, '硕士': 4, '本科': 3, '大专': 2, '高中': 1}
    first_edu = max(edu_list, key=lambda e: degree_order.get(e.get('degree'), 0), default={})
    def work_recency(work: dict) -> tuple:
        def year_month(value: str) -> tuple[int, int]:
            parts = re.fullmatch(r'(\d{4})[./](\d{1,2})', value or '')
            return (int(parts[1]), int(parts[2])) if parts else (0, 0)
        return (work.get('end_date') == '至今', year_month(work.get('end_date', '')),
                year_month(work.get('start_date', '')))

    latest_work = max(works, key=work_recency, default={})
    exp_years = info.get("experience_years")

    def _text(value: Any) -> str:
        return str(value or "").strip()

    education_text = " · ".join(part for part in (_text(first_edu.get("school")), _text(first_edu.get("major")), _text(first_edu.get("degree"))) if part)
    if not education_text:
        education_text = _text(info.get("education"))
    education_period = " - ".join(part for part in (_text(first_edu.get("start_date")), _text(first_edu.get("end_date"))) if part)
    role = _text(info.get("role")) or _text(latest_work.get("position"))
    company = _text(latest_work.get("company"))

    # 预览用：项目经历 / 竞赛与荣誉 / 自我评价（来自解析器，无内容则为空）
    projects = []
    for _pr in (parsed.get("project_experience") or []):
        _pname = _text(_pr.get("name"))
        _desc = [_text(x) for x in (_pr.get("description") or []) if _text(x)]
        if _pname or _desc:
            projects.append({"name": _pname or "项目实践", "duration": _text(_pr.get("time")), "tech_stack": "", "responsibilities": _desc})
    honors = [{"time": _text(_h.get("time")), "title": _text(_h.get("title"))} for _h in (parsed.get("honors") or []) if _text(_h.get("title"))]
    self_evaluation = _text(parsed.get("self_evaluation"))
    profile = {
        "name": _text(info.get("name")),
        "role": role,
        "experience": "应届" if info.get("is_fresh_graduate") else (f"{exp_years} 年" if isinstance(exp_years, int) else ""),
        "education": education_text,
        "company": company,
        "skills": resume_skills,
        "summary": "",
        "projects": projects,
        "honors": honors,
        "self_evaluation": self_evaluation,
        "education_history": edu_list,
        "work_experience": works,
        "phone": _text(info.get("phone")), "email": _text(info.get("email")),
        "location": _text(info.get("location")), "gender": _text(info.get("gender")),
        "age": info.get("age"),
        "education_school": _text(first_edu.get("school")),
        "education_major": _text(first_edu.get("major")),
        "education_degree": _text(first_edu.get("degree")),
        "education_period": education_period,
        "experience_years": exp_years if isinstance(exp_years, int) else "",
    }
    db = SessionLocal()
    try:
        # 自动匹配遍历完整 M2 岗位目录；target_job_id 仅保留接口兼容，不影响推荐列表。
        rows = db.execute(text("""
            SELECT id, job_name, name_en, job_name_zh, category, required_skills, bonus_skills,
                   source, quality, collected_at, source_jd_count
            FROM job_definition ORDER BY id LIMIT 6000
        """)).mappings().all()
    finally:
        db.close()
    candidates = []
    seen_ids: set[str] = set()
    for row in rows:
        title = str(row.get("job_name") or "未命名岗位")
        if str(row["id"]) in seen_ids:
            continue
        required = list(dict.fromkeys(to_canonical(item) for item in _parse_json_list(row.get("required_skills")) if isinstance(item, str) and item.strip()))
        bonus = list(dict.fromkeys(to_canonical(item) for item in _parse_json_list(row.get("bonus_skills")) if isinstance(item, str) and item.strip() and to_canonical(item) not in required))
        job_skills = list(dict.fromkeys(required + bonus))
        result = quick_match_weighted(resume_skills, required, bonus)
        sources = _parse_json_list(row.get("source"))
        raw_score = round(float(result.get("total_score", 0) or 0))
        candidates.append({"id": str(row["id"]), "title": row.get("job_name_zh") or title, "name_en": row.get("name_en") or title,
                           "category": row.get("category") or "", "platform": sources[0] if len(sources) == 1 else "multi",
                           "platform_label": "/".join(PLATFORM_LABELS.get(str(source), str(source)) for source in sources),
                           "score": raw_score, "raw_score": raw_score, "display_score": raw_score,
                           "matched": result.get("matched_skills", []),
                           "missing": [{"name": skill, "level": "high" if skill in required else "medium", "tip": "简历未提及，请先核实实际经历，再决定是否学习或补充说明"} for skill in result.get("unmatched_job_skills", [])],
                           "skills": job_skills, "collected_at": str(row.get("collected_at") or ""),
                           "source_jd_count": int(row.get("source_jd_count") or 0)})
        seen_ids.add(str(row["id"]))
    candidates.sort(key=lambda item: (-item["score"], item["title"]))
    threshold_candidates = [item for item in candidates if item["raw_score"] >= 90]
    recommended = (threshold_candidates[:3] if len(threshold_candidates) >= 3 else candidates[:3])
    # 兼容旧响应字段，展示分始终使用实际规则计算分。
    for item in recommended:
        item["is_score_floor"] = False
        item["display_randomized"] = False
    # 新前端不传 target_job_id；旧客户端传入时仍返回对应主诊断，推荐列表保持自动计算。
    target_candidate = next((item for item in candidates if item["id"] == target_job_id.strip()), None) if target_job_id.strip() else None
    best = target_candidate or (recommended[0] if recommended else None)
    match_result = {"score": best["display_score"] if best else 0, "raw_score": best["raw_score"] if best else 0,
                    "is_score_floor": False,
                    "display_randomized": False, "matched": best["matched"] if best else [],
                    "missing": best["missing"] if best else [], "strengths": resume_skills,
                    "target_job": best["title"] if best else "", "target_job_en": best.get("name_en", "") if best else "",
                    "target_job_id": best["id"] if best else "", "platform": best["platform"] if best else ""}
    coverage = [bool(profile['name']), bool(profile['phone'] or profile['email']), bool(edu_list), bool(works or projects), bool(resume_skills)]
    return ok({"profile": profile, "matchResult": match_result, "recommendedJobs": recommended,
               "parseQuality": round(sum(coverage) / len(coverage) * 100), "parseQualityBasis": "field_coverage", "recommendationThreshold": 90,
               "thresholdCandidates": len(threshold_candidates), "recommendationFloorApplied": any(item.get("display_randomized") for item in recommended)})


@router.get("/resume/target-jobs")
def resume_target_jobs():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, job_name, name_en, job_name_zh, category, source FROM job_definition ORDER BY job_name LIMIT 6000")).mappings().all()
        return ok([{"value": str(row["id"]), "label": row.get("job_name_zh") or row["job_name"], "name_en": row.get("name_en") or row["job_name"], "category": row.get("category") or "", "score": 0, "source": _parse_json_list(row["source"])} for row in rows])
    finally:
        db.close()


@router.get("/resume/skill-dimensions")
def resume_skill_dimensions(target_job: str = Query("")):
    db = SessionLocal()
    try:
        row = db.execute(text("SELECT required_skills, bonus_skills FROM job_definition WHERE id=:id"), {"id": target_job}).first()
    finally:
        db.close()
    if not row:
        return ok({"dimensions": [], "jobStandard": [], "personalAbility": []})
    from app.matching.skill_extractor import get_skill_category
    required = _parse_json_list(row[0]); all_skills = required + _parse_json_list(row[1])
    categories = list(dict.fromkeys(get_skill_category(str(skill)) for skill in all_skills))[:8]
    personal = [round(sum(1 for skill in required if get_skill_category(str(skill)) == category) / max(1, sum(1 for skill in all_skills if get_skill_category(str(skill)) == category)) * 100) for category in categories]
    return ok({"dimensions": categories, "jobStandard": [100] * len(categories), "personalAbility": personal})


class JobPayload(BaseModel):
    job_name: str
    core_duties: str = ""
    required_skills: list = []
    bonus_skills: list = []
    scenarios: list = []
    source: list = []
    quality: float = 0.0
    is_emerging: bool = False
    evolution: dict = {}
    first_seen: str = ""
    collected_at: str = ""
    updated_at: str = ""


@router.get("/jobs/export")
def export_jobs():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT job_name, core_duties, required_skills, bonus_skills, source, collected_at, updated_at FROM job_definition ORDER BY id")).mappings().all()
    finally:
        db.close()
    import csv
    buf = io.StringIO(); writer = csv.writer(buf)
    writer.writerow(["job_name", "core_duties", "required_skills", "bonus_skills", "source", "collected_at", "updated_at"])
    for row in rows:
        writer.writerow([row["job_name"], row["core_duties"] or "", json.dumps(_parse_json_list(row["required_skills"]), ensure_ascii=False), json.dumps(_parse_json_list(row["bonus_skills"]), ensure_ascii=False), json.dumps(_parse_json_list(row["source"]), ensure_ascii=False), row["collected_at"] or "", row["updated_at"] or ""])
    return FastResponse(content="\ufeff" + buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=chinese-platform-jobs.csv"})


@router.get("/jobs/{job_id}")
def job_detail(job_id: int):
    db = SessionLocal()
    try:
        row = db.execute(text("""SELECT id, job_name, name_en, job_name_zh, m2_job_id, category, category_review,
                               required_skills, bonus_skills, core_duties, scenarios, source, quality,
                               is_emerging, evolution, source_jd_count, collected_at, updated_at
                               FROM job_definition WHERE id=:id"""), {"id": job_id}).mappings().first()
        if row:
            item = _catalog_to_item(dict(row)); item["responsibilities"] = [line.strip() for line in str(row.get("core_duties") or "").splitlines() if line.strip()]; item["requirements"] = []; item["job_name"] = str(row.get("job_name") or ""); return ok(item)
        row = db.execute(text("SELECT id, source, source_detail, job_title, raw_text, duties, experience, quality, crawled_at, status FROM jd_pool WHERE id=:id AND source IN ('boss','zhaopin','liepin')"), {"id": job_id}).mappings().first()
        if not row: raise BizError(4041, "岗位不存在")
        item = _raw_pool_to_item(dict(row)); item["responsibilities"] = [line.strip() for line in str(row.get("duties") or "").splitlines() if line.strip()]; item["requirements"] = [str(row.get("experience") or "").strip()] if row.get("experience") else []; item["raw_text"] = row.get("raw_text") or ""; return ok(item)
    finally:
        db.close()


@router.post("/jobs")
def create_job(payload: JobPayload):
    if not payload.job_name.strip(): raise BizError(4001, "job_name 不能为空")
    db = SessionLocal()
    try:
        result = db.execute(text("""INSERT INTO job_definition (job_name, core_duties, required_skills, bonus_skills, scenarios, source, quality, is_emerging, evolution, collected_at, updated_at) VALUES (:job_name, :core_duties, :required_skills, :bonus_skills, :scenarios, :source, :quality, :is_emerging, :evolution, :collected_at, :updated_at)"""), {"job_name": payload.job_name.strip(), "core_duties": payload.core_duties, "required_skills": json.dumps(payload.required_skills, ensure_ascii=False), "bonus_skills": json.dumps(payload.bonus_skills, ensure_ascii=False), "scenarios": json.dumps(payload.scenarios, ensure_ascii=False), "source": json.dumps(payload.source, ensure_ascii=False), "quality": payload.quality, "is_emerging": int(payload.is_emerging), "evolution": json.dumps(payload.evolution, ensure_ascii=False), "collected_at": payload.collected_at or None, "updated_at": payload.updated_at or None})
        new_id = result.lastrowid
        db.commit()
        return ok({"id": str(new_id)})
    except Exception: db.rollback(); raise
    finally: db.close()


@router.put("/jobs/{job_id}")
def update_job(job_id: int, payload: JobPayload):
    if not payload.job_name.strip(): raise BizError(4001, "job_name 不能为空")
    db = SessionLocal()
    try:
        cur=db.execute(text("""UPDATE job_definition SET job_name=:job_name, core_duties=:core_duties, required_skills=:required_skills, bonus_skills=:bonus_skills, scenarios=:scenarios, source=:source, quality=:quality, is_emerging=:is_emerging, evolution=:evolution, collected_at=:collected_at, updated_at=:updated_at WHERE id=:id"""), {"id":job_id,"job_name":payload.job_name.strip(),"core_duties":payload.core_duties,"required_skills":json.dumps(payload.required_skills,ensure_ascii=False),"bonus_skills":json.dumps(payload.bonus_skills,ensure_ascii=False),"scenarios":json.dumps(payload.scenarios,ensure_ascii=False),"source":json.dumps(payload.source,ensure_ascii=False),"quality":payload.quality,"is_emerging":int(payload.is_emerging),"evolution":json.dumps(payload.evolution,ensure_ascii=False),"collected_at":payload.collected_at or None,"updated_at":payload.updated_at or None}); db.commit();
        if cur.rowcount==0: raise BizError(4041,"岗位不存在")
        return ok({"success":True})
    except Exception: db.rollback(); raise
    finally: db.close()


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int):
    db=SessionLocal()
    try:
        cur=db.execute(text("DELETE FROM job_definition WHERE id=:id"),{"id":job_id}); db.commit()
        if cur.rowcount==0: raise BizError(4041,"岗位不存在")
        return ok({"success":True})
    except Exception: db.rollback(); raise
    finally: db.close()


@router.post("/jobs/batch-delete")
def batch_delete_jobs(ids: list[int] = Body(...)):
    if not ids: raise BizError(4001,"ids 不能为空")
    db=SessionLocal()
    try:
        for job_id in ids: db.execute(text("DELETE FROM job_definition WHERE id=:id"),{"id":job_id})
        db.commit(); return ok({"deleted":len(ids)})
    except Exception: db.rollback(); raise
    finally: db.close()


@router.post("/jobs/import")
async def import_jobs(file: UploadFile = File(...)):
    raw = await file.read()
    return await run_in_threadpool(_import_jobs, raw, file.filename or "")


def _import_jobs(raw: bytes, filename: str):
    import csv
    try:
        content = raw.decode("utf-8-sig")
        is_json = filename.lower().endswith(".json") or content.lstrip().startswith("[")
        if is_json:
            rows = json.loads(content)
            if not isinstance(rows, list):
                raise ValueError("JSON 顶层必须为数组")
        else:
            reader = csv.DictReader(io.StringIO(content), strict=True)
            if not reader.fieldnames or not {"job_name", "title"}.intersection(reader.fieldnames):
                raise ValueError("CSV 缺少 job_name 或 title 列")
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("CSV 存在重复列名")
            rows = list(reader)
        payloads = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict) or None in row:
                raise ValueError(f"第 {index} 行结构无效")
            item = dict(row)
            item["job_name"] = item.get("job_name") or item.get("title") or ""
            for field in ("required_skills", "bonus_skills", "scenarios", "source"):
                value = item.get(field)
                if value is None or value == "":
                    value = []
                elif not is_json and isinstance(value, str):
                    value = json.loads(value) if value.lstrip().startswith("[") else [part.strip() for part in re.split(r"[;|]", value) if part.strip()]
                if not isinstance(value, list) or any(not isinstance(part, str) for part in value):
                    raise ValueError(f"第 {index} 行 {field} 必须为字符串列表")
                item[field] = value
            for field in ("core_duties", "collected_at", "updated_at", "first_seen"):
                if item.get(field) is None:
                    item[field] = ""
            for field, default in (("quality", 0), ("is_emerging", False), ("evolution", {})):
                if item.get(field) is None or item.get(field) == "":
                    item[field] = default
            if not is_json and isinstance(item["evolution"], str):
                item["evolution"] = json.loads(item["evolution"])
            payload = JobPayload(**item)
            payload.job_name = payload.job_name.strip()
            if not payload.job_name or len(payload.job_name) > 128:
                raise ValueError(f"第 {index} 行 job_name 必须为 1–128 个字符")
            if not math.isfinite(payload.quality) or abs(payload.quality) > 3.4028234663852886e38:
                raise ValueError(f"第 {index} 行 quality 超出 FLOAT 范围")
            if len(payload.core_duties.encode("utf-8")) > 65535:
                raise ValueError(f"第 {index} 行 core_duties 超出 TEXT 字节上限")
            # MySQL JSON rejects non-finite numbers, including nested overflow from 1e999.
            json.dumps(payload.model_dump(), ensure_ascii=False, allow_nan=False).encode("utf-8")
            for field in ("collected_at", "updated_at", "first_seen"):
                value = getattr(payload, field)
                if value:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)?", value):
                        raise ValueError(f"第 {index} 行 {field} 必须为不带时区的日期时间")
                    parsed = datetime.fromisoformat(value)
                    if parsed.year < 1000:
                        raise ValueError(f"第 {index} 行 {field} 超出 DATETIME 范围")
                    setattr(payload, field, parsed.isoformat(sep=" "))
            payloads.append(payload)
    except (ValueError, TypeError, csv.Error) as exc:
        raise BizError(4001, "导入文件格式或字段无效，请检查 UTF-8 编码、岗位名称、列表及日期") from exc
    # Preserve per-row commits; validate the whole file before any database write.
    for payload in payloads:
        create_job(payload)
    return ok({"imported": len(payloads)})


@router.get("/graph/skill-radar")
def graph_skill_radar(node_name: str = Query("")):
    return ok({"dimensions": [], "values": []})
