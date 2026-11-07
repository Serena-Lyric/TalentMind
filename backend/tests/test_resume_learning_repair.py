"""合成简历/内存文件回归；数据库边界一律替换，不连接任何真实服务。"""
import asyncio
import io

import pytest
from docx import Document
from fastapi import UploadFile

from app.matching.canonical import to_canonical
from app.matching.matcher import quick_match_weighted
from app.matching.resume_parser import parse_resume
from app.matching.skill_extractor import extract_skills
from app.response import BizError
from app.routers import mvp, learning


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    def forbidden():
        pytest.fail("test attempted to open a database")
    monkeypatch.setattr(mvp, "SessionLocal", forbidden)
    monkeypatch.setattr(learning, "SessionLocal", forbidden)


def test_symbol_skills_and_ascii_boundaries():
    skills = {to_canonical(s) for s in extract_skills("熟悉C++、C#和Python，使用Node.js。")}
    assert {"c++", "c#", "python", "node.js"} <= skills
    assert "c" not in skills
    assert "java" not in {to_canonical(s) for s in extract_skills("JavaScript")}
    assert extract_skills("Python MySQL") == extract_skills("MySQL Python") == sorted(extract_skills("Python MySQL"), key=str.casefold)


def test_undated_work_and_section_headers():
    parsed = parse_resume("姓名：测试甲\n工作经历\n示例科技有限公司\n后端工程师\n负责Python服务。\n荣誉奖项\n校级奖学金")
    work = parsed["work_experience"][0]
    assert work["company"] == "示例科技有限公司"
    assert work["position"] == "后端工程师"
    assert work["description"] == ["负责Python服务。"]
    assert parsed["honors"][0]["title"] == "校级奖学金"


def test_generic_school_multiline_and_contact_spaces():
    parsed = parse_resume("姓名：测试乙\n手机： 13800138000\n邮箱： test@example.com\n教育经历\n2019.09 - 2023.06\n示例应用技术学院\n软件工程 本科\n项目经历\n演示平台 2023.01 - 2023.06\n负责接口开发")
    assert parsed["personal_info"]["phone"] == "13800138000"
    assert parsed["personal_info"]["email"] == "test@example.com"
    assert parsed["education"] == [{"start_date": "2019.09", "end_date": "2023.06", "school": "示例应用技术学院", "major": "软件工程", "degree": "本科"}]


def test_section_word_inside_description_is_not_a_heading():
    parsed = parse_resume("姓名：测试丙\n自我评价：喜欢整理项目经验\n教育背景\n示例大学 本科")
    assert parsed["project_experience"] == []
    assert parsed["self_evaluation"] == "喜欢整理项目经验。"


@pytest.mark.parametrize("header", ["一、教育背景", "1. 教育背景", "教育背景 / Education", "【教育背景】", "## 教育背景"])
def test_decorated_section_headers_remain_readable(header):
    parsed = parse_resume(f"姓名：测试丙\n{header}\n示例大学 本科\n二、工作经历\n演示公司\n测试工程师\n三、项目经历 / Projects\n演示项目 2024.01 - 2024.06\n负责开发")
    assert parsed["education"][0]["school"] == "示例大学"
    assert parsed["work_experience"][0]["company"] == "演示公司"
    assert parsed["project_experience"][0]["name"] == "演示项目"


def test_docx_body_order_and_merged_cells_once():
    doc = Document()
    doc.add_paragraph("教育背景")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "示例学院 本科"
    doc.add_paragraph("工作经历")
    doc.add_paragraph("演示公司")
    data = io.BytesIO()
    doc.save(data)
    result = mvp._extract_file_text("resume.docx", data.getvalue())
    assert result.splitlines() == ["教育背景", "示例学院 本科", "工作经历", "演示公司"]


@pytest.mark.parametrize("name,data", [("bad.exe", b"hello"), ("old.doc", b"\xd0\xcf\x11\xe0"), ("bad.txt", b"\x00\xff\x01")])
def test_unsupported_or_binary_upload_rejected(name, data):
    with pytest.raises(BizError):
        asyncio.run(mvp.resume_upload(file=UploadFile(filename=name, file=io.BytesIO(data)), content="", target_job_id=""))


