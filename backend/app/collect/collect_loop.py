"""持续采集循环（D44）：每隔 N 小时执行一次 fetch_all，累计 signal 时间序列与 HN/信号数据。

不依赖 Windows 计划任务（该环境下 SYSTEM 任务自动触发不可靠，2026-08-18 实测 02:00 未运行）。

用法:
  python -m app.collect.collect_loop --hours 6 --rounds 4    # 每 6 小时一次，共 4 轮
  python -m app.collect.collect_loop --hours 24 --forever   # 每 24 小时一次，无限循环
"""
from __future__ import annotations
import argparse
import time
from datetime import datetime


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="持续采集循环（D44）")
    parser.add_argument("--hours", type=float, default=6.0, help="每轮间隔小时数")
    parser.add_argument("--rounds", type=int, default=4, help="轮数（--forever 时忽略）")
    parser.add_argument("--forever", action="store_true", help="无限循环")
    args = parser.parse_args()

    from app.collect.fetch_signals import run_fetch as run_signals
    from app.collect.fetch_hn_jobs import run_fetch as run_hn

    round_i = 0
    while True:
        round_i += 1
        _log(f"=== 第 {round_i} 轮采集开始 ===")
        try:
            run_signals(["github", "blog"])
        except Exception as e:
            _log(f"signal 采集异常: {e}")
        try:
            run_hn(0)
        except Exception as e:
            _log(f"hn 采集异常: {e}")
        try:
            from app.collect.cross_validate import run as run_cv
            run_cv(dry_run=False)
        except Exception as e:
            _log(f"交叉验证异常: {e}")
        _log(f"=== 第 {round_i} 轮完成 ===")
        if not args.forever and round_i >= args.rounds:
            break
        _log(f"等待 {args.hours}h 后下一轮...")
        time.sleep(args.hours * 3600)
    _log("循环结束")


if __name__ == "__main__":
    main()
