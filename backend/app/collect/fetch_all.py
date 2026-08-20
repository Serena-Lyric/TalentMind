"""一键执行全部采集任务（信号 + HN，可选 BOSS 登录浏览器）。

用法:
  python -m app.collect.fetch_all
  python -m app.collect.fetch_all --skip-signals   # 只抓 HN 岗位
  python -m app.collect.fetch_all --skip-hn        # 只抓信号
  python -m app.collect.fetch_all --boss --boss-keywords Python --boss-cities 北京=101010100
"""
from __future__ import annotations
import argparse


def main():
    parser = argparse.ArgumentParser(description="一键执行全部采集（信号 + HN，可选 BOSS）")
    parser.add_argument("--skip-signals", action="store_true", help="跳过信号采集")
    parser.add_argument("--skip-hn", action="store_true", help="跳过 HN 岗位采集")
    parser.add_argument("--hn-limit", type=int, default=0, help="HN 抓取条数上限（0=全部）")
    parser.add_argument("--boss", action="store_true", help="启用 BOSS 采集（需要已登录的 Chrome CDP）")
    parser.add_argument("--boss-keywords", default="", help="BOSS 关键词，逗号分隔")
    parser.add_argument("--boss-cities", default="", help="BOSS 城市，格式 北京=101010100,上海=101020100")
    parser.add_argument("--boss-cdp", default="http://127.0.0.1:9222", help="BOSS Chrome CDP 地址")
    parser.add_argument("--boss-pages", type=int, default=5, help="每个 BOSS 关键词/城市最多翻页数")
    parser.add_argument("--boss-detail-limit", type=int, default=100, help="BOSS 最多补采详情数")
    args = parser.parse_args()

    if not args.skip_signals:
        from app.collect.fetch_signals import run_fetch as run_signals
        run_signals(["github", "blog"])
    if not args.skip_hn:
        from app.collect.fetch_hn_jobs import run_fetch as run_hn
        run_hn(args.hn_limit)
    if args.boss:
        if not args.boss_keywords or not args.boss_cities:
            parser.error("--boss 必须同时提供 --boss-keywords 和 --boss-cities")
        from app.collect.fetch_boss_jobs import _parse_cities, _split_csv, run_fetch as run_boss
        run_boss(
            _split_csv(args.boss_keywords),
            _parse_cities(args.boss_cities),
            cdp_endpoint=args.boss_cdp,
            pages=args.boss_pages,
            detail_limit=args.boss_detail_limit,
        )
    if not args.skip_hn or args.boss:
        # 岗位源刷新后重算既有 LinkedIn/HN 多源交叉验证。
        from app.collect.cross_validate import run as run_cv
        run_cv(dry_run=False)
    print("[fetch_all] 全部采集任务完成")


if __name__ == "__main__":
    main()
