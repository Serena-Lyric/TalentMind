"""BOSS 低速持续采集循环。

每次只处理一个关键词/城市组合，完成后在较长的随机间隔后切换到下一个组合。
随机间隔用于降低访问密度和避免固定节奏，不用于绕过登录、验证码或反爬机制。

示例：
  python -m app.collect.boss_collect_loop --forever \
    --cdp http://127.0.0.1:9333 \
    --user-data-dir C:/path/to/edge-profile
"""
from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

from app.collect.fetch_boss_jobs import _parse_cities, _split_csv, run_fetch
from app.collect.fetchers.cdp import CdpError


DEFAULT_KEYWORDS = (
    "Python",
    "Java",
    "数据分析",
    "后端工程师",
    "数据工程师",
    "AI工程师",
    "机器学习",
    "产品经理",
)
DEFAULT_CITIES = (
    ("北京", "101010100"),
    ("上海", "101020100"),
    ("深圳", "101280600"),
)


@dataclass(frozen=True)
class QueryTarget:
    keyword: str
    city_name: str
    city_code: str


def build_targets(
    keywords: Iterable[str], cities: Iterable[tuple[str, str]]
) -> list[QueryTarget]:
    """按关键词/城市笛卡尔积生成稳定轮换序列。"""
    targets = [
        QueryTarget(keyword.strip(), city_name.strip(), city_code.strip())
        for keyword in keywords
        for city_name, city_code in cities
        if keyword.strip() and city_name.strip() and city_code.strip()
    ]
    if not targets:
        raise ValueError("至少需要一个有效的关键词和城市")
    return targets


def _validate_range(lower: float, upper: float) -> None:
    if lower < 0 or upper < lower:
        raise ValueError("时间范围必须满足 0 <= lower <= upper")


def _sample_seconds(rng: random.Random, lower: float, upper: float) -> float:
    _validate_range(lower, upper)
    return lower if lower == upper else rng.uniform(lower, upper)


def _log(message: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


def run_loop(
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
    sleeper: Callable[[float], None] = time.sleep,
    fetcher: Callable[..., dict] = run_fetch,
    rng: random.Random | None = None,
) -> int:
    """持续轮换采集；rounds=0 表示不设轮数上限。"""
    if not targets:
        raise ValueError("targets 不能为空")
    if rounds < 0:
        raise ValueError("rounds 不能为负数")
    for lower, upper in (
        (page_delay_min, page_delay_max),
        (settle_min, settle_max),
        (switch_interval_min, switch_interval_max),
    ):
        _validate_range(lower, upper)

    rng = rng or random.Random()
    round_index = 0
    while rounds == 0 or round_index < rounds:
        target = targets[round_index % len(targets)]
        round_index += 1
        page_delay = _sample_seconds(rng, page_delay_min, page_delay_max)
        settle = _sample_seconds(rng, settle_min, settle_max)
        _log(
            f"BOSS 第 {round_index} 轮开始: {target.city_name}/{target.keyword}; "
            f"pages={pages}, detail_limit={detail_limit}, page_delay={page_delay:.1f}s, settle={settle:.1f}s"
        )
        try:
            result = fetcher(
                [target.keyword],
                [(target.city_name, target.city_code)],
                cdp_endpoint=cdp_endpoint,
                user_data_dir=user_data_dir,
                pages=pages,
                detail_limit=detail_limit,
                max_jobs=max_jobs,
                delay=page_delay,
                settle=settle,
            )
            _log(f"BOSS 第 {round_index} 轮完成: {result}")
        except CdpError as exc:
            _log(f"BOSS CDP/登录状态异常，停止循环: {exc}")
            return 2
        except Exception as exc:
            _log(f"BOSS 第 {round_index} 轮异常，继续低频重试: {exc!r}")

        if rounds and round_index >= rounds:
            break
        interval = _sample_seconds(rng, switch_interval_min, switch_interval_max)
        _log(f"等待 {interval:.1f}s 后切换下一个关键词/城市")
        sleeper(interval)

    _log("BOSS 低速持续采集循环结束")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BOSS 直聘低速持续采集（人工登录 Edge + CDP）")
    parser.add_argument("--keywords", default=",".join(DEFAULT_KEYWORDS), help="逗号分隔关键词")
    parser.add_argument(
        "--cities",
        default=",".join(f"{name}={code}" for name, code in DEFAULT_CITIES),
        help="城市代码，例如 北京=101010100,上海=101020100",
    )
    parser.add_argument("--cdp", default="http://127.0.0.1:9333", help="CDP 地址")
    parser.add_argument("--user-data-dir", default=None, help="Edge 用户目录；可用于动态发现 CDP 端口")
    parser.add_argument("--pages", type=int, default=1, help="每个关键词/城市最多翻页数")
    parser.add_argument("--detail-limit", type=int, default=8, help="每轮最多补采详情数")
    parser.add_argument("--max-jobs", type=int, default=12, help="每轮最多入库岗位数")
    parser.add_argument("--page-delay-min", type=float, default=15.0, help="列表/详情页面间最小等待秒数")
    parser.add_argument("--page-delay-max", type=float, default=30.0, help="列表/详情页面间最大等待秒数")
    parser.add_argument("--settle-min", type=float, default=5.0, help="页面加载后最小等待秒数")
    parser.add_argument("--settle-max", type=float, default=10.0, help="页面加载后最大等待秒数")
    parser.add_argument("--switch-interval-min", type=float, default=360.0, help="切换关键词/城市的最小间隔秒数")
    parser.add_argument("--switch-interval-max", type=float, default=720.0, help="切换关键词/城市的最大间隔秒数")
    parser.add_argument("--rounds", type=int, default=0, help="采集轮数；0 表示不间断运行")
    parser.add_argument("--forever", action="store_true", help="不间断运行（默认行为，便于命令自述）")
    parser.add_argument("--once", action="store_true", help="只采一轮，便于连通性验证")
    parser.add_argument("--seed", type=int, default=None, help="可选随机种子，仅用于测试/复现节奏")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.once:
        args.rounds = 1
    if args.pages < 1 or args.detail_limit < 0 or args.max_jobs < 0:
        raise SystemExit("pages 必须 >= 1，detail-limit/max-jobs 不能为负数")
    keywords = _split_csv(args.keywords)
    cities = _parse_cities(args.cities)
    targets = build_targets(keywords, cities)
    return run_loop(
        targets,
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
        rng=random.Random(args.seed),
    )


if __name__ == "__main__":
    raise SystemExit(main())