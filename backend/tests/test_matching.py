"""M4 简历匹配模块测试：技能提取、canonical 化（D31）、加权匹配输出。"""
from app.matching.skill_extractor import extract_skills, normalize_skill
from app.matching.matcher import quick_match_weighted
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


def test_quick_match_weighted_canonical_output():
    result = quick_match_weighted(["Python", "Docker"], ["Python", "Kubernetes"])
    assert result["matched_skills"] == ["python"]
    assert result["unmatched_job_skills"] == ["kubernetes"]
    assert result["resume_extra_skills"] == ["docker"]


def test_quick_match_weighted_keeps_required_and_bonus_separate():
    # 必备/加分重叠只计必备；加分缺口不计入必备数量。
    result = quick_match_weighted(["K8s"], ["Kubernetes", "k8s"], ["K8S", "Docker"])
    assert result["matched_skills"] == ["kubernetes"]
    assert result["unmatched_job_skills"] == ["docker"]
    assert result["job_required_count"] == 1
