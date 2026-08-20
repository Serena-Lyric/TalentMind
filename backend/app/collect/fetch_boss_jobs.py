"""BOSS 直聘岗位采集（用户登录浏览器 + CDP，不绕过验证码/反爬）。

示例：
  python -m app.collect.fetch_boss_jobs --keywords Python,后端工程师 --cities 北京=101010100 --pages 10
"""
from __future__ import annotations

import argparse
import time
import urllib.parse
from datetime import datetime, timezone

from sqlalchemy import text

from app.collect.fetchers.boss import deduplicate_jobs, normalize_boss_job
from app.collect.fetchers.cdp import CdpClient, CdpError
from app.collect.pipeline import run_pipeline

SEARCH_URL = "https://www.zhipin.com/web/geek/jobs"

SEARCH_EXTRACT_JS = r"""
(() => {
  const text = (node) => (node?.innerText || node?.textContent || '').replace(/\s+/g, ' ').trim();
  const first = (root, selectors) => {
    for (const selector of selectors) {
      const node = root.querySelector(selector);
      if (node && text(node)) return text(node);
    }
    return '';
  };
  const anchors = [...document.querySelectorAll('a[href*="/job_detail/"]')];
  const seen = new Set();
  return anchors.map((anchor) => {
    const url = new URL(anchor.href, location.origin).href;
    const card = anchor.closest('.job-card-wrapper, .job-card-box, .job-card, .job-list-box, li') || anchor.parentElement;
    const tags = [...(card?.querySelectorAll('.tag-list .tag, .job-card-left .tag, .job-limit .tag, .tag') || [])]
      .map(text).filter(Boolean);
    return {
      url,
      title: first(card || anchor, ['.job-name', '.job-title', '.job-card-left .name']) || text(anchor),
      salary: first(card || anchor, ['.salary', '.job-salary']),
      location: first(card || anchor, ['.job-area', '.job-location', '.job-card-left .job-area']),
      company: first(card || anchor, ['.company-name', '.company-text', '.company-name-text']),
      company_scale: first(card || anchor, ['.company-size', '.company-scale']),
      company_stage: first(card || anchor, ['.company-stage']),
      industry: first(card || anchor, ['.company-tag', '.company-industry']),
      tags,
      welfare: [...(card?.querySelectorAll('.福利, .welfare-list .tag, .benefits .tag') || [])].map(text).filter(Boolean),
    };
  }).filter((job) => {
    const path = new URL(job.url, location.origin).pathname;
    if (!job.url || path === '/job_detail/' || !job.title || seen.has(job.url)) return false;
    seen.add(job.url);
    return true;
  });
})()
"""

DETAIL_EXTRACT_JS = r"""
(() => {
  const text = (node) => (node?.innerText || node?.textContent || '').replace(/\s+/g, ' ').trim();
  const first = (selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      if (node && text(node)) return text(node);
    }
    return '';
  };
  return {
    url: location.href,
    title: first(['.job-name', '.job-title']),
    company: first(['.company-info .name', '.company-name', '.info-company .name']),
    salary: first(['.salary', '.job-salary']),
    location: first(['.job-location', '.job-area']),
    experience: first(['.job-limit .tag:nth-child(1)', '.job-limit']),
    degree: first(['.job-limit .tag:nth-child(2)']),
    description: first(['.job-sec-text', '.job-detail', '.job-description', '.job-detail-section']),
    company_info: first(['.job-sec.company-info', '.company-info .desc', '.company-info']),
  };
})()
"""


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_cities(value: str) -> list[tuple[str, str]]:
    cities = []
    for token in _split_csv(value):
        if "=" in token:
            name, code = token.split("=", 1)
        else:
            name, code = token, token
        name, code = name.strip(), code.strip()
        if not code.isdigit():
            raise ValueError(f"城市必须使用 BOSS 城市代码，例如 北京=101010100：{token}")
        cities.append((name or code, code))
    return cities


def _search_url(keyword: str, city_code: str, page: int) -> str:
    query = urllib.parse.urlencode({"city": city_code, "query": keyword, "page": page})
    return f"{SEARCH_URL}?{query}"


def _looks_like_login_page(client: CdpClient) -> bool:
    state = client.evaluate(
        "JSON.stringify({url: location.href, text: (document.body?.innerText || '').slice(0, 2000)})"
    )
    if isinstance(state, str):
        import json
        state = json.loads(state)
    url = str(state.get("url", ""))
    body = str(state.get("text", ""))
    has_job_cards = bool(client.evaluate("document.querySelector('a[href*=\\\"/job_detail/\\\"], .job-card-wrapper, .job-card-box')"))
    return "/user/login" in url or ("登录" in body and not has_job_cards)


def _fetch_search_page(client: CdpClient, url: str, settle: float) -> list[dict]:
    client.navigate(url, settle_seconds=settle)
    # BOSS 页面先渲染空壳，岗位卡片可能晚于 document.readyState 出现；
    # 在有限窗口内轮询，避免只抓到“职位搜索”占位链接或过早返回空页。
    deadline = time.monotonic() + max(5.0, settle * 2.0)
    latest: list[dict] = []
    while True:
        value = client.evaluate(SEARCH_EXTRACT_JS)
        latest = [job for job in value if isinstance(job, dict)] if isinstance(value, list) else []
        if latest or time.monotonic() >= deadline:
            return latest
        time.sleep(0.5)


