"""集成测试 —— 全管道串联（不含 API 调用）。"""
import pytest
import json
from pathlib import Path
from app.job_analysis.models import (
    JdRecord, ExtractionResult, SkillEntry, EvolutionInfo,
    MergedJobDefinition, MergedJobSkillDetail,
)
from app.job_analysis.db import parse_jd_pool
from app.job_analysis.rules import apply_rules
from app.job_analysis.merge import merge_jobs
from app.job_analysis.export import export_all, _write_json, _load_json, _is_valid_checkpoint
from app.job_analysis.config import DATA_DIR

DATA_DIR_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "job_analysis"


# ── DB → Rules ──

def test_full_rules_pipeline():
    """测试 DB加载 → 硬规则预筛 的完整链路。"""
    sql_path = DATA_DIR_PATH / "seed_jd_pool.sql"
    if not sql_path.exists():
        pytest.skip("seed_jd_pool.sql not found")

    records = parse_jd_pool(str(sql_path))
    assert len(records) > 0

    passed, rejected = apply_rules(records)
    assert len(passed) > 0
    assert len(passed) + len(rejected) == len(records)


# ── DB → Rules → Merge ──

def test_rules_to_merge_chain():
    """测试 DB→Rules→Merge 链路（不含 LLM）。"""
    sql_path = DATA_DIR_PATH / "seed_jd_pool.sql"
    if not sql_path.exists():
        pytest.skip("seed_jd_pool.sql not found")

    records = parse_jd_pool(str(sql_path))
    passed, _ = apply_rules(records)

    # 模拟 stage3 输出：每条 JdRecord → ExtractionResult
    extractions = []
    for r in passed[:10]:  # 只取前10条避免太慢
        extractions.append(ExtractionResult(
            jd_id=r.id,
            job_name=r.job_title,
            core_duties=r.duties if r.duties else r.raw_text[:100],
            required_skills=[
                SkillEntry(name="python", confidence=0.8,
                           evidence=f"JD #{r.id}", is_required=True),
            ],
            bonus_skills=[],
            scenarios=["AI"],
            source=r.source,
            quality=r.quality,
            collected_at=r.crawled_at,
            evolution=EvolutionInfo(stage="growth", stage_confidence=0.5),
            verdict="pass",
        ))

    defs, skills = merge_jobs(extractions)
    assert len(defs) > 0
    assert len(skills) == len(defs)
    for d in defs:
        assert d.job_name
        assert d.source_jd_count >= 1


# ── Export ──

def test_export_roundtrip(tmp_path):
    """测试导出 → 重新加载 的数据一致性。"""
    from datetime import datetime, timezone
    from app.job_analysis.models import MergedJobSkill

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    defs = [
        MergedJobDefinition(
            job_name="AI Engineer",
            core_duties="Build AI systems",
            required_skills=["python", "langchain"],
            bonus_skills=["docker"],
            scenarios=["Enterprise AI"],
            source=["Boss直聘"],
            quality=0.85,
            first_seen="2026-01-01",
            collected_at="2026-07-01",
            updated_at=now,
            source_jd_count=3,
        ),
    ]
    skills = [
        MergedJobSkillDetail(
            job_name="AI Engineer",
            skills=[
                MergedJobSkill(
                    skill_id="s_python", name="python", weight=0.5,
                    confidence=0.9, evidence="JD #1: Python required",
                    evidence_jd_count=2, is_required=True,
                ),
                MergedJobSkill(
                    skill_id="s_langchain", name="langchain", weight=0.3,
                    confidence=0.85, evidence="JD #2: LangChain",
                    evidence_jd_count=1, is_required=True,
                ),
                MergedJobSkill(
                    skill_id="s_docker", name="docker", weight=0.2,
                    confidence=0.6, evidence="JD #1: Docker nice-to-have",
                    evidence_jd_count=1, is_required=False,
                ),
            ],
        ),
    ]

    stats = export_all(defs, skills, [], [], [], tmp_path)

    # 验证文件存在
    assert (tmp_path / "job_definition.json").exists()
    assert (tmp_path / "job_skill.json").exists()
    assert (tmp_path / "pipeline_report.json").exists()

    # 验证内容
    loaded_defs = _load_json(tmp_path / "job_definition.json")
    assert loaded_defs is not None
    assert len(loaded_defs) == 1
    assert loaded_defs[0]["job_name"] == "AI Engineer"

    # 验证 stats
    assert stats.final_job_definitions == 1


# ── Checkpoint ──

def test_checkpoint_detection(tmp_path):
    """测试断点检测逻辑。"""
    # 空文件不应视为有效 checkpoint
    empty_path = tmp_path / "empty.json"
    empty_path.write_text("", encoding="utf-8")
    assert not _is_valid_checkpoint(empty_path)

    # 有效 JSON 数组
    valid_path = tmp_path / "valid.json"
    valid_path.write_text('[{"a": 1}]', encoding="utf-8")
    assert _is_valid_checkpoint(valid_path)

    # JSON 对象（非数组）
    obj_path = tmp_path / "obj.json"
    obj_path.write_text('{"a": 1}', encoding="utf-8")
    assert not _is_valid_checkpoint(obj_path)


