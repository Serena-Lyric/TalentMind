"""多源交叉验证质量分（D42）：跨来源（linkedin/hn）同岗位比对。

规则（明确定义，不臆造数字）：
- normalize_title：小写、去标点/括号、压缩空格；
- hn 标题按 | — - · 分段，与 linkedin 归一化标题做"包含/被包含"匹配（长度>=4）；
- 命中跨源的 jd_pool 行标记 cross_source=1，quality 上浮为 MAX(原 quality, 0.85)
  （0.85 = 多源一致置信下界，写入决策跟踪/计划文档）；
- --dry-run 只分析不写库。

用法:
  python -m app.collect.cross_validate            # 分析 + 写库
  python -m app.collect.cross_validate --dry-run  # 只分析
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[3]

CROSS_SOURCE_FLOOR = 0.85
_SEP_RE = re.compile(r"[|\u2014\u2013\u00b7\-]")


def normalize_title(s: str) -> str:
    t = (s or "").lower()
    t = re.sub(r"[\(\)\[\]{}]", " ", t)
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def hn_segments(title: str) -> list[str]:
    """HN 标题按分隔符分段：仅保留 >=2 词、长度>=6 的段（避免 'engineer'/'manager' 等单段误匹配）。"""
    segs = [normalize_title(x) for x in _SEP_RE.split(title or "")]
    return [x for x in segs if len(x) >= 6 and " " in x]


def _is_match(a: str, b: str) -> bool:
    """双向包含 + 长度比>=0.6（避免 'engineer' 子串命中长标题的低质量匹配）。"""
    if not a or not b or len(a) < 6 or len(b) < 6:
        return False
    if " " not in a and " " not in b:
        return False
    shorter, longer = sorted((a, b), key=len)
    return shorter in longer and len(shorter) / len(longer) >= 0.6


def main():
    parser = argparse.ArgumentParser(description="多源交叉验证质量分（D42）")
    parser.add_argument("--dry-run", action="store_true", help="只分析不写库")
    args = parser.parse_args()

    from app.db.mysql import get_db
    db = next(get_db())
    try:
        ln = db.execute(text(
            "SELECT id, job_title, quality FROM jd_pool "
            "WHERE source='linkedin' AND status='cleaned'"
        )).mappings().all()
        hn = db.execute(text(
            "SELECT id, job_title, quality FROM jd_pool "
            "WHERE source='hn' AND status='cleaned'"
        )).mappings().all()
    finally:
        db.close()

    ln_norm = [(r["id"], normalize_title(r["job_title"])) for r in ln]
    ln_by_id = {r["id"]: r for r in ln}
    hn_by_id = {r["id"]: r for r in hn}
    matches: list[tuple[int, int]] = []
    for r in hn:
        segs = hn_segments(r["job_title"])
        for seg in segs:
            for lid, lnt in ln_norm:
                if _is_match(seg, lnt):
                    matches.append((r["id"], lid))
                    break
            else:
                continue
            break

    hit_ids = set()
    for hid, lid in matches:
        hit_ids.add(hid)
        hit_ids.add(lid)

    if not args.dry_run and hit_ids:
        params = [{"i": i, "f": CROSS_SOURCE_FLOOR} for i in hit_ids]
        for j in range(0, len(params), 500):
            db.execute(text(
                "UPDATE jd_pool SET cross_source=1, "
                "quality=ROUND(GREATEST(quality, :f), 3) WHERE id=:i"
            ), params[j:j + 500])
            db.commit()
        print(f"[cross_validate] 更新 {len(hit_ids)} 行 cross_source=1, "
              f"quality=MAX(quality,{CROSS_SOURCE_FLOOR})")

    # 报告
    report_path = REPO_ROOT / "exchange" / "m1" / "cross_validate_report.md"
    lines = [
        "# M1 多源交叉验证报告（D42，2026-08-17）",
        "",
        f"- 数据：linkedin {len(ln)} × hn {len(hn)}（均 cleaned）",
        f"- 匹配规则：normalize_title + hn 段（≥2 词、≥6 字符）↔ linkedin 双向包含 + 长度比 ≥0.6",
        f"- 结果：匹配 {len(matches)} 对；hn 命中率 {len(matches) / max(len(hn), 1):.1%}",
        f"- 命中行：cross_source=1 共 {len(hit_ids)} 行（hn {sum(1 for i in hit_ids if i in hn_by_id)} + linkedin {sum(1 for i in hit_ids if i in ln_by_id)}）",
        f"- quality 上浮：MAX(原 quality, {CROSS_SOURCE_FLOOR})（多源一致置信下界）",
        "",
        "| hn id | linkedin id | hn 标题 | linkedin 标题 |",
        "|---|---|---|---|",
    ]
    for hid, lid in matches[:20]:
        lines.append(f"| {hid} | {lid} | {hn_by_id[hid]['job_title'][:50]} | {ln_by_id[lid]['job_title'][:50]} |")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"linkedin={len(ln)} hn={len(hn)} 匹配对={len(matches)}")
    print(f"报告: {report_path}")
    for m in matches[:10]:
        hid, lid = m
        print(f"  hn#{hid} <-> linkedin#{lid}: [{hn_by_id[hid]['job_title'][:50]}] <=> [{ln_by_id[lid]['job_title'][:50]}]")


if __name__ == "__main__":
    main()