def run_fetch(
    keywords: list[str],
    cities: list[tuple[str, str]],
    *,
    cdp_endpoint: str = "http://127.0.0.1:9222",
    user_data_dir: str | None = None,
    pages: int = 5,
    detail_limit: int = 100,
    max_jobs: int = 0,
    delay: float = 2.0,
    settle: float = 2.0,
    no_details: bool = False,
) -> dict:
    if not keywords or not cities:
        raise ValueError("至少需要一个关键词和一个城市")
    if pages < 1 or detail_limit < 0 or max_jobs < 0 or delay < 0:
        raise ValueError("pages/detail_limit/max_jobs/delay 不能为负数")

    client = CdpClient.connect_first_page(cdp_endpoint, user_data_dir=user_data_dir, target_url_contains="zhipin.com")
    collected: list[dict] = []
    try:
        for keyword in keywords:
            for city_name, city_code in cities:
                consecutive_empty = 0
                for page in range(1, pages + 1):
                    url = _search_url(keyword, city_code, page)
                    jobs = _fetch_search_page(client, url, settle)
                    if not jobs:
                        if _looks_like_login_page(client):
                            raise CdpError("当前页面需要 BOSS 登录或触发验证，请在浏览器中人工处理后重试")
                        consecutive_empty += 1
                        if consecutive_empty >= 2:
                            break
                    else:
                        consecutive_empty = 0
                        collected.extend(jobs)
                    print(f"[fetch_boss_jobs] {city_name}/{keyword} 第 {page} 页: {len(jobs)} 条")
                    time.sleep(delay)
    finally:
        client.close()

    jobs = deduplicate_jobs(collected)
    if max_jobs:
        jobs = jobs[:max_jobs]

    if not no_details and detail_limit:
        detail_client = CdpClient.connect_first_page(cdp_endpoint, user_data_dir=user_data_dir, target_url_contains="zhipin.com")
        try:
            for index, job in enumerate(jobs[:detail_limit], 1):
                try:
                    detail_client.navigate(job["url"], settle_seconds=settle)
                    detail = detail_client.evaluate(DETAIL_EXTRACT_JS)
                    if isinstance(detail, dict):
                        job.update({key: value for key, value in detail.items() if value})
                except Exception as exc:
                    print(f"[fetch_boss_jobs] 详情失败 {index}/{min(detail_limit, len(jobs))}: {exc}")
                time.sleep(delay)
        finally:
            detail_client.close()

    raws = [raw for job in jobs if (raw := normalize_boss_job(job))]
    if not raws:
        return {"listed": len(jobs), "new": 0, "skipped": 0, "details": 0}

    from app.db.mysql import get_db
    db = next(get_db())
    try:
        existing = {
            row[0]
            for row in db.execute(
                text("SELECT source_detail FROM jd_pool WHERE source='boss' AND source_detail IS NOT NULL")
            ).all()
        }
        new_raws = [raw for raw in raws if raw.source_detail not in existing]
        if new_raws:
            stats = run_pipeline(db, new_raws)
        else:
            stats = {"jd_saved": 0}
    finally:
        db.close()

    return {
        "listed": len(jobs),
        "new": int(stats.get("jd_saved", 0)),
        "skipped": len(raws) - int(stats.get("jd_saved", 0)),
        "details": min(detail_limit, len(jobs)) if not no_details else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="BOSS 直聘岗位采集（登录浏览器 + CDP）")
    parser.add_argument("--keywords", required=True, help="逗号分隔关键词，例如 Python,后端工程师,数据工程师")
    parser.add_argument("--cities", required=True, help="城市代码，例如 北京=101010100,上海=101020100")
    parser.add_argument("--cdp", default="http://127.0.0.1:9222", help="CDP 地址；也可填 auto（配合 --user-data-dir）或 ws:// 浏览器级 WebSocket")
    parser.add_argument("--user-data-dir", default=None, help="Edge 用户目录；CDP 固定端口不可用时读取其中的 DevToolsActivePort")
    parser.add_argument("--pages", type=int, default=5, help="每个关键词/城市最多翻页数")
    parser.add_argument("--detail-limit", type=int, default=100, help="最多补采详情的岗位数，0=不补采")
    parser.add_argument("--max-jobs", type=int, default=0, help="全局岗位上限，0=不限制")
    parser.add_argument("--delay", type=float, default=2.0, help="页面之间等待秒数")
    parser.add_argument("--settle", type=float, default=2.0, help="页面加载后的等待秒数")
    parser.add_argument("--no-details", action="store_true", help="只采列表，不打开详情页")
    args = parser.parse_args()

    try:
        result = run_fetch(
            _split_csv(args.keywords),
            _parse_cities(args.cities),
            cdp_endpoint=args.cdp,
            user_data_dir=args.user_data_dir,
            pages=args.pages,
            detail_limit=args.detail_limit,
            max_jobs=args.max_jobs,
            delay=args.delay,
            settle=args.settle,
            no_details=args.no_details,
        )
    except (ValueError, CdpError) as exc:
        parser.error(str(exc))
    print(f"[fetch_boss_jobs] 完成: {result}")


if __name__ == "__main__":
    main()