# ── All imports ──

def test_all_modules_importable():
    """确保所有模块可 import。"""
    modules = [
        "app.job_analysis.config", "app.job_analysis.models",
        "app.job_analysis.db", "app.job_analysis.rules",
        "app.job_analysis.llm", "app.job_analysis.stage1_relevance",
        "app.job_analysis.stage2_quality", "app.job_analysis.stage3_extract",
        "app.job_analysis.merge", "app.job_analysis.differ",
        "app.job_analysis.export", "app.job_analysis.pipeline",
        "app.job_analysis.translate",
    ]
    for mod in modules:
        __import__(mod)


# ── 数据流完整性 ──

def test_full_data_flow_no_api():
    """DB解析 → 规则 → 合并 → 导出 → 文件完整性（不含API）。"""
    sql_path = DATA_DIR_PATH / "seed_jd_pool.sql"
    if not sql_path.exists():
        pytest.skip("seed_jd_pool.sql not found")

    records = parse_jd_pool(str(sql_path))
    assert len(records) > 0, "fixture 无记录"

    passed, rejected = apply_rules(records)
    assert len(passed) + len(rejected) == len(records)
    # 确保每条记录字段完整
    for r in passed[:5]:
        assert r.id > 0
        assert r.job_title
        assert r.raw_text
        assert r.source


def test_merge_dedup_same_name():
    """同岗位名合并：skills union，quality 加权平均。"""
    from app.job_analysis.merge import merge_jobs
    e1 = ExtractionResult(
        jd_id=1, job_name="AI Engineer", core_duties="Build AI",
        required_skills=[
            SkillEntry(name="python", confidence=0.9, evidence="JD1", is_required=True),
        ],
        bonus_skills=[
            SkillEntry(name="docker", confidence=0.7, evidence="JD1", is_required=False),
        ],
        scenarios=["Enterprise AI"], source="src1", quality=0.9,
        collected_at="2026-01-01",
    )
    e2 = ExtractionResult(
        jd_id=2, job_name="AI Engineer", core_duties="Build AI systems",
        required_skills=[
            SkillEntry(name="python", confidence=0.95, evidence="JD2", is_required=True),
            SkillEntry(name="langchain", confidence=0.8, evidence="JD2", is_required=True),
        ],
        bonus_skills=[],
        scenarios=["Enterprise AI", "Healthcare AI"], source="src2", quality=0.7,
        collected_at="2026-02-01",
    )

    defs, skills_detail = merge_jobs([e1, e2])
    assert len(defs) == 1
    d = defs[0]
    assert d.job_name == "AI Engineer"
    assert d.source_jd_count == 2
    assert len(d.required_skills) >= 2  # python + langchain
    assert "python" in d.required_skills
    assert 0.7 < d.quality <= 1.0  # weighted average

    # job_skill 里 python 应该取最高 confidence
    skill_map = {s.name: s for s in skills_detail[0].skills}
    assert skill_map["python"].confidence == 0.95
    assert skill_map["python"].evidence_jd_count == 2


# ── 翻译输出验证 ──

def test_translate_structure_preserved():
    """翻译后不丢字段，技能数组长度一致。"""
    import asyncio
    import tempfile
    import os

    original = [{
        "job_name": "Software Engineer",
        "core_duties": "Build software products and lead teams.",
        "required_skills": ["python", "docker", "communication skills", "project management"],
        "bonus_skills": ["aws", "kubernetes"],
        "scenarios": ["Enterprise Software", "Cloud Migration"],
        "source": ["linkedin"],
        "quality": 0.85,
        "is_emerging": True,
        "evolution": {"stage": "growth", "stage_confidence": 0.6, "indicators": {}},
        "first_seen": "2026-01-01",
        "collected_at": "2026-01-01",
        "updated_at": "2026-01-01",
        "source_jd_count": 1,
    }]

    with tempfile.TemporaryDirectory() as tmpdir:
        en_path = os.path.join(tmpdir, "en.json")
        zh_path = os.path.join(tmpdir, "zh.json")
        with open(en_path, "w", encoding="utf-8") as f:
            json.dump(original, f, ensure_ascii=False)

        from app.job_analysis.translate import translate_job_definitions
        asyncio.run(translate_job_definitions(en_path, zh_path))

        with open(zh_path, "r", encoding="utf-8") as f:
            zh = json.load(f)

        assert len(zh) == 1
        # 所有字段必须保留
        for key in original[0]:
            assert key in zh[0], f"Missing key: {key}"
        # 技能数量一致
        assert len(zh[0]["required_skills"]) == len(original[0]["required_skills"])
        assert len(zh[0]["bonus_skills"]) == len(original[0]["bonus_skills"])
        # 技术名词保留英文，通用技能可能翻译
        assert "python" in zh[0]["required_skills"] or "Python" in zh[0]["required_skills"]


