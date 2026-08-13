"""技能 canonical 归一（D31）：对齐 backend/app/skills/skill_dict_seed.json。"""
import json
from pathlib import Path

_SEED_PATH = Path(__file__).resolve().parents[1] / "skills" / "skill_dict_seed.json"
_CACHE: tuple[set[str], dict[str, str]] | None = None


def _load() -> tuple[set[str], dict[str, str]]:
    global _CACHE
    if _CACHE is None:
        with open(_SEED_PATH, "r", encoding="utf-8") as f:
            entries = json.load(f)
        canonicals = {e["canonical"] for e in entries}
        aliases = {}
        for e in entries:
            for a in e["aliases"]:
                aliases[a.lower()] = e["canonical"]
        _CACHE = (canonicals, aliases)
    return _CACHE


def to_canonical(name: str) -> str:
    """技能名 → canonical（小写）；未命中返回小写原名。"""
    canonicals, aliases = _load()
    n = name.strip().lower()
    if n in aliases:
        return aliases[n]
    if n in canonicals:
        return n
    return n