def test_upload_limit_checked_before_parsing(monkeypatch):
    monkeypatch.setattr(mvp, "_extract_file_text", lambda *args: pytest.fail("oversize reached parser"))
    with pytest.raises(BizError, match="10MB"):
        asyncio.run(mvp.resume_upload(file=UploadFile(filename="a.txt", file=io.BytesIO(b"a" * (10 * 1024 * 1024 + 1))), content="", target_job_id=""))


def test_weighted_match_aliases_and_overlap():
    result = quick_match_weighted(["K8s"], ["Kubernetes", "k8s"], ["K8S", "Docker"])
    assert result["matched_skills"] == ["kubernetes"]
    assert result["unmatched_job_skills"] == ["docker"]
    assert result["job_required_count"] == 1
    assert result["total_score"] == 70


class CatalogSession:
    def execute(self, *args, **kwargs):
        return self
    def mappings(self):
        return self
    def all(self):
        return [{"id": 1, "job_name": "测试岗位", "required_skills": '["Python", "Docker"]', "bonus_skills": "[]", "source": "[]"}]
    def close(self):
        pass


def test_upload_real_score_and_profile_coverage(monkeypatch):
    monkeypatch.setattr(mvp, "SessionLocal", CatalogSession)
    data = asyncio.run(mvp.resume_upload(file=None, content="姓名：测试丁\n技能：Python", target_job_id=""))["data"]
    job = data["recommendedJobs"][0]
    assert 0 < job["score"] < 90
    assert job["score"] == job["raw_score"] == job["display_score"]
    assert not job["display_randomized"]
    assert not data["recommendationFloorApplied"]
    assert data["parseQuality"] < 92
    assert data["parseQualityBasis"] == "field_coverage"
    assert "education_history" in data["profile"]
    assert "work_experience" in data["profile"]


def test_recent_work_uses_calendar_dates_not_lexical_order(monkeypatch):
    monkeypatch.setattr(mvp, "SessionLocal", CatalogSession)
    content = "姓名：测试丁\n工作经历\n2024.10 - 2025.1 新公司 后端工程师\n2024.9 - 2024.10 旧公司 测试工程师"
    data = asyncio.run(mvp.resume_upload(file=None, content=content, target_job_id=""))["data"]
    assert data["profile"]["company"] == "新公司"
    assert data["profile"]["role"] == "后端工程师"


def path(required=(), bonus=(), resume=()):
    return learning.build_learning_path(job_id="1", job_title="测试岗位", job_name_en="Test", category="", required=list(required), bonus=list(bonus), resume_skills=list(resume))


def test_learning_aliases_deduplicate_and_required_wins():
    data = path(["K8s", "Kubernetes", " "], ["kubernetes", "Docker", "docker"], ["KUBERNETES"])
    assert len(data["core_skills"]) == 1
    assert len(data["bonus_skills"]) == 1
    assert data["overview"]["mastered_required"] == 1
    assert data["overview"]["missing_bonus"] == 1
    assert len(data["missing_skills"]) == 1


def test_empty_job_is_insufficient_evidence():
    data = path()
    assert data["overview"]["at_standard"] is False
    assert data["overview"]["requirements_available"] is False


def test_unmentioned_soft_skill_needs_verification():
    data = path(["沟通", "Python"], resume=["Python"])
    assert data["missing_skills"] == []
    assert data["stages"] == []
    assert data["verification_skills"][0]["name"] == "沟通"
    assert data["verification_skills"][0]["status"] == "needs_verification"
    assert data["overview"]["at_standard"] is False


def test_gap_has_practice_and_completion_criteria():
    item = path(["Docker"])["missing_skills"][0]
    assert item["practice"]
    assert item["completion_criteria"]


@pytest.mark.parametrize("value", ['"python"', '"123"', '{"a":1}', [None, {}, " Python ", ""]])
def test_learning_list_rejects_non_lists_or_non_strings(value):
    assert learning._list(value) == (["Python"] if isinstance(value, list) else [])


