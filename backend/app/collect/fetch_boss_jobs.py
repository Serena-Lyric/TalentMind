"""BOSS 直聘岗位采集（用户登录浏览器 + CDP，不绕过验证码/反爬）。

示例：
  python -m app.collect.fetch_boss_jobs --keywords Python,后端工程师 --cities 北京=101010100 --pages 10
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
from functools import partial

from app.collect.events import emit_event

from app.collect.fetchers.boss import BOSS_CARD_SELECTOR, BOSS_DESCRIPTION_SELECTORS, deduplicate_jobs, normalize_boss_job, normalize_url
from app.collect.fetchers.cdp import CdpClient, CdpError, CdpConnectionError
from app.collect.cleaner import clean, is_valid_jd
from app.collect.pipeline import run_pipeline
from app.collect.repository import save_incremental_jd_rows
from app.collect import browser

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
    const card = anchor.closest(__BOSS_CARDS__) || anchor.parentElement;
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
""".replace('__BOSS_CARDS__', json.dumps(BOSS_CARD_SELECTOR + ', li'))

DETAIL_EXTRACT_JS = r"""
(() => {
  const text = (node) => (node?.innerText || node?.textContent || '').replace(/\r\n?/g, '\n').trim();
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
    description: first(__BOSS_DESCRIPTIONS__),
    company_info: first(['.job-sec.company-info', '.company-info .desc', '.company-info']),
  };
})()
""".replace('__BOSS_DESCRIPTIONS__', json.dumps(BOSS_DESCRIPTION_SELECTORS))


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


def _fetch_search_page(client: CdpClient, url: str, settle: float) -> list[dict]:
    client.navigate(url, settle_seconds=settle)
    browser.wait_access(client, 'boss', max(5.0, settle * 2.0))
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
    browser_timeout: float = 20,
    login_timeout: float = 120,
    on_event=None,
) -> dict:
    if not keywords or not cities:
        raise ValueError("至少需要一个关键词和一个城市")
    if pages < 1 or detail_limit < 0 or max_jobs < 0 or delay < 0:
        raise ValueError("pages/detail_limit/max_jobs/delay 不能为负数")

    prepared = browser.ensure_ready('boss', cdp_endpoint, user_data_dir,
                                   timeout=browser_timeout, wait_for_login=login_timeout)
    cdp_endpoint = prepared['endpoint']

    from app.db.mysql import get_db

    # 保留 provider 至 finally，避免 next(get_db()) 的临时生成器提前关闭 session。
    provider = get_db()
    db = next(provider)
    created_ids: set[int] = set()
    def emit(event, **payload):
        emit_event(on_event, 'boss', event, **payload)
    stats = dict(listed=0, details=0, new=0, skipped=0, detail_attempted=0, detail_obtained=0,
                 complete=0, inserted=0, updated=0, rejected=0, failed=0, unattempted=0,
                 rejection_reasons={}, stop_reason=None)
    def saved_event(item):
        stats[item['outcome']] += 1
        stats['new'] = stats['inserted']
        emit('persisted', items=[item])
    save_list = partial(save_incremental_jd_rows, created_ids=created_ids, on_saved=saved_event)
    save_detail = partial(save_incremental_jd_rows, created_ids=created_ids, allow_updates=True, on_saved=saved_event)
    jobs: list[dict] = []
    details_count = 0
    try:
        client = CdpClient.connect_first_page(cdp_endpoint, target_url_contains="zhipin.com", target_id=prepared.get('target_id'))
        try:
            for keyword in keywords:
                for city_name, city_code in cities:
                    consecutive_empty = 0
                    for page in range(1, pages + 1):
                        url = _search_url(keyword, city_code, page)
                        page_jobs = _fetch_search_page(client, url, settle)
                        if not page_jobs:
                            consecutive_empty += 1
                            if consecutive_empty >= 2:
                                break
                        else:
                            consecutive_empty = 0
                            jobs = deduplicate_jobs(jobs + page_jobs)
                            if max_jobs:
                                jobs = jobs[:max_jobs]
                            page_urls = {job["url"] for job in deduplicate_jobs(page_jobs)}
                            raws = [raw for job in jobs if job["url"] in page_urls
                                    and (raw := normalize_boss_job(job))]
                            emit('listed', jobs=jobs)
                            stats['listed'] = len(jobs)
                            stats['unattempted'] = len(jobs)
                            if no_details:
                                run_pipeline(db, raws, jd_saver=save_list)
                        print(f"[fetch_boss_jobs] {city_name}/{keyword} 第 {page} 页: {len(page_jobs)} 条")
                        if max_jobs and len(jobs) >= max_jobs:
                            break
                        time.sleep(delay)
                    if max_jobs and len(jobs) >= max_jobs:
                        break
                if max_jobs and len(jobs) >= max_jobs:
                    break
        finally:
            client.close()

        if not no_details and detail_limit and jobs:
            detail_client = CdpClient.connect_first_page(cdp_endpoint, target_url_contains="zhipin.com", target_id=prepared.get('target_id'))
            try:
                for index, job in enumerate(jobs[:detail_limit], 1):
                    details_count += 1
                    stats['details'] = stats['detail_attempted'] = details_count
                    stats['unattempted'] = len(jobs) - details_count
                    emit('detail_attempt', job=job, index=index)
                    try:
                        detail_client.navigate(job["url"], settle_seconds=settle)
                        access = browser.wait_access(detail_client, 'boss', max(5.0, settle * 2.0))
                        if access.get('content_limited'):
                            raise browser.AccessBlocked('limited_guest_content')
                        detail = detail_client.evaluate(DETAIL_EXTRACT_JS)
                    except (browser.AccessBlocked, CdpConnectionError) as exc:
                        stats['failed'] += 1
                        stats['stop_reason'] = str(exc)
                        emit('failure', job=job, reason=str(exc))
                        emit('finished', stats=stats)
                        raise
                    except Exception as exc:
                        stats['failed'] += 1
                        emit('failure', job=job, reason=str(exc))
                        print(f"[fetch_boss_jobs] 详情失败 {index}/{min(detail_limit, len(jobs))}: {exc}")
                        time.sleep(delay)
                        continue
                    reason = detail_rejection(job, detail)
                    if isinstance(detail, dict) and str(detail.get('description') or '').strip():
                        stats['detail_obtained'] += 1
                    emit('detail', job=job, detail=detail, rejection=reason)
                    if reason:
                        stats['rejected'] += 1
                        stats['rejection_reasons'][reason] = stats['rejection_reasons'].get(reason, 0) + 1
                    else:
                        stats['complete'] += 1
                        job.update({key: value for key, value in detail.items() if value and key != 'url'})
                        raw = normalize_boss_job(job)
                        if raw:
                            run_pipeline(db, [raw], jd_saver=save_detail)
                    time.sleep(delay)
            finally:
                detail_client.close()
    finally:
        provider.close()

    emit('finished', stats=stats)
    return stats


