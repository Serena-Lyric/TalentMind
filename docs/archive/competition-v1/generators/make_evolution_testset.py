"""时间演化测试集生成 —— 150 中文岗位 × 3 时间版本 = 450 条 JD。

- 岗位全部来自中文平台管道筛选结果(新一代/现有按 M2_final 分类)
- 版本 3 = 真实筛选出的 JD(原文一字不改,jd_id/crawled_at 可回查 state.db)
- 版本 1/2 = 演化回溯版:时间戳回拨、技能递减(按 confidence 升序=最新技能)、
  正文按证据句删减、变化说明标注每次变化
- 变化维度:技能(3 次变化,至少含技能变化)+ 时间(版本时间戳)
  薪资按用户决定不做
- 输出: exchange/M2_testset/ 新一代/现有 两份 + 测试方案说明.md
"""
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR  # noqa: E402

FINAL_DIR = Path("exchange/M2_final")
OUT_DIR = Path("exchange/M2_testset")
CN_PLATFORMS = {"boss", "zhaopin", "liepin"}
TOTAL = 150
MIN_SKILLS = 4      # 至少 4 技能才能做 3 次变化(4-3/4-2/4)
SENT_SPLIT = re.compile(r"(?<=[。！？；!?;])|\n")


def parse_dt(s: str) -> datetime | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def split_sentences(text: str) -> list[str]:
    parts = SENT_SPLIT.split(text)
    out, buf = [], ""
    for p in parts:
        buf += p
        if buf.strip():
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return out


def remove_evidence_sentences(text: str, anchors: list[str]) -> str:
    """删除包含证据锚点(技能原文引用)的句子,演化版正文。"""
    sents = split_sentences(text)
    kept = []
    removed_anchors = set()
    for s in sents:
        hit = None
        for a in anchors:
            key = (a or "")[:8].strip()
            if key and key in s:
                hit = key
                break
        if hit:
            removed_anchors.add(hit)
            continue
        kept.append(s)
    return "".join(kept)


