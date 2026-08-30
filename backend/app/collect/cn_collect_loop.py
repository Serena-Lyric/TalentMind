"""智联/猎聘低速循环。每轮只处理一个关键词/城市组合。"""
from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from app.collect.fetch_cn_jobs import parse_cities, run_fetch, split_csv
from app.collect.fetchers.cdp import CdpError
from app.collect.fetchers.job_sites import SITES


@dataclass(frozen=True)
class QueryTarget:
    keyword: str
    city_name: str
    city_code: str


def build_targets(keywords: list[str], cities: list[tuple[str, str]]) -> list[QueryTarget]:
    targets = [
        QueryTarget(keyword.strip(), name.strip(), code.strip())
        for keyword in keywords
        for name, code in cities
        if keyword.strip() and name.strip() and code.strip()
    ]
    if not targets:
        raise ValueError("至少需要一个有效的关键词和城市")
    return targets


def run_loop(
    platform: str,
    targets: list[QueryTarget],
    *,
    cdp_endpoint: str,
    user_data_dir: str | None,
    pages: int = 1,
    detail_limit: int = 8,
    max_jobs: int = 12,
    page_delay_min: float = 15.0,
    page_delay_max: float = 30.0,
    settle_min: float = 5.0,
    settle_max: float = 10.0,
    switch_interval_min: float = 360.0,
    switch_interval_max: float = 720.0,
    rounds: int = 0,
    search_url_template: str | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    fetcher: Callable[..., dict] = run_fetch,
    rng: random.Random | None = None,
) -> int:
    if platform not in SITES:
        raise ValueError(f"不支持的平台: {platform}")
    if not targets or rounds < 0:
        raise ValueError("targets 不能为空，rounds 不能为负数")
    ranges = ((page_delay_min, page_delay_max), (settle_min, settle_max), (switch_interval_min, switch_interval_max))
    if any(lower < 0 or upper < lower for lower, upper in ranges):
        raise ValueError("时间范围必须满足 0 <= lower <= upper")
    rng = rng or random.Random()
    index = 0
    while rounds == 0 or index < rounds:
        target = targets[index % len(targets)]
        index += 1
        page_delay = rng.uniform(page_delay_min, page_delay_max)
        settle = rng.uniform(settle_min, settle_max)
        print(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {platform} 第 {index} 轮开始: "
            f"{target.city_name}/{target.keyword}; pages={pages}, detail_limit={detail_limit}",
            flush=True,
        )
        try:
            result = fetcher(
                platform,
                [target.keyword],
                [(target.city_name, target.city_code)],
                cdp_endpoint=cdp_endpoint,
                user_data_dir=user_data_dir,
                pages=pages,
                detail_limit=detail_limit,
                max_jobs=max_jobs,
                delay=page_delay,
                settle=settle,
                search_url_template=search_url_template,
            )
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {platform} 第 {index} 轮完成: {result}", flush=True)
        except CdpError as exc:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {platform} CDP/登录状态异常，停止循环: {exc}", flush=True)
            return 2
        except Exception as exc:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {platform} 第 {index} 轮异常，继续低频重试: {exc!r}", flush=True)
        if rounds and index >= rounds:
            break
        interval = rng.uniform(switch_interval_min, switch_interval_max)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 等待 {interval:.1f}s 后切换下一个关键词/城市", flush=True)
        sleeper(interval)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="智联/猎聘低速页面采集循环")
    parser.add_argument("--platform", choices=sorted(SITES), required=True)
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--cities", required=True)
    parser.add_argument("--cdp", default="http://127.0.0.1:9333")
    parser.add_argument("--user-data-dir", default=None)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--detail-limit", type=int, default=8)
    parser.add_argument("--max-jobs", type=int, default=12)
    parser.add_argument("--page-delay-min", type=float, default=15.0)
    parser.add_argument("--page-delay-max", type=float, default=30.0)
    parser.add_argument("--settle-min", type=float, default=5.0)
    parser.add_argument("--settle-max", type=float, default=10.0)
    parser.add_argument("--switch-interval-min", type=float, default=360.0)
    parser.add_argument("--switch-interval-max", type=float, default=720.0)
    parser.add_argument("--rounds", type=int, default=0)
    parser.add_argument("--forever", action="store_true", help="不间断运行（默认行为）")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--search-url-template", default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if args.once:
        args.rounds = 1
    if args.pages < 1 or args.detail_limit < 0 or args.max_jobs < 0:
        raise SystemExit("pages 必须 >=1，detail-limit/max-jobs 不能为负数")
    return run_loop(
        args.platform,
        build_targets(split_csv(args.keywords), parse_cities(args.cities)),
        cdp_endpoint=args.cdp,
        user_data_dir=args.user_data_dir,
        pages=args.pages,
        detail_limit=args.detail_limit,
        max_jobs=args.max_jobs,
        page_delay_min=args.page_delay_min,
        page_delay_max=args.page_delay_max,
        settle_min=args.settle_min,
        settle_max=args.settle_max,
        switch_interval_min=args.switch_interval_min,
        switch_interval_max=args.switch_interval_max,
        rounds=args.rounds,
        search_url_template=args.search_url_template,
        rng=random.Random(args.seed),
    )


if __name__ == "__main__":
    raise SystemExit(main())
