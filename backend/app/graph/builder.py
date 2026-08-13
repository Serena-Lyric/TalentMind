"""
M3 图谱模块 - 岗位知识图谱构建器

功能：从数据库/Mock数据加载岗位信息，构建岗位-技能图谱，输出 graph.json

产出物：exchange/m3/graph.json（nodes/edges 格式）
数据契约：遵循 2026-08-03-team-plan-design.md 规范
命名风格：snake_case
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Any

# ====================== 配置区 ======================
# 仓库根目录（backend/app/graph/builder.py -> parents[3]）
REPO_ROOT = Path(__file__).resolve().parents[3]
SIMILAR_THRESHOLD = 0.25  # 岗位相似度阈值，超过则建立关联
OUTPUT_DIR = REPO_ROOT / "exchange" / "m3"
MOCK_DATA_PATH = OUTPUT_DIR / "mock_job_data.json"
OUTPUT_PATH = OUTPUT_DIR / "graph.json"
M2_JOB_DEFINITION_PATH = REPO_ROOT / "exchange" / "m2" / "job_definition.json"
SKILL_DICT_PATH = REPO_ROOT / "backend" / "app" / "skills" / "skill_dict_seed.json"

# 数据源优先级：M2 交接产出优先，Mock 回退（D26/D31）
DATA_SOURCE_PRIORITY = ["m2", "mock"]

# 统一响应格式（API 场景）
class Response:
    @staticmethod
    def success(data: Any, message: str = "success") -> Dict:
        return {"code": 0, "message": message, "data": data}

    @staticmethod
    def error(message: str, code: int = 500) -> Dict:
        return {"code": code, "message": message, "data": None}
# ====================================================


# ====================== 数据加载模块 ======================
def load_job_data() -> List[Dict]:
    """
    从数据源加载岗位数据（按优先级尝试：MySQL -> SQLite -> Mock）

    Returns:
        List[Dict]: 岗位数据列表，格式参考 job_definition.json

    Example:
        >>> jobs = load_job_data()
        >>> len(jobs) > 0
        True
    """
    for source in DATA_SOURCE_PRIORITY:
        if source == "m2":
            result = load_m2_job_definitions()
            if result:
                return result
        elif source == "mock":
            result = load_mock_data()
            if result:
                return result

    print("[WARN] 所有数据源均不可用，使用空数据集")
    return []


def load_m2_job_definitions() -> List[Dict]:
    """从 M2 交接产出 exchange/m2/job_definition.json 加载岗位数据。"""
    if not M2_JOB_DEFINITION_PATH.exists():
        print(f"[WARN] M2 产出不存在: {M2_JOB_DEFINITION_PATH}")
        return []
    try:
        with open(M2_JOB_DEFINITION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        jobs = []
        for d in data:
            jobs.append({
                "job_name": d.get("job_name", ""),
                "core_duties": d.get("core_duties", ""),
                "required_skills": list(d.get("required_skills", [])),
                "bonus_skills": list(d.get("bonus_skills", [])),
                "scenarios": list(d.get("scenarios", [])),
                "source": list(d.get("source", [])),
                "quality": d.get("quality", 0.0),
                "industry": "",
                "collected_at": d.get("collected_at", ""),
                "is_emerging": d.get("is_emerging", False),
            })
        print(f"[OK] 成功加载 M2 产出: {len(jobs)} 个岗位")
        return jobs
    except Exception as e:
        print(f"[ERROR] 加载 M2 产出失败: {e}")
        return []


_SKILL_CACHE: tuple[set[str], dict[str, str]] | None = None


def _load_skill_dict() -> tuple[set[str], dict[str, str]]:
    """加载 skill_dict 种子：返回 (canonical 集合, alias→canonical 映射)。"""
    global _SKILL_CACHE
    if _SKILL_CACHE is None:
        with open(SKILL_DICT_PATH, "r", encoding="utf-8") as f:
            entries = json.load(f)
        canonicals = {e["canonical"] for e in entries}
        aliases = {}
        for e in entries:
            for a in e["aliases"]:
                aliases[a.lower()] = e["canonical"]
        _SKILL_CACHE = (canonicals, aliases)
    return _SKILL_CACHE


def _canonicalize(name: str) -> str | None:
    """技能名 → skill_dict.canonical；无法映射返回 None。"""
    canonicals, aliases = _load_skill_dict()
    n = name.strip().lower()
    if n in aliases:
        return aliases[n]
    if n in canonicals:
        return n
    return None


def _normalize_skills(jobs: List[Dict]) -> List[Dict]:
    """归一岗位技能到 canonical；未命中技能跳过并记录（D31 反幻觉）。"""
    skipped: List[str] = []
    for job in jobs:
        req, bonus = [], []
        for s in job.get("required_skills", []):
            c = _canonicalize(s)
            if c:
                req.append(c)
            else:
                skipped.append(f"{job.get('job_name')}: {s}")
        for s in job.get("bonus_skills", []):
            c = _canonicalize(s)
            if c:
                bonus.append(c)
            else:
                skipped.append(f"{job.get('job_name')}: {s}")
        job["required_skills"] = req
        job["bonus_skills"] = bonus
    if skipped:
        print(f"[WARN] 跳过未归一技能 {len(skipped)} 个: {skipped[:10]}")
    return jobs


def load_mock_data() -> List[Dict]:
    """从 Mock 文件加载岗位数据"""
    if not os.path.exists(MOCK_DATA_PATH):
        print(f"[WARN] Mock 数据文件不存在: {MOCK_DATA_PATH}")
        return []

    try:
        with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[OK] 成功加载 Mock 数据: {len(data)} 个岗位")
            return data
    except Exception as e:
        print(f"[ERROR] 加载 Mock 数据失败: {e}")
        return []


def load_from_sqlite() -> List[Dict]:
    """
    从 SQLite 数据库加载岗位数据（降级方案）

    Returns:
        List[Dict]: 岗位数据列表，字段已映射为团队规范格式
    """
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"[WARN] SQLite 数据库不存在: {SQLITE_DB_PATH}")
        return None

    try:
        import sqlite3
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM job_info").fetchall()

        jobs = []
        for row in rows:
            # 映射 SQLite 字段到团队规范格式
            req_raw = row["required_skill"] or ""
            bonus_raw = row["bonus_skill"] or ""

            jobs.append({
                "job_name": row["job_name"],
                "core_duties": row["duty"] or "",
                "required_skills": [s.strip() for s in req_raw.split(",") if s.strip()],
                "bonus_skills": [s.strip() for s in bonus_raw.split(",") if s.strip()],
                "scenarios": [],
                "source": [],
                "quality": 0.8,
                "industry": row["industry"] or "",
                "collected_at": "2026-08-01T00:00:00",
                "is_emerging": False
            })

        conn.close()
        print(f"[OK] 成功从 SQLite 加载: {len(jobs)} 个岗位")
        return jobs

    except Exception as e:
        print(f"[ERROR] 从 SQLite 加载失败: {e}")
        return None


# ====================== 图谱构建模块 ======================
def build_skill_nodes(jobs: List[Dict]) -> List[Dict]:
    """
    构建技能节点（共享模式：同名技能只创建一次）

    Args:
        jobs: 岗位数据列表

    Returns:
        List[Dict]: 技能节点列表，格式: {id, type, name, category}

    Example:
        >>> jobs = load_job_data()
        >>> skills = build_skill_nodes(jobs)
        >>> # 同名技能只出现一次
        >>> skill_names = [s["name"] for s in skills]
        >>> len(skill_names) == len(set(skill_names))
        True
    """
    skill_dict = {}  # {skill_name: {"category": "required"/"bonus", "jobs": []}}

    for job in jobs:
        # 必备技能
        for skill in job.get("required_skills", []):
            if skill not in skill_dict:
                skill_dict[skill] = {"category": "required", "jobs": []}
            skill_dict[skill]["jobs"].append(job["job_name"])

        # 加分技能
        for skill in job.get("bonus_skills", []):
            if skill not in skill_dict:
                skill_dict[skill] = {"category": "bonus", "jobs": []}
            elif skill_dict[skill]["category"] == "required":
                # 必备优先级高于加分
                pass
            skill_dict[skill]["jobs"].append(job["job_name"])

    # 构建节点列表
    nodes = []
    for skill_name, meta in sorted(skill_dict.items()):
        nodes.append({
            "id": skill_name,  # 对齐 skill_dict.canonical（D26/D31）
            "type": "skill",
            "name": skill_name,
            "category": meta["category"],
            "job_count": len(set(meta["jobs"]))  # 被多少岗位需要（热度）
        })

    print(f"[BUILD] 构建技能节点: {len(nodes)} 个（已去重）")
    return nodes


def build_job_nodes(jobs: List[Dict]) -> List[Dict]:
    """
    构建岗位节点

    Args:
        jobs: 岗位数据列表

    Returns:
        List[Dict]: 岗位节点列表，格式: {id, type, name, industry, is_emerging}
    """
    nodes = []
    for job in jobs:
        nodes.append({
            "id": job["job_name"],  # 对齐 job_definition.job_name（D26）
            "type": "job",
            "name": job["job_name"],
            "industry": job.get("industry", ""),
            "is_emerging": job.get("is_emerging", False),
            "core_duties": job.get("core_duties", "")
        })

    print(f"[BUILD] 构建岗位节点: {len(nodes)} 个")
    return nodes


def build_job_skill_edges(jobs: List[Dict], skill_nodes: List[Dict]) -> List[Dict]:
    """
    构建岗位-技能关系边（REQUIRES）

    Args:
        jobs: 岗位数据列表
        skill_nodes: 技能节点列表

    Returns:
        List[Dict]: 边列表，格式: {source, target, type, weight, is_required}
    """
    # 构建技能名称到节点ID的映射
    skill_id_map = {node["name"]: node["id"] for node in skill_nodes}

    edges = []
    for job in jobs:
        job_id = job["job_name"]

        # 必备技能边
        for skill in job.get("required_skills", []):
            if skill in skill_id_map:
                edges.append({
                    "source": job_id,
                    "target": skill_id_map[skill],
                    "type": "REQUIRES",
                    "weight": 1.0,
                    "is_required": True
                })

        # 加分技能边
        for skill in job.get("bonus_skills", []):
            if skill in skill_id_map:
                edges.append({
                    "source": job_id,
                    "target": skill_id_map[skill],
                    "type": "REQUIRES",
                    "weight": 0.6,
                    "is_required": False
                })

    print(f"[BUILD] 构建岗位-技能关系: {len(edges)} 条")
    return edges


def calc_jaccard(set_a: Set, set_b: Set) -> float:
    """
    计算杰卡德相似度

    Args:
        set_a: 技能集合 A
        set_b: 技能集合 B

    Returns:
        float: 相似度值 [0, 1]
    """
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return round(inter / union, 4)


def build_job_edges(jobs: List[Dict]) -> List[Dict]:
    """
    构建岗位-岗位关系边（RELATED_TO），基于技能相似度

    Args:
        jobs: 岗位数据列表

    Returns:
        List[Dict]: 边列表，格式: {source, target, type, similar}
    """
    # 构建岗位技能集合
    job_skill_map = {}
    for job in jobs:
        all_skills = set(job.get("required_skills", [])) | set(job.get("bonus_skills", []))
        job_skill_map[job["job_name"]] = all_skills

    # 计算两两相似度
    edges = []
    job_ids = list(job_skill_map.keys())

    for i in range(len(job_ids)):
        for j in range(i + 1, len(job_ids)):
            job1_id = job_ids[i]
            job2_id = job_ids[j]
            sim = calc_jaccard(job_skill_map[job1_id], job_skill_map[job2_id])

            if sim >= SIMILAR_THRESHOLD:
                edges.append({
                    "source": job1_id,
                    "target": job2_id,
                    "type": "RELATED_TO",
                    "similar": sim
                })

    print(f"[BUILD] 构建岗位-岗位关系: {len(edges)} 条（阈值≥{SIMILAR_THRESHOLD}）")
    return edges


# ====================== 输出模块 ======================
def export_graph_json(nodes: List[Dict], edges: List[Dict]) -> bool:
    """
    导出图谱数据到 graph.json 文件

    Args:
        nodes: 所有节点列表（Job + Skill）
        edges: 所有边列表（REQUIRES + RELATED_TO）

    Returns:
        bool: 是否成功

    Example:
        >>> export_graph_json([...nodes], [...edges])
        True
    """
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    graph_data = {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "version": "1.0"
        }
    }

    try:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] 图谱数据导出成功！")
        print(f"   文件路径: {OUTPUT_PATH}")
        print(f"   节点总数: {len(nodes)}")
        print(f"   边总数: {len(edges)}")
        return True

    except Exception as e:
        print(f"[ERROR] 导出失败: {e}")
        return False


# ====================== 主流程 ======================
def build_graph():
    """
    构建岗位知识图谱（主入口）

    Returns:
        Dict: 统一响应格式 {code, message, data}
    """
    print("=" * 60)
    print("[INFO] M3 图谱模块 - 开始构建岗位知识图谱")
    print("=" * 60)

    # 1. 加载数据
    print("\n[STEP 1] 加载岗位数据")
    jobs = load_job_data()
    if not jobs:
        return Response.error("加载岗位数据失败")
    jobs = _normalize_skills(jobs)

    # 2. 构建节点
    print("\n[STEP 2] 构建图谱节点")
    job_nodes = build_job_nodes(jobs)
    skill_nodes = build_skill_nodes(jobs)
    all_nodes = job_nodes + skill_nodes

    # 3. 构建边
    print("\n[STEP 3] 构建图谱关系")
    job_skill_edges = build_job_skill_edges(jobs, skill_nodes)
    job_edges = build_job_edges(jobs)
    all_edges = job_skill_edges + job_edges

    # 4. 导出文件
    print("\n[STEP 4] 导出图谱数据")
    success = export_graph_json(all_nodes, all_edges)

    if success:
        print("\n" + "=" * 60)
        print("[SUCCESS] 图谱构建完成！")
        print("=" * 60)
        return Response.success({
            "output_path": str(OUTPUT_PATH),
            "node_count": len(all_nodes),
            "edge_count": len(all_edges)
        })
    else:
        return Response.error("导出图谱数据失败")


if __name__ == "__main__":
    # 执行图谱构建
    result = build_graph()

    # 输出结果（API 场景）
    print("\n[RESULT] 执行结果（统一响应格式）:")
    print(json.dumps(result, ensure_ascii=False, indent=2))