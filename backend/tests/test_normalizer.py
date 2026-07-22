from app.skills.normalizer import normalize, build_alias_map

DICT = [
    {"canonical": "Kubernetes", "aliases": ["K8s", "k8s"]},
    {"canonical": "Python", "aliases": []},
]

def test_alias_maps_to_canonical():
    m = build_alias_map(DICT)
    assert normalize("k8s", m) == "Kubernetes"
    assert normalize("K8S", m) == "Kubernetes"   # 大小写不敏感

def test_canonical_itself():
    m = build_alias_map(DICT)
    assert normalize("Python", m) == "Python"

def test_unknown_returns_none():
    m = build_alias_map(DICT)
    assert normalize("COBOL", m) is None
