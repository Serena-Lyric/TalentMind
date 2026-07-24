import hashlib
import re


def text_signature(text: str) -> str:
    norm = re.sub(r"[\s,。.,、;;]+", "", text or "").lower()
    return hashlib.md5(norm.encode()).hexdigest()[:16]


def assign_dup_groups(rows: list[dict]) -> list[dict]:
    for r in rows:
        r["dup_group"] = text_signature(r.get("raw_text", ""))
    return rows


def quality_score(row: dict, group_size: int) -> float:
    text = row.get("raw_text", "")
    length_score = min(len(text) / 200, 1.0)
    multi_source = min(group_size / 3, 1.0)
    return round(0.6 * length_score + 0.4 * multi_source, 2)