def detail_rejection(job: dict, detail) -> str | None:
    if not isinstance(detail, dict) or not str(detail.get('description') or '').strip():
        return 'empty_detail'
    if detail.get('description_truncated'):
        return 'truncated_description'
    if not detail.get('title') or ' '.join(detail['title'].split()) != ' '.join(job['title'].split()):
        return 'title_mismatch'
    if normalize_url(str(detail.get('url') or '')) != normalize_url(job['url']):
        return 'identity_mismatch'
    raw = normalize_boss_job({'url': job['url'], 'title': job['title'], 'description': detail['description']})
    if not raw or not is_valid_jd(clean(raw)):
        return 'invalid_detail_body'
    return None



def main() -> int:
    parser = argparse.ArgumentParser(description="BOSS 直聘岗位采集（登录浏览器 + CDP）")
    parser.add_argument("--keywords", help="逗号分隔关键词，例如 Python,后端工程师,数据工程师")
    parser.add_argument("--cities", help="城市代码，例如 北京=101010100,上海=101020100")
    parser.add_argument("--cdp", default="http://127.0.0.1:9222", help="CDP 地址；也可填 auto（配合 --user-data-dir）或 ws:// 浏览器级 WebSocket")
    parser.add_argument("--user-data-dir", default=None, help="Edge 用户目录；CDP 固定端口不可用时读取其中的 DevToolsActivePort")
    parser.add_argument("--pages", type=int, default=5, help="每个关键词/城市最多翻页数")
    parser.add_argument("--detail-limit", type=int, default=100, help="最多补采详情的岗位数，0=不补采")
    parser.add_argument("--max-jobs", type=int, default=0, help="全局岗位上限，0=不限制")
    parser.add_argument("--delay", type=float, default=2.0, help="页面之间等待秒数")
    parser.add_argument("--settle", type=float, default=2.0, help="页面加载后的等待秒数")
    parser.add_argument("--no-details", action="store_true", help="只采列表，不打开详情页")
    parser.add_argument('--prepare-only', action='store_true', help='只准备浏览器，不采集、不连接数据库')
    parser.add_argument('--browser-timeout', type=float, default=20)
    parser.add_argument('--login-timeout', type=float, default=120)
    args = parser.parse_args()
    if args.prepare_only:
        state = browser.prepare('boss', args.cdp, args.user_data_dir,
                                args.browser_timeout, args.login_timeout)
        print(json.dumps(state, ensure_ascii=False))
        return 0 if state['can_collect'] else 2
    if not args.keywords or not args.cities:
        parser.error('采集必须提供 --keywords 和 --cities')

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
            browser_timeout=args.browser_timeout,
            login_timeout=args.login_timeout,
        )
    except (ValueError, CdpError) as exc:
        parser.error(str(exc))
    print(f"[fetch_boss_jobs] 完成: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