def main():
    # ═══ 1. 中文平台岗位定义(M2_final,含分类) ═══
    defs = []
    for fname in ("新一代岗位_定义.json", "现有岗位_定义.json"):
        d = json.load(open(FINAL_DIR / fname, encoding="utf-8"))
        for x in d["items"]:
            if set(x.get("source", [])) & CN_PLATFORMS:
                defs.append(x)
    print(f"[测试集] 中文平台岗位定义 {len(defs)} 个")

    # ═══ 2. 真实记录(state.db s3_pass)按提取岗位名索引 ═══
    conn = sqlite3.connect(str(DATA_DIR / "state.db"))
    conn.row_factory = sqlite3.Row
    recs_by_name: dict[str, list[dict]] = {}
    for r in conn.execute(
            "SELECT id, job_title, crawled_at, raw_text, s3_json FROM records "
            "WHERE status='s3_pass' AND s3_json IS NOT NULL"):
        try:
            s3 = json.loads(r["s3_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        name = (s3.get("job_name") or "").strip()
        if not name:
            continue
        skills = s3.get("required_skills", []) + s3.get("bonus_skills", [])
        recs_by_name.setdefault(name, []).append({
            "id": r["id"], "job_title": r["job_title"],
            "crawled_at": r["crawled_at"], "raw_text": r["raw_text"],
            "job_name": name, "skills": skills,
        })
    print(f"        真实记录 {sum(len(v) for v in recs_by_name.values())} 条")

    # ═══ 3. 匹配:定义 -> 真实记录(取技能最多的那条) ═══
    norm = lambda s: re.sub(r"\s+", "", s or "").lower()
    candidates = []
    for d in defs:
        zh = d["job_name"]
        recs = recs_by_name.get(zh.strip()) or \
            [r for n, rs in recs_by_name.items()
             if norm(n) == norm(zh) for r in rs]
        if not recs:
            continue
        rec = max(recs, key=lambda r: len(r["skills"]))
        if len(rec["skills"]) < MIN_SKILLS:
            continue
        candidates.append({
            "def": d, "rec": rec,
            "n_skills": len(rec["skills"]),
        })
    print(f"        匹配且技能>={MIN_SKILLS} 的候选 {len(candidates)} 个")

    # ═══ 4. 按分类比例抽样 150(新一代:现有 = 池内比例) ═══
    from collections import Counter
    pool_cnt = Counter(d["category"] for d in defs)
    quota = {c: round(TOTAL * pool_cnt[c] / len(defs))
             for c in ("新一代", "现有")}
    # 修正取整误差
    quota["新一代"] += TOTAL - sum(quota.values())
    picked = []
    for cat in ("新一代", "现有"):
        cat_cands = sorted(
            [c for c in candidates if c["def"]["category"] == cat],
            key=lambda c: -c["n_skills"])
        picked.extend(cat_cands[:quota[cat]])
    print(f"        抽样 {len(picked)} 个(配额 {quota})")

    # ═══ 5. 生成 3 版本 ═══
    items = []
    for i, c in enumerate(picked, 1):
        d, rec = c["def"], c["rec"]
        skills = sorted(rec["skills"], key=lambda s: s.get("confidence", 0))
        # 最新技能 = confidence 最低的 3 个(时间演化:新增技能要求置信度渐升)
        newest = [s["name"] for s in skills[:3]]
        anchors = [(s.get("evidence") or "")[:12].strip()
                   for s in skills[:3] if (s.get("evidence") or "").strip()]
        v3_dt = parse_dt(rec["crawled_at"]) or datetime(2026, 8, 20)
        v2_dt = v3_dt - timedelta(days=120 + (i % 5) * 15)
        v1_dt = v3_dt - timedelta(days=240 + (i % 13) * 15)
        span_months = round((v3_dt - v1_dt).days / 30.0, 1)

        v3_text = rec["raw_text"]
        v2_text = remove_evidence_sentences(v3_text, anchors[:1]) \
            if anchors else v3_text
        v1_text = remove_evidence_sentences(v2_text, anchors[1:3]) \
            if anchors else v2_text

        # 标题演化:去括号限定词 = 早期版本
        base_title = rec["job_title"].strip()
        v1_title = re.sub(r"[（(][^（()）]*[)）]\s*$", "", base_title).strip() \
            or base_title

        all_names = [s["name"] for s in rec["skills"]]
        v2_names = [n for n in all_names if n not in newest[:1]]
        v1_names = [n for n in v2_names if n not in newest[1:3]]

        items.append({
            "job_type_id": f"t_{i:03d}",
            "job_name": d["job_name"],
            "job_name_zh": d["job_name"],
            "category": d["category"],
            "source": sorted(rec["job_name"] and d.get("source", [])),
            "versions": [
                {"version": 1, "jd_id": f"syn_t{i:03d}_v1",
                 "job_title": v1_title, "crawled_at": fmt_dt(v1_dt),
                 "raw_text": v1_text, "expected_skills": v1_names,
                 "change_note": ""},
                {"version": 2, "jd_id": f"syn_t{i:03d}_v2",
                 "job_title": base_title, "crawled_at": fmt_dt(v2_dt),
                 "raw_text": v2_text, "expected_skills": v2_names,
                 "change_note": f"新增技能要求:{newest[0]}"},
                {"version": 3, "jd_id": rec["id"],
                 "job_title": base_title, "crawled_at": rec["crawled_at"],
                 "raw_text": v3_text, "expected_skills": all_names,
                 "change_note": f"新增技能要求:{newest[1]}、{newest[2]}"},
            ],
            "time_span_months": span_months,
            "real_jd_id": rec["id"],
        })

    # ═══ 6. 输出两份 + 说明 ═══
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def wrap(ls):
        return {"schema_version": "1.0", "contract_version": "2026-08-31",
                "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "module": "m2", "items": ls}

    for cat in ("新一代", "现有"):
        cat_items = [x for x in items if x["category"] == cat]
        fname = f"{cat}岗位_时间演化测试集.json"
        json.dump(wrap(cat_items), open(OUT_DIR / fname, "w",
                                        encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"        {fname}: {len(cat_items)} 个岗位 × 3 版本")

    readme = """# 时间演化测试集说明

- 规模:150 种岗位 × 3 个时间版本 = 450 条 JD,全部来自中文平台
  (boss/zhaopin/liepin)管道筛选结果
- 分类:新一代(萌芽/兴起中)/ 现有(成熟/衰退),与岗位定义分类一致
- 时间线:版本 1 → 2 → 3 跨 8~14 个月,3 次变化,至少含技能变化
- 版本 3 = 真实筛选出的 JD:jd_id/raw_text/crawled_at 与 state.db 记录
  逐字一致,expected_skills 即管道真实提取的技能(真值)
- 版本 1/2 = 演化回溯版:时间戳回拨、技能按"最新技能(低置信度)"递减、
  正文按证据句删减(演示演化);变化真值以 expected_skills 与
  change_note 为准
- 用法:将各版本喂给管道,对比三个版本的提取结果,即可演示赛题②
  "既有岗位能力动态更新"(技能要求随时间变化 + 时间体现)
"""
    (OUT_DIR / "测试方案说明.md").write_text(readme, encoding="utf-8")
    print(f"[测试集] 完成 -> {OUT_DIR}")


if __name__ == "__main__":
    main()
