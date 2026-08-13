"""MVP 统一 API（A 集成层，阶段 6）。

实现最小闭环：岗位列表（MySQL job_definition）、图谱数据（Neo4j）、简历上传/匹配（M4 matching）。
统一响应 {code:0, message, data}（D29），字段 snake_case。
"""
import json

from fastapi import APIRouter, File, Form, Query, UploadFile
from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.db.neo4j import get_neo4j
from app.matching.matcher import quick_match
from app.matching.resume_parser import parse_resume
from app.response import BizError, ok

router = APIRouter()  # 前缀 /api 由 main.py include_router 指定


def _job_rows(keyword: str = "", page: int = 1, page_size: int = 10) -> tuple[list, int]:
    db = SessionLocal()
    try:
        like = f"%{keyword}%"
        rows = db.execute(
            text("""
                SELECT id, job_name, core_duties, required_skills, bonus_skills,
                       scenarios, source, quality, is_emerging,
                       collected_at, updated_at
                FROM job_definition
                WHERE (:kw = '' OR job_name LIKE :like)
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """),
            {"kw": keyword, "like": like,
             "limit": page_size, "offset": (page - 1) * page_size},
        ).mappings().all()
        total = db.execute(
            text("SELECT COUNT(*) AS c FROM job_definition "
                 "WHERE (:kw = '' OR job_name LIKE :like)"),
            {"kw": keyword, "like": like},
        ).scalar()
        return rows, int(total or 0)
    finally:
        db.close()


def _parse_json_list(value) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []


@router.get("/jobs")
def list_jobs(
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    rows, total = _job_rows(keyword, page, page_size)
    items = []
    for r in rows:
        skills = _parse_json_list(r["required_skills"]) + _parse_json_list(r["bonus_skills"])
        items.append({
            "id": str(r["id"]),
            "title": r["job_name"],
            "company": "",
            "city": "",
            "type": "",
            "salary": "",
            "status": "open",  # D34：招聘状态（展示层）
            "skills": skills,
            "updated": str(r["updated_at"] or r["collected_at"] or ""),
            "track": "",
            "kind": "job",
        })
    return ok({"list": items, "total": total, "page": page, "pageSize": page_size})


@router.get("/graph/jobs")
def graph_jobs():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, job_name FROM job_definition ORDER BY id")).all()
        return ok([{"value": str(r[0]), "label": r[1]} for r in rows])
    finally:
        db.close()


@router.get("/graph/years")
def graph_years():
    # MVP：无时间序列对比，仅当前年份
    return ok(["2026"])


@router.get("/graph/data")
def graph_data(year: str = "", focus_job: str = ""):
    driver = get_neo4j()
    with driver.session() as s:
        node_recs = s.run(
            "MATCH (n) RETURN n.name AS name, labels(n) AS ls"
        ).data()
        edge_recs = s.run(
            "MATCH (a)-[r]->(b) RETURN a.name AS s, b.name AS t, type(r) AS k"
        ).data()

    nodes = []
    for rec in node_recs:
        name = rec.get("name")
        ls = set(rec.get("ls") or [])
        if not name:
            continue
        if "Job" in ls:
            nodes.append({
                "id": name, "label": name, "kind": "job",
                "size": 30, "color": "#D98B6E", "status": "stable",
                "jobs": 1,
            })
        elif "Skill" in ls:
            nodes.append({
                "id": name, "label": name, "kind": "skill",
                "size": 20, "color": "#8CA0B8", "status": "stable",
            })

    edges = [{"source": e["s"], "target": e["t"], "kind": e["k"].lower()}
             for e in edge_recs if e.get("s") and e.get("t")]

    return ok({
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "totalNodes": len(nodes),
            "totalEdges": len(edges),
            "added": 0, "removed": 0, "changed": 0,
        },
    })


@router.post("/resume/upload")
async def resume_upload(
    file: UploadFile | None = File(None),
    content: str = Form(""),
):
    if file is not None:
        raw = (await file.read()).decode("utf-8", errors="replace")
        content = (content + "\n" + raw).strip()
    if not content.strip():
        raise BizError(4001, "简历内容为空")

    parsed = parse_resume(content) or {}
    info = parsed.get("personal_info", {}) or {}
    skills = parsed.get("skills", []) or []
    # 技能 canonical 化（D31）
    from app.matching.canonical import to_canonical
    skills = [to_canonical(s) for s in skills]

    profile = {
        "name": info.get("name", ""),
        "role": info.get("role", ""),
        "experience": str(info.get("experience_years", "") or ""),
        "education": str(info.get("education", "") or ""),
        "company": "",
        "skills": skills,
        "summary": "",
    }

    # 与库内岗位匹配，取最高分
    db = SessionLocal()
    try:
        rows = db.execute(
            text("SELECT job_name, required_skills, bonus_skills FROM job_definition")
        ).all()
    finally:
        db.close()

    best = None
    for r in rows:
        job_skills = _parse_json_list(r[1]) + _parse_json_list(r[2])
        if not job_skills:
            continue
        result = quick_match(skills, job_skills)
        score = result.get("total_score", 0)
        if best is None or score > best[0]:
            best = (score, r[0], result)

    if best is None:
        match_result = {
            "score": 0, "matched": [], "missing": [], "strengths": [],
        }
    else:
        score, job_name, result = best
        match_result = {
            "score": round(score),
            "matched": result.get("matched_skills", []),
            "missing": [
                {"name": m, "level": "medium", "tip": ""}
                for m in result.get("unmatched_job_skills", [])
            ],
            "strengths": result.get("resume_extra_skills", []),
            "target_job": job_name,
        }

    return ok({"profile": profile, "matchResult": match_result})


@router.get("/resume/target-jobs")
def resume_target_jobs():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, job_name FROM job_definition ORDER BY id")).all()
        return ok([{"value": str(r[0]), "label": r[1], "score": 0} for r in rows])
    finally:
        db.close()


@router.get("/resume/skill-dimensions")
def resume_skill_dimensions(target_job: str = Query("")):
    # MVP：无维度画像数据，返回空结构（前端按空处理）
    return ok({"dimensions": [], "jobStandard": [], "personalAbility": []})