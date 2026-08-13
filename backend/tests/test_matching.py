"""M4 简历匹配模块测试：技能提取、canonical 化（D31）、匹配输出。"""
from app.matching.skill_extractor import extract_skills, normalize_skill
from app.matching.matcher import ResumeJobMatcher, quick_match, match_resume_job
from app.matching.canonical import to_canonical


def test_extract_skills_basic():
    # 注意：原型 \b 边界对"中文紧邻英文"提取失效（已知限制，见资产与状态.md），此处用空格分隔文本
    skills = extract_skills("熟悉 Python、Java 和 Spring Boot，掌握 MySQL、Redis")
    assert "Python" in skills
    assert "Java" in skills
    assert "Spring Boot" in skills
    assert "MySQL" in skills


def test_normalize_skill_alias():
    assert normalize_skill("k8s") == "Kubernetes"
    assert normalize_skill("springboot") == "Spring Boot"


def test_to_canonical():
    assert to_canonical("Python") == "python"
    assert to_canonical("K8s") == "kubernetes"
    assert to_canonical("SpringBoot") == "spring boot"


def test_quick_match_canonical_output():
    result = quick_match(["Python", "Docker"], ["Python", "Kubernetes"])
    assert result["matched_skills"] == ["python"]
    assert result["unmatched_job_skills"] == ["kubernetes"]
    assert result["resume_extra_skills"] == ["docker"]


def test_matcher_full_flow():
    resume = "姓名：张三\n技能：Python、Django、MySQL"
    job = "【后端工程师】要求：Python、Django、MySQL、Redis"
    result = match_resume_job(resume, job)
    assert result["success"]
    assert result["skills_match"]["matched_count"] >= 3
    for s in result["skills_match"]["matched_skills"]:
        assert s == s.lower(), f"技能未 canonical: {s!r}"