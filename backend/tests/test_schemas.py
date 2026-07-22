from app.models.schemas import SkillItem, MatchResult

def test_skillitem_has_confidence_evidence():
    s = SkillItem(skill_id=1, name="RAG", weight=0.3, confidence=0.9, evidence="JD第3段")
    assert s.name == "RAG" and s.confidence == 0.9

def test_matchresult_shape():
    m = MatchResult(target_job="AI应用工程师", score=82,
                    matched=["Python"], missing=["RAG"],
                    path=[{"from": "后端工程师", "to": "AI应用工程师", "gap": ["RAG"]}])
    assert m.score == 82 and m.missing == ["RAG"]