def test_translate_job_skills():
    """job_skill 翻译后结构完整。"""
    import asyncio
    import tempfile
    import os

    original = [{
        "job_name": "AI Engineer",
        "skills": [
            {"skill_id": "s_python", "name": "python", "weight": 0.5,
             "confidence": 0.9, "evidence": "JD #1: Python required",
             "evidence_jd_count": 2, "is_required": True},
            {"skill_id": "s_comm", "name": "communication skills", "weight": 0.3,
             "confidence": 0.8, "evidence": "JD #1: Good communication",
             "evidence_jd_count": 1, "is_required": True},
        ]
    }]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "skill.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(original, f, ensure_ascii=False)

        from app.job_analysis.translate import translate_job_skills
        asyncio.run(translate_job_skills(path, path))

        with open(path, "r", encoding="utf-8") as f:
            zh = json.load(f)

        assert len(zh) == 1
        assert len(zh[0]["skills"]) == 2
        # python 应保留英文（大小写不敏感）
        skill_names_lower = [s["name"].lower() for s in zh[0]["skills"]]
        assert "python" in skill_names_lower, f"Skills: {[s['name'] for s in zh[0]['skills']]}"
        # evidence 不变
        assert zh[0]["skills"][0]["evidence"] == "JD #1: Python required"


# ── 交付物完整性 ──

def test_exchange_deliverables():
    """验证 exchange/M2/ 下所有交付物存在且格式正确。"""
    exchange = Path(__file__).resolve().parents[3] / "exchange" / "m2"
    if not exchange.exists():
        pytest.skip("exchange/m2/ not found")

    required = [
        "job_definition.json",
        "job_definition_zh.json",
        "job_skill.json",
        "job_change_log.json",
        "pipeline_report.json",
        "rejected.json",
        "manual_review.json",
    ]
    for fname in required:
        fpath = exchange / fname
        assert fpath.exists(), f"Missing: {fname}"

    # job_definition 结构
    with open(exchange / "job_definition.json", "r", encoding="utf-8") as f:
        defs = json.load(f)
    assert isinstance(defs, list)
    assert len(defs) > 0
    for d in defs:
        assert d.get("job_name")
        assert d.get("core_duties")
        assert isinstance(d.get("required_skills"), list)
        assert isinstance(d.get("bonus_skills"), list)
        assert isinstance(d.get("scenarios"), list)

    # 中文版一对一
    with open(exchange / "job_definition_zh.json", "r", encoding="utf-8") as f:
        zh = json.load(f)
    assert len(zh) == len(defs), f"ZH mismatch: {len(zh)} vs {len(defs)}"

    # job_skill 结构
    with open(exchange / "job_skill.json", "r", encoding="utf-8") as f:
        skills = json.load(f)
    assert len(skills) == len(defs), f"Skills mismatch: {len(skills)} vs {len(defs)}"
    for s in skills:
        assert s.get("job_name")
        assert isinstance(s.get("skills"), list)
        assert len(s["skills"]) > 0
        for sk in s["skills"]:
            assert sk.get("name")
            assert 0 <= sk.get("confidence", 0) <= 1

    # pipeline_report 结构
    with open(exchange / "pipeline_report.json", "r", encoding="utf-8") as f:
        report = json.load(f)
    assert isinstance(report, list)
    r = report[0]
    assert r.get("final_job_definitions", 0) > 0


def test_chinese_content_is_chinese():
    """中文版文件确实包含中文。"""
    import re
    exchange = Path(__file__).resolve().parents[3] / "exchange" / "m2"
    if not exchange.exists():
        pytest.skip("exchange/m2/ not found")

    has_cjk = re.compile(r'[一-鿿]')

    # job_definition_zh 的 job_name 应该是中文
    with open(exchange / "job_definition_zh.json", "r", encoding="utf-8") as f:
        zh = json.load(f)
    zh_names = sum(1 for d in zh if has_cjk.search(d.get("job_name", "")))
    assert zh_names >= len(zh) * 0.8, f"Only {zh_names}/{len(zh)} job names have Chinese"

    # core_duties 应该有中文
    zh_duties = sum(1 for d in zh if has_cjk.search(d.get("core_duties", "")))
    assert zh_duties >= len(zh) * 0.8, f"Only {zh_duties}/{len(zh)} duties have Chinese"

    # job_skill 的 job_name 应该是中文
    with open(exchange / "job_skill.json", "r", encoding="utf-8") as f:
        skills = json.load(f)
    sk_zh = sum(1 for s in skills if has_cjk.search(s.get("job_name", "")))
    assert sk_zh >= len(skills) * 0.8, f"Only {sk_zh}/{len(skills)} skill job_names have Chinese"
