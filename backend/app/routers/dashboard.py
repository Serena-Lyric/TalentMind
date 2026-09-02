"""数据看板 API（A 集成层，MVP 补全）。前缀 /api 由 main.py 指定。"""
import json

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.response import ok

router = APIRouter()

# 基础行业赛道（MVP 占位，后续按 M2 产出/图谱生成）
TRACKS = [
    {"id": "ai", "name": "人工智能", "color": "#7c5cff",
     "description": "大模型、算法与智能体应用"},
    {"id": "frontend", "name": "前端开发", "color": "#2f7cf6",
     "description": "Web 应用、体验与工程化"},
    {"id": "backend", "name": "后端开发", "color": "#43a047",
     "description": "服务端、中间件与架构"},
    {"id": "data", "name": "大数据", "color": "#ef6c00",
     "description": "数据仓库、实时计算与 BI"},
    {"id": "cloud", "name": "云计算/DevOps", "color": "#00897b",
     "description": "云原生、容器与自动化运维"},
]

RADAR_DIMENSIONS = ["市场需求", "技术热度", "岗位覆盖", "增长趋势",
                    "学习难度", "生态成熟", "薪资水平", "就业广度"]


@router.get("/dashboard/overview")
def dashboard_overview():
    db = SessionLocal()
    try:
        total_jobs = db.execute(text("SELECT COUNT(*) FROM job_definition")).scalar() or 0
        total_resumes = db.execute(text("SELECT COUNT(*) FROM resume")).scalar() or 0
    finally:
        db.close()
    return ok({
        "totalJobs": total_jobs,
        "totalResumes": total_resumes,
        "matchSuccess": 0,
        "skillGaps": 0,
        "coralBlocks": [
            {"label": "新增岗位", "value": 0},
            {"label": "待面试", "value": 0},
            {"label": "紧急招聘", "value": 0},
        ],
    })


@router.get("/dashboard/trend")
def dashboard_trend(range: str = Query("month")):
    """按天聚合 signal 信号量，取信号值最高的 Top 技能作为多条序列。

    数据源：`signal` 表（captured_at / skill_or_job / value）。
    无数据时返回空结构（前端诚实空态），不编造数字。
    """
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT DATE(captured_at) AS d, skill_or_job AS s, SUM(value) AS v "
            "FROM `signal` GROUP BY DATE(captured_at), skill_or_job ORDER BY d"
        )).all()
    finally:
        db.close()
    if not rows:
        return ok({"months": [], "series": []})
    dates = sorted({str(r.d) for r in rows})
    total: dict[str, float] = {}
    for r in rows:
        total[r.s] = total.get(r.s, 0.0) + float(r.v or 0)
    top = [s for s, _ in sorted(total.items(), key=lambda x: -x[1])[:5]]
    colors = ["#E07B6D", "#A8C5B8", "#7B8FA8", "#E8A88A", "#66BB6A"]
    series = []
    for i, s in enumerate(top):
        by_date = {str(r.d): float(r.v or 0) for r in rows if r.s == s}
        series.append({
            "name": s,
            "color": colors[i % len(colors)],
            "data": [round(by_date.get(d, 0.0), 1) for d in dates],
        })
    return ok({"months": [d[5:] for d in dates], "series": series})


@router.get("/dashboard/skill-distribution")
def dashboard_skill_distribution():
    """从 job_skill 统计技能出现频次。"""
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT skills FROM job_skill")).all()
    finally:
        db.close()
    counter: dict[str, int] = {}
    for (skills_json,) in rows:
        if not skills_json:
            continue
        try:
            skills = json.loads(skills_json) if isinstance(skills_json, str) else skills_json
        except (TypeError, json.JSONDecodeError):
            continue
        for s in skills:
            name = (s.get("name") if isinstance(s, dict) else s) or ""
            if name:
                counter[name] = counter.get(name, 0) + 1
    if not counter:
        return ok([])
    max_count = max(counter.values())
    items = [{"name": k, "count": v,
              "percentage": round(v / max_count * 100)}
             for k, v in sorted(counter.items(), key=lambda x: -x[1])]
    return ok(items[:30])


@router.get("/dashboard/skill-radar")
def dashboard_skill_radar(skill_name: str = Query("")):
    # 暂无技能画像数据：返回空结构（前端按空处理），不再返回全 50 占位
    return ok({"dimensions": [], "values": []}, message="暂无技能画像数据")


@router.get("/dashboard/industry-tracks")
def dashboard_industry_tracks():
    return ok(TRACKS)