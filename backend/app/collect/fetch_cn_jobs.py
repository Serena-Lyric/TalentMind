"""智联/猎聘页面可见内容采集。

连接独立 Edge 的公开或用户人工认证页面并读取可见 DOM；不读取 Cookie、密码，
不拦截请求，不调用未公开接口，不处理验证码或其他验证。
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Iterable

from sqlalchemy import text
from websockets.exceptions import WebSocketException

from app.collect.fetchers.cdp import CdpClient, CdpError
from app.collect.fetchers.job_sites import (
    SITES,
    SiteSpec,
    build_activate_card_js,
    build_detail_extract_js,
    build_search_extract_js,
    deduplicate_jobs,
    normalize_job,
    normalize_url,
)
from app.collect.pipeline import run_pipeline
from app.collect.cleaner import clean, is_valid_jd
from app.collect import browser


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_cities(value: str) -> list[tuple[str, str]]:
    cities = []
    for token in split_csv(value):
        if "=" in token:
            name, code = token.split("=", 1)
        else:
            name, code = token, token
        name, code = name.strip(), code.strip()
        if not name or not code:
            raise ValueError(f"城市格式应为 名称=平台城市值: {token}")
        cities.append((name, code))
    if not cities:
        raise ValueError("至少需要一个城市")
    return cities


def extract_current_page(client: CdpClient, spec: SiteSpec) -> list[dict]:
    browser.wait_access(client, spec.source)
    result = client.evaluate(build_search_extract_js(spec))
    return result if isinstance(result, list) else []


def fetch_search_page(client: CdpClient, spec: SiteSpec, url: str, settle: float) -> list[dict]:
    client.navigate(url, settle_seconds=settle)
    return extract_current_page(client, spec)


def detail_rejection(spec: SiteSpec, job: dict, detail) -> str | None:
    """A list card cannot prove its detail body or identity is complete."""
    if not isinstance(detail, dict) or not str(detail.get('description') or '').strip():
        return 'empty_detail'
    if detail.get('description_truncated'):
        return 'truncated_description'
    if job.get('_dom'):
        # A title or card index alone cannot bind an asynchronous detail panel.
        return 'unverified_dom_identity'
    title = ' '.join(str(detail.get('title') or '').split())
    if not title:
        return 'missing_detail_title'
    if title.casefold() != ' '.join(str(job.get('title') or '').split()).casefold():
        return 'title_mismatch'
    if not job.get('_dom') and normalize_url(spec, str(detail.get('url') or '')) != normalize_url(spec, job['url']):
        return 'identity_mismatch'
    raw = normalize_job(spec, {'url': job['url'], 'title': title}, {'description': detail['description']})
    if not raw or not is_valid_jd(clean(raw)):
        return 'invalid_detail_body'
    return None


def run_fetch(
    platform: str,
    keywords: Iterable[str],
    cities: Iterable[tuple[str, str]],
    *,
    cdp_endpoint: str,
    user_data_dir: str | None = None,
    pages: int = 1,
    detail_limit: int = 8,
    max_jobs: int = 12,
    delay: float = 15.0,
    settle: float = 6.0,
    no_details: bool = False,
    search_url_template: str | None = None,
    current_page_only: bool = False,
    browser_timeout: float = 20,
    login_timeout: float = 120,
    on_event=None,
) -> dict:
    spec = SITES.get(platform)
    if spec is None:
        raise ValueError(f"不支持的平台: {platform}")
    keywords = [x for x in keywords if x]
    cities = list(cities)
    if not keywords or not cities:
        raise ValueError("至少需要一个关键词和城市")
    if pages < 1 or detail_limit < 0 or max_jobs < 0 or delay < 0 or settle < 0:
        raise ValueError("pages 必须 >=1，其余数值不能为负数")
    if search_url_template:
        spec = SiteSpec(**{**spec.__dict__, "search_template": search_url_template})

    prepared = browser.ensure_ready(platform, cdp_endpoint, user_data_dir,
                                   timeout=browser_timeout, wait_for_login=login_timeout)
    cdp_endpoint = prepared['endpoint']

    client = CdpClient.connect_first_page(
        cdp_endpoint, target_url_contains=spec.host_hint, target_id=prepared.get('target_id')
    )
    def emit(event: str, **payload):
        if on_event:
            on_event({"event": event, "platform": platform, **payload})

    collected: list[dict] = []
    try:
        if current_page_only:
            collected = deduplicate_jobs(spec, extract_current_page(client, spec))
            if max_jobs:
                collected = collected[:max_jobs]
        else:
            queries = ((keyword, name, code, page) for keyword in keywords
                       for name, code in cities for page in range(1, pages + 1))
            for keyword, city_name, city_code, page in queries:
                incoming = fetch_search_page(client, spec, spec.search_url(keyword, city_code, page), settle)
                collected = deduplicate_jobs(spec, collected + incoming)
                if max_jobs:
                    collected = collected[:max_jobs]
                print(f"[fetch_cn_jobs] {platform} {city_name}/{keyword} 第 {page} 页: 候选 {len(collected)} 条", flush=True)
                if max_jobs and len(collected) >= max_jobs:
                    break
                if page < pages:
                    time.sleep(delay)
    finally:
        client.close()

    jobs = collected
    emit('listed', jobs=jobs)
    stats = dict(platform=platform, listed=len(jobs), details=0, detail_attempted=0,
                 detail_obtained=0, complete=0, inserted=0, updated=0, new=0,
                 skipped=0, rejected=0, failed=0, unattempted=len(jobs),
                 rejection_reasons={}, stop_reason=None)
    accepted = list(jobs) if no_details else []
    if not no_details and detail_limit and jobs:
        detail_client = CdpClient.connect_first_page(
            cdp_endpoint, target_url_contains=spec.host_hint, target_id=prepared.get('target_id')
        )
        try:
            for index, job in enumerate(jobs[:detail_limit], 1):
                stats['detail_attempted'] += 1
                stats['details'] += 1
                stats['unattempted'] -= 1
                emit('detail_attempt', index=index, job=job)
                try:
                    if job.get('_dom'):
                        result = detail_client.evaluate(build_activate_card_js(spec, int(job.get('_card_index', -1))))
                        if not isinstance(result, dict) or not result.get('clicked'):
                            raise CdpError('card_activation_failed')
                        time.sleep(settle)
                    else:
                        detail_client.navigate(job['url'], settle_seconds=settle)
                    access = browser.wait_access(detail_client, platform, max(5.0, settle * 2.0))
                    if access.get('content_limited'):
                        raise browser.AccessBlocked('limited_guest_content')
                    detail = detail_client.evaluate(build_detail_extract_js(spec))
                    if isinstance(detail, dict) and str(detail.get('description') or '').strip():
                        stats['detail_obtained'] += 1
                    reason = detail_rejection(spec, job, detail)
                    emit('detail', index=index, job=job, detail=detail, access=access, rejection=reason)
                    if reason:
                        stats['rejected'] += 1
                        stats['rejection_reasons'][reason] = stats['rejection_reasons'].get(reason, 0) + 1
                    else:
                        accepted.append({**job, **{key: value for key, value in detail.items() if value and key != 'url'}})
                        stats['complete'] += 1
                except (CdpError, WebSocketException, OSError, TimeoutError) as exc:
                    stats['failed'] += 1
                    stats['stop_reason'] = str(exc)
                    emit('failure', index=index, job=job, reason=str(exc))
                    break
                if index < min(detail_limit, len(jobs)):
                    time.sleep(delay)
        finally:
            detail_client.close()

    raws = [raw for job in accepted if (raw := normalize_job(spec, job))]
    if raws:
        from app.db.mysql import get_db
        provider = get_db()
        db = next(provider)
        try:
            existing = {row[0] for row in db.execute(
                text("SELECT source_detail FROM jd_pool WHERE source=:source AND source_detail IS NOT NULL"),
                {'source': spec.source}).all()}
            new_raws = [raw for raw in raws if raw.source_detail not in existing]
            stats['skipped'] = len(raws) - len(new_raws)
            saved = run_pipeline(db, new_raws)['jd_saved'] if new_raws else 0
            stats['new'] = stats['inserted'] = int(saved)
            emit('persisted', source_details=[raw.source_detail for raw in new_raws], inserted=int(saved))
        except Exception:
            db.rollback()
            raise
        finally:
            provider.close()
    emit('finished', stats=stats)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="智联/猎聘页面可见内容采集")
    parser.add_argument("--platform", choices=sorted(SITES), required=True)
    parser.add_argument("--keywords", help="逗号分隔关键词")
    parser.add_argument("--cities", help="名称=平台城市值，例如 北京=530")
    parser.add_argument("--cdp", default="http://127.0.0.1:9333")
    parser.add_argument("--user-data-dir", default=None)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--detail-limit", type=int, default=8)
    parser.add_argument("--max-jobs", type=int, default=12)
    parser.add_argument("--delay", type=float, default=15.0)
    parser.add_argument("--settle", type=float, default=6.0)
    parser.add_argument("--no-details", action="store_true")
    parser.add_argument("--current-page", action="store_true", help="只采集当前已打开且已登录的页面，不导航")
    parser.add_argument("--search-url-template", default=None, help="覆盖当前平台搜索 URL 模板，支持 {keyword}/{city}/{page}")
    parser.add_argument('--prepare-only', action='store_true', help='只准备浏览器，不采集、不连接数据库')
    parser.add_argument('--browser-timeout', type=float, default=20)
    parser.add_argument('--login-timeout', type=float, default=120)
    args = parser.parse_args()
    if args.prepare_only:
        state = browser.prepare(args.platform, args.cdp, args.user_data_dir,
                                args.browser_timeout, args.login_timeout)
        print(json.dumps(state, ensure_ascii=False))
        return 0 if state['can_collect'] else 2
    if not args.keywords or not args.cities:
        parser.error('采集必须提供 --keywords 和 --cities')
    result = run_fetch(
        args.platform,
        split_csv(args.keywords),
        parse_cities(args.cities),
        cdp_endpoint=args.cdp,
        user_data_dir=args.user_data_dir,
        pages=args.pages,
        detail_limit=args.detail_limit,
        max_jobs=args.max_jobs,
        delay=args.delay,
        settle=args.settle,
        no_details=args.no_details,
        current_page_only=args.current_page,
        search_url_template=args.search_url_template,
        browser_timeout=args.browser_timeout,
        login_timeout=args.login_timeout,
    )
    print(f"[fetch_cn_jobs] 完成: {result}")
    return 2 if result.get("stop_reason") else 0


if __name__ == "__main__":
    raise SystemExit(main())
