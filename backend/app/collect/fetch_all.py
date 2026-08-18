"""CLI：一键执行全部采集任务（信号 + HN 岗位），D41。

用法:
  python -m app.collect.fetch_all
  python -m app.collect.fetch_all --skip-signals   # 只抓 HN 岗位
  python -m app.collect.fetch_all --skip-hn        # 只抓信号
"""
from __future__ import annotations
import argparse


def main():
    parser = argparse.ArgumentParser(description="一键执行全部采集（D41）")
    parser.add_argument("--skip-signals", action="store_true", help="跳过信号采集")
    parser.add_argument("--skip-hn", action="store_true", help="跳过 HN 岗位采集")
    parser.add_argument("--hn-limit", type=int, default=0, help="HN 抓取条数上限（0=全部）")
    args = parser.parse_args()

    if not args.skip_signals:
        from app.collect.fetch_signals import run_fetch as run_signals
        run_signals(["github", "blog"])
    if not args.skip_hn:
        from app.collect.fetch_hn_jobs import run_fetch as run_hn
        run_hn(args.hn_limit)
        # hn 刷新后重算多源交叉验证，保持 cross_source 标记与当前 jd_pool 一致
        from app.collect.cross_validate import run as run_cv
        run_cv(dry_run=False)
    print("[fetch_all] 全部采集任务完成")


if __name__ == "__main__":
    main()
