"""CLI：抓取多源信号写入 signal 表（D39 多源采集）。

用法:
  python -m app.collect.fetch_signals                # 默认 github,blog
  python -m app.collect.fetch_signals --sources blog # 只抓 RSS
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone

import httpx
from sqlalchemy import text


def run_fetch(sources: list[str]) -> int:
    """抓取指定来源信号并写入 signal 表（D44：追加式时间序列，每次运行生成一个时间点快照）。

    不再"当日先清后写"：signal 为轻量计数，追加可形成多时间点序列（captured_at 不同），
    供 M2 evolution 趋势；如需清理历史可手动 DELETE。
    """
    client = httpx.Client(timeout=20, follow_redirects=True, verify=False)  # 本机无系统证书链，公网抓取关闭校验
    all_signals = []
    try:
        if "github" in sources:
            from app.collect.fetchers.trending import fetch_trending_signals
            print("[fetch_signals] 抓取 GitHub Trending...")
            all_signals += fetch_trending_signals(client)
        if "blog" in sources:
            from app.collect.fetchers.blog_rss import fetch_blog_signals
            print("[fetch_signals] 抓取技术博客 RSS...")
            all_signals += fetch_blog_signals(client)
    finally:
        client.close()

    from app.db.mysql import get_db
    from app.collect.repository import save_signals

    db = next(get_db())
    try:
        n = save_signals(db, all_signals)
        print(f"[fetch_signals] 写入 {n} 条 signal（sources={sources}，追加式）")
        return n
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="抓取多源信号写入 signal 表（D39）")
    parser.add_argument("--sources", default="github,blog",
                        help="逗号分隔来源: github,blog")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    if not sources:
        print("[fetch_signals] 未指定来源")
        return
    run_fetch(sources)


if __name__ == "__main__":
    main()
