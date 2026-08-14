"""MVP 统一 API（A 集成层，阶段 6）。

实现最小闭环：岗位列表（MySQL job_definition）、图谱数据（Neo4j）、简历上传/匹配（M4 matching）。
统一响应 {code:0, message, data}（D29），字段 snake_case。
"""
import json
from pathlib import Path

import io

from fastapi import APIRouter, Body, File, Form, Query, UploadFile
from fastapi.responses import Response as FastResponse
from pydantic import BaseModel
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


# ── 中英文展示过渡（2026-08-14，短期方案） ──
# 契约 key = 英文 job_name；展示名取 job_definition_zh.json（与 en 同序，translate 保序）。
# 长期：M2 输出 job_name_zh 字段后，此映射改为读该字段（见修正方案第三节）。
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ZH_MAP: dict[str, str] | None = None


def _load_zh_map() -> dict[str, str]:
    global _ZH_MAP
    if _ZH_MAP is None:
        m: dict[str, str] = {}
        path = _REPO_ROOT / "exchange" / "m2" / "job_definition_zh.json"
        en_path = _REPO_ROOT / "exchange" / "m2" / "job_definition.json"
        try:
            en_list = json.loads(en_path.read_text(encoding="utf-8"))
            zh_list = json.loads(path.read_text(encoding="utf-8"))
            for e, z in zip(en_list, zh_list):
                m[e.get("job_name", "")] = z.get("job_name", "") or e.get("job_name", "")
        except Exception:
            m = {}
        _ZH_MAP = m
    return _ZH_MAP


def _display_title(en_name: str) -> str:
    """英文 key → 中文展示名（找不到回退英文）。"""
    return _load_zh_map().get(en_name, en_name)


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
            "title": _display_title(r["job_name"]),
            "name_en": r["job_name"],
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
        return ok([{"value": str(r[0]), "label": _display_title(r[1]), "name_en": r[1]} for r in rows])
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
                "id": name, "label": _display_title(name), "name_en": name,
                "kind": "job",
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



def _extract_file_text(filename: str, data: bytes) -> str:
    """按扩展名解析简历文件（PDF/DOCX/DOC/TXT），返回文本。"""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    if name.endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(data))
        return "\n".join(para.text for para in doc.paragraphs)
    if name.endswith(".doc"):
        import mammoth
        result = mammoth.extract_raw_text(io.BytesIO(data))
        return result.value
    # txt / json / 其他按文本
    return data.decode("utf-8", errors="replace")


@router.post("/resume/upload")
async def resume_upload(
    file: UploadFile | None = File(None),
    content: str = Form(""),
):
    if file is not None:
        raw = await file.read()
        try:
            parsed_text = _extract_file_text(file.filename or "", raw)
        except Exception as exc:
            raise BizError(4002, f"文件解析失败: {exc}") from exc
        content = (content + "\n" + parsed_text).strip()
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
            "target_job": _display_title(job_name),
            "target_job_en": job_name,
        }

    return ok({"profile": profile, "matchResult": match_result})


@router.get("/resume/target-jobs")
def resume_target_jobs():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, job_name FROM job_definition ORDER BY id")).all()
        return ok([{"value": str(r[0]), "label": _display_title(r[1]), "name_en": r[1], "score": 0} for r in rows])
    finally:
        db.close()


@router.get("/resume/skill-dimensions")
def resume_skill_dimensions(target_job: str = Query("")):
    # MVP：无维度画像数据，返回空结构（前端按空处理）
    return ok({"dimensions": [], "jobStandard": [], "personalAbility": []})

# ==================== 岗位 CRUD / 导入导出 / 图谱雷达（MVP 补全） ====================

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


def _job_definition_to_item(r) -> dict:
    return {
        "id": str(r[0]),
        "title": r[1],
        "company": "",
        "city": "",
        "type": "",
        "salary": "",
        "status": "open",
        "skills": _parse_json_list(r[2]) + _parse_json_list(r[3]),
        "updated": str(r[7] or r[6] or ""),
        "track": "",
        "kind": "job",
    }


