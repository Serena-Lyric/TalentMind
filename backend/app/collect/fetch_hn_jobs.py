"""CLI：抓取 HN 'Who is hiring' 岗位写入 jd_pool（D40 多源岗位）。

用法:
  python -m app.collect.fetch_hn_jobs               # 全部
  python -m app.collect.fetch_hn_jobs --limit 50    # 只取前 50 条
幂等：当日同 source 先清后写（与 fetch_signals 一致）。
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone

import httpx
from sqlalchemy import text


def run_fetch(limit: int = 0, months: int = 0) -> int:
    """抓取当月及历史 N 个月 HN Who-is-hiring 岗位写入 jd_pool（幂等：当日同 source 先清后写）。返回入库条数。"""
    client = httpx.Client(timeout=30, follow_redirects=True, verify=False)
    try:
        from app.collect.fetchers.hn_hiring import fetch_hn_hiring_rawjds
        print(f"[fetch_hn_jobs] 抓取 HN Who is hiring（当月 + 前 {months} 个月）...")
        raws, posts = fetch_hn_hiring_rawjds(client, limit=limit, months_back=months)
    finally:
        client.close()

    if not raws:
        print("[fetch_hn_jobs] 未找到帖子或评论为空")
        return 0

    from app.db.mysql import get_db
    from app.collect.pipeline import run_pipeline

    db = next(get_db())
    try:
        # 当日同源先清后写（幂等；历史帖也会被重新抓取，不产生重复）
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        db.execute(text("DELETE FROM jd_pool WHERE source='hn' AND DATE(crawled_at)=:d"),
                   {"d": today})
        db.commit()
        stats = run_pipeline(db, raws)
        print(f"[fetch_hn_jobs] 抓取 {len(raws)} 条评论（{len(posts)} 个帖），"
              f"入库 {stats['jd_saved']} 条（source=hn）")
        return int(stats["jd_saved"])
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="HN Who-is-hiring 岗位采集（D40）")
    parser.add_argument("--limit", type=int, default=0, help="抓取条数上限（0=全部）")
    parser.add_argument("--months", type=int, default=0,
                        help="额外抓取历史月份数（0=仅当月；如 5=当月+前5个月）")
    args = parser.parse_args()
    run_fetch(args.limit, args.months)


if __name__ == "__main__":
    main()