def test_upload_to_learning_http_flow_with_isolated_sqlite(monkeypatch):
    """真实路由 + SQL 查询；唯一内存库，夹具在 finally 精确清理并核对零行。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    assert engine.url.database is None  # 无磁盘数据库、无宿主服务连接
    with engine.begin() as db:
        db.execute(text('CREATE TABLE job_definition (id INTEGER PRIMARY KEY, job_name TEXT, name_en TEXT, job_name_zh TEXT, category TEXT, required_skills TEXT, bonus_skills TEXT, source TEXT, quality TEXT, collected_at TEXT, source_jd_count INTEGER, evolution TEXT, m2_job_id TEXT)'))
        db.execute(text("INSERT INTO job_definition (id, job_name, required_skills, bonus_skills, source) VALUES (800001, 'fixture-resume-learning-http', '[\"Kubernetes\",\"Docker\",\"沟通\"]', '[\"docker\"]', '[]')"))
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(mvp, 'SessionLocal', factory)
    monkeypatch.setattr(learning, 'SessionLocal', factory)
    app = FastAPI()
    app.include_router(mvp.router, prefix='/api')
    app.include_router(learning.router, prefix='/api')
    try:
        with TestClient(app) as client:
            response = client.post('/api/resume/upload', files={'file': ('synthetic.txt', '姓名：演示甲\n技能：K8s'.encode(), 'text/plain')})
            assert response.status_code == 200
            uploaded = response.json()['data']
            job = uploaded['recommendedJobs'][0]
            assert job['id'] == '800001'
            assert job['matched'] == ['kubernetes']
            response = client.post('/api/learning/generate-path', json={'job_id': job['id'], 'resume_skills': uploaded['profile']['skills'], 'requirements_version': job['requirements_version']})
            assert response.status_code == 200
            result = response.json()['data']
            assert result['job_id'] == job['id']
            assert [s['name'] for s in result['missing_skills']] == ['Docker']
            assert result['verification_skills'][0]['name'] == '沟通'
            assert result['bonus_skills'] == []
            assert client.post('/api/learning/generate-path', json={'job_id': 0}).status_code == 422
    finally:
        with engine.begin() as db:
            db.execute(text("DELETE FROM job_definition WHERE id=800001 AND job_name='fixture-resume-learning-http'"))
            assert db.execute(text('SELECT count(*) FROM job_definition')).scalar_one() == 0
        engine.dispose()

def test_catalog_profile_does_not_invent_recruitment_state():
    item = mvp._catalog_to_item({'id': 1, 'job_name': 'fixture-profile', 'updated_at': '2026-11-07'})
    assert item['status'] == 'unknown'
    assert item['collected_at'] == ''
    assert item['object_type'] == 'job_profile'


def test_recommendation_has_version_but_no_implicit_target(monkeypatch):
    monkeypatch.setattr(mvp, 'SessionLocal', CatalogSession)
    result = mvp._process_resume_upload('', None, '技能：Python', '')['data']
    assert result['matchResult']['target_job_id'] == ''
    assert len(result['recommendedJobs'][0]['requirements_version']) == 64


def test_learning_rejects_changed_requirements_and_returns_same_version_score(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(mvp, 'SessionLocal', CatalogSession)
    recommendation = mvp._process_resume_upload('', None, '技能：Python', '')['data']['recommendedJobs'][0]
    row = CatalogSession().all()[0]
    monkeypatch.setattr(learning, 'SessionLocal', CatalogSession)
    monkeypatch.setattr(learning, '_job', lambda db, job_id: row)
    result = learning.generate_learning_path(learning.LearningPathRequest(job_id=1, resume_skills=['Python'], requirements_version=recommendation['requirements_version']))['data']
    assert result['score'] == recommendation['score']
    assert result['requirements_version'] == recommendation['requirements_version']
    row['bonus_skills'] = '["Git"]'
    with pytest.raises(HTTPException) as exc:
        learning.generate_learning_path(learning.LearningPathRequest(job_id=1, resume_skills=['Python'], requirements_version=recommendation['requirements_version']))
    assert exc.value.status_code == 409

def test_catalog_edit_keeps_storage_name_separate_from_english_label():
    item = mvp._catalog_to_item({'id': 2, 'job_name': '数据库工程师', 'name_en': 'Database Engineer'})
    assert item['job_name'] == '数据库工程师'