@router.get("/jobs/export")
def export_jobs():
    """导出岗位为 CSV（文件流，不走统一响应体）。"""
    db = SessionLocal()
    try:
        rows = db.execute(
            text("SELECT job_name, core_duties, required_skills, bonus_skills "
                 "FROM job_definition ORDER BY id")
        ).all()
    finally:
        db.close()
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(["job_name", "core_duties", "required_skills", "bonus_skills"])
    for r in rows:
        writer.writerow([
            r[0],
            r[1] or "",
            " | ".join(_parse_json_list(r[2])),
            " | ".join(_parse_json_list(r[3])),
        ])
    csv_text = "﻿" + buf.getvalue()  # BOM 兼容 Excel
    return FastResponse(content=csv_text, media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=jobs.csv"})




@router.get("/jobs/{job_id}")
def job_detail(job_id: int):
    db = SessionLocal()
    try:
        r = db.execute(
            text("SELECT id, job_name, required_skills, bonus_skills, core_duties, "
                 "scenarios, collected_at, updated_at FROM job_definition WHERE id = :i"),
            {"i": job_id},
        ).first()
        if not r:
            raise BizError(4041, "岗位不存在")
        return ok({
            "id": str(r[0]), "title": _display_title(r[1]), "name_en": r[1],
            "skills": _parse_json_list(r[2]) + _parse_json_list(r[3]),
            "responsibilities": [r[4]] if r[4] else [],
            "scenarios": _parse_json_list(r[5]),
            "updated": str(r[7] or r[6] or ""),
            "status": "open",
        })
    finally:
        db.close()


@router.post("/jobs")
def create_job(payload: JobPayload):
    if not payload.job_name.strip():
        raise BizError(4001, "job_name 不能为空")
    db = SessionLocal()
    try:
        db.execute(
            text("INSERT INTO job_definition "
                 "(job_name, core_duties, required_skills, bonus_skills, scenarios, "
                 " source, quality, is_emerging, evolution, collected_at, updated_at) "
                 "VALUES (:job_name, :core_duties, :required_skills, :bonus_skills, :scenarios, "
                 " :source, :quality, :is_emerging, :evolution, :collected_at, :updated_at)"),
            {
                "job_name": payload.job_name.strip(),
                "core_duties": payload.core_duties,
                "required_skills": json.dumps(payload.required_skills, ensure_ascii=False),
                "bonus_skills": json.dumps(payload.bonus_skills, ensure_ascii=False),
                "scenarios": json.dumps(payload.scenarios, ensure_ascii=False),
                "source": json.dumps(payload.source, ensure_ascii=False),
                "quality": payload.quality,
                "is_emerging": int(payload.is_emerging),
                "evolution": json.dumps(payload.evolution, ensure_ascii=False),
                "collected_at": payload.collected_at or None,
                "updated_at": payload.updated_at or None,
            },
        )
        db.commit()
        new_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        return ok({"id": str(new_id)})
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.put("/jobs/{job_id}")
def update_job(job_id: int, payload: JobPayload):
    if not payload.job_name.strip():
        raise BizError(4001, "job_name 不能为空")
    db = SessionLocal()
    try:
        cur = db.execute(
            text("UPDATE job_definition SET job_name=:job_name, core_duties=:core_duties, "
                 "required_skills=:required_skills, bonus_skills=:bonus_skills, "
                 "scenarios=:scenarios, source=:source, quality=:quality, "
                 "is_emerging=:is_emerging, evolution=:evolution, "
                 "collected_at=:collected_at, updated_at=:updated_at WHERE id=:i"),
            {
                "i": job_id,
                "job_name": payload.job_name.strip(),
                "core_duties": payload.core_duties,
                "required_skills": json.dumps(payload.required_skills, ensure_ascii=False),
                "bonus_skills": json.dumps(payload.bonus_skills, ensure_ascii=False),
                "scenarios": json.dumps(payload.scenarios, ensure_ascii=False),
                "source": json.dumps(payload.source, ensure_ascii=False),
                "quality": payload.quality,
                "is_emerging": int(payload.is_emerging),
                "evolution": json.dumps(payload.evolution, ensure_ascii=False),
                "collected_at": payload.collected_at or None,
                "updated_at": payload.updated_at or None,
            },
        )
        db.commit()
        if cur.rowcount == 0:
            raise BizError(4041, "岗位不存在")
        return ok({"success": True})
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int):
    db = SessionLocal()
    try:
        cur = db.execute(text("DELETE FROM job_definition WHERE id = :i"), {"i": job_id})
        db.commit()
        if cur.rowcount == 0:
            raise BizError(4041, "岗位不存在")
        return ok({"success": True})
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/jobs/batch-delete")
def batch_delete_jobs(ids: list[int] = Body(...)):
    if not ids:
        raise BizError(4001, "ids 不能为空")
    db = SessionLocal()
    try:
        for i in ids:
            db.execute(text("DELETE FROM job_definition WHERE id = :i"), {"i": i})
        db.commit()
        return ok({"deleted": len(ids)})
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/jobs/import")
async def import_jobs(file: UploadFile = File(...)):
    """批量导入岗位：支持 JSON 数组（job_definition 结构）或 CSV（首行标题）。"""
    raw = (await file.read()).decode("utf-8", errors="replace")
    name = (file.filename or "").lower()
    imported = 0
    if name.endswith(".json") or raw.lstrip().startswith("["):
        data = json.loads(raw)
        for d in data:
            payload = JobPayload(
                job_name=str(d.get("job_name", "")).strip(),
                core_duties=d.get("core_duties", "") or "",
                required_skills=d.get("required_skills", []) or [],
                bonus_skills=d.get("bonus_skills", []) or [],
                scenarios=d.get("scenarios", []) or [],
                source=d.get("source", []) or [],
                quality=float(d.get("quality", 0) or 0),
                is_emerging=bool(d.get("is_emerging", False)),
                evolution=d.get("evolution", {}) or {},
                collected_at=str(d.get("collected_at", "") or ""),
                updated_at=str(d.get("updated_at", "") or ""),
            )
            if payload.job_name:
                create_job(payload)
                imported += 1
    else:
        # CSV：首行标题；支持 job_name,core_duties,required_skills(分号分隔)
        import csv as _csv
        import io as _io
        reader = _csv.DictReader(_io.StringIO(raw))
        for row in reader:
            job_name = (row.get("job_name") or row.get("title") or "").strip()
            if not job_name:
                continue
            skills = [s.strip() for s in (row.get("required_skills") or "").split(";") if s.strip()]
            payload = JobPayload(job_name=job_name, required_skills=skills)
            create_job(payload)
            imported += 1
    return ok({"imported": imported})



@router.get("/graph/skill-radar")
def graph_skill_radar(node_name: str = Query("")):
    # MVP：无节点画像数据，返回空结构（前端按空处理）
    return ok({"dimensions": [], "values": []})
