"""智联/猎聘页面可见内容采集。

连接独立 Edge 的公开或用户人工认证页面并读取可见 DOM；不读取 Cookie、密码，
不拦截请求，不调用未公开接口，不处理验证码或其他验证。
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from typing import Iterable

from websockets.exceptions import WebSocketException

from app.collect.fetchers.cdp import CdpClient, CdpError
from app.collect.fetchers.job_sites import (
    SITES,
    SiteSpec,
    build_activate_card_js,
    build_detail_extract_js,
    build_panel_probe_js,
    build_search_extract_js,
    clean as clean_text,
    deduplicate_jobs,
    normalize_job,
)
from app.collect.pipeline import run_pipeline
from app.collect import browser
from app.collect.events import emit_event
from app.collect.identity import content_rejection, dom_fingerprint, identity_decision
from app.collect.repository import save_incremental_jd_rows


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


def _panel_content_signature(probe: dict) -> tuple[str, str, str, bool]:
    return (
        clean_text(probe.get('panel_title')),
        clean_text(probe.get('description')),
        clean_text(probe.get('company')),
        bool(probe.get('panel_visible')),
    )


def _panel_stability_signature(probe: dict) -> tuple:
    return (*_panel_content_signature(probe), bool(probe.get('target_active')))


def await_stable_panel(
    client: CdpClient,
    spec: SiteSpec,
    card_index: int,
    before: dict,
    timeout: float = 5.0,
    interval: float = 0.2,
) -> dict:
    """Poll the detail panel until one update becomes stable twice in a row."""
    deadline = time.monotonic() + timeout
    previous = None
    stable_samples = 0
    last = {}
    while time.monotonic() < deadline:
        probe = client.evaluate(build_panel_probe_js(spec, card_index))
        if isinstance(probe, dict):
            signature = _panel_stability_signature(probe)
            stable_samples = stable_samples + 1 if signature == previous else 1
            previous = signature
            last = probe
            if stable_samples >= 2:
                break
        time.sleep(interval)
    return {
        'target_card_found': bool(last.get('target_card_found')),
        'target_active_before': bool(before.get('target_active')),
        'target_active_after': bool(last.get('target_active')),
        'panel_visible': bool(last.get('panel_visible')),
        'panel_changed': _panel_content_signature(before) != _panel_content_signature(last),
        'stable_samples': stable_samples,
        'panel_title': clean_text(last.get('panel_title')),
        'before_panel_title': clean_text(before.get('panel_title')),
        'description': str(last.get('description') or ''),
        'company': clean_text(last.get('company')),
        'list_url': str(last.get('list_url') or before.get('list_url') or ''),
        'binding_policy': 'zhaopin-dom-panel-v1',
    }


def detail_rejection(spec: SiteSpec, job: dict, detail) -> str | None:
    """Compatibility helper for callers that have no binding evidence."""
    reason = content_rejection(spec, job, detail)
    if reason:
        return reason
    _, _, reason = identity_decision(spec, job, detail, None, '')
    return reason


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
        emit_event(on_event, platform, event, **payload)

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
                 detail_obtained=0, content_eligible=0, identity_pending=0,
                 identity_verified=0, complete=0, inserted=0, updated=0, new=0,
                 skipped=0, rejected=0, failed=0, unattempted=len(jobs),
                 rejection_reasons={}, stop_reason=None)
    accepted = list(jobs) if no_details else []
    if no_details:
        stats['content_eligible'] = None
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
                    binding = None
                    if job.get('_dom'):
                        before = detail_client.evaluate(build_panel_probe_js(spec, int(job.get('_card_index', -1))))
                        if not isinstance(before, dict):
                            raise CdpError('panel_probe_failed')
                        result = detail_client.evaluate(build_activate_card_js(spec, int(job.get('_card_index', -1))))
                        if not isinstance(result, dict) or not result.get('clicked'):
                            raise CdpError('card_activation_failed')
                        binding = await_stable_panel(
                            detail_client, spec, int(job.get('_card_index', -1)), before,
                            timeout=max(2.0, settle * 2.0),
                        )
                    else:
                        detail_client.navigate(job['url'], settle_seconds=settle)
                    access = browser.wait_access(detail_client, platform, max(5.0, settle * 2.0))
                    if access.get('content_limited'):
                        raise browser.AccessBlocked('limited_guest_content')
                    detail = detail_client.evaluate(build_detail_extract_js(spec))
                    if isinstance(detail, dict) and str(detail.get('description') or '').strip():
                        stats['detail_obtained'] += 1
                    content_reason = content_rejection(spec, job, detail)
                    content_ok = content_reason is None
                    if content_ok:
                        stats['content_eligible'] += 1
                    observed_at = None
                    if content_ok:
                        observed_at = datetime.now(timezone.utc).isoformat()
                        status, evidence, reason = identity_decision(spec, job, detail, binding, observed_at)
                    else:
                        status, evidence, reason = 'unknown', {}, content_reason
                    if reason:
                        stats['rejected'] += 1
                        stats['rejection_reasons'][reason] = stats['rejection_reasons'].get(reason, 0) + 1
                    else:
                        if status == 'pending':
                            stats['identity_pending'] += 1
                            fingerprint = dom_fingerprint(evidence)
                            job = {**job, 'url': f'dom://{platform}/{fingerprint}'}
                        elif status == 'verified':
                            stats['identity_verified'] += 1
                            stats['complete'] += 1
                        evidence = {**evidence, '_observation_key': job.get('_observation_key', '')}
                        enriched_job = {
                            **job,
                            '_identity_status': status,
                            '_content_eligible': True,
                            '_identity_evidence': json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                        }
                        accepted.append({**enriched_job, **{
                            key: value for key, value in detail.items() if value and key != 'url'
                        }})
                    emit('detail', index=index, job=job, detail=detail, access=access,
                         rejection=reason, identity_status=status, content_eligible=content_ok,
                         identity_evidence=evidence, observed_at=observed_at)
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
            row_by_detail = {
                row.source_detail: {
                    'identity_status': row.identity_status,
                    'content_eligible': row.content_eligible,
                    'identity_evidence': row.identity_evidence,
                    'observation_key': row.observation_key,
                }
                for row in raws
            }
            def saved_event(item):
                if item['outcome'] == 'skipped':
                    stats['skipped'] += 1
                identity = row_by_detail.get(item.get('source_detail'), {})
                evidence = identity.get('identity_evidence')
                if evidence:
                    try:
                        evidence = json.loads(evidence)
                    except (TypeError, ValueError):
                        evidence = None
                emit('persisted', items=[{
                    **item,
                    'identity_status': identity.get('identity_status', 'unknown'),
                    'content_eligible': identity.get('content_eligible'),
                    'identity_evidence': evidence,
                    'observation_key': identity.get('observation_key') or item.get('observation_key'),
                }])
            def saver(session, rows):
                return save_incremental_jd_rows(session, rows, created_ids=set(), on_saved=saved_event)
            saved = run_pipeline(db, raws, jd_saver=saver)['jd_saved']
            stats['new'] = stats['inserted'] = int(saved)
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
