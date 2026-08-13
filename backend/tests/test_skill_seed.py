"""校验 skill_dict 种子文件（决策 D31）：canonical 唯一、aliases 无冲突、数量达标。"""
import json
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[1] / "app" / "skills" / "skill_dict_seed.json"


def _load_seed():
    assert SEED_PATH.exists(), f"缺少种子文件: {SEED_PATH}"
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_seed_is_list_of_entries():
    seed = _load_seed()
    assert isinstance(seed, list) and len(seed) >= 200
    for item in seed:
        assert item.get("canonical")
        assert isinstance(item.get("aliases"), list)
        assert item.get("category")


def test_canonical_unique():
    seed = _load_seed()
    names = [x["canonical"] for x in seed]
    assert len(names) == len(set(names))


def test_aliases_no_conflict():
    """同一 alias 不得映射到两个 canonical。"""
    seed = _load_seed()
    mapping = {}
    for x in seed:
        for a in x["aliases"]:
            assert a not in mapping or mapping[a] == x["canonical"], \
                f"alias 冲突: {a!r}"
            mapping[a] = x["canonical"]


def test_aliases_unique_within_entry():
    seed = _load_seed()
    for x in seed:
        assert len(x["aliases"]) == len(set(x["aliases"]))