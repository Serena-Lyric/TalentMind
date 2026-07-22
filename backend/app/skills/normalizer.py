def build_alias_map(skill_dict: list[dict]) -> dict[str, str]:
    """把 [{canonical, aliases[]}] 展平成 {小写别名/标准名: canonical}。"""
    m: dict[str, str] = {}
    for row in skill_dict:
        canon = row["canonical"]
        m[canon.lower()] = canon
        for a in row.get("aliases") or []:
            m[a.lower()] = canon
    return m

def normalize(raw: str, alias_map: dict[str, str]) -> str | None:
    if not raw:
        return None
    return alias_map.get(raw.strip().lower())
