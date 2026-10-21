"""M1 中文平台采集控制器。

只负责把现有采集循环包装为可观察的本地任务，不重写采集器。
运行状态和历史写入 `data/local/collection/`，该目录属于本地运行态，不入库。
"""
from __future__ import annotations

import ast
import json
import math
import os
import re
import subprocess
import sys
import threading
import uuid
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.collect.boss_collect_loop import DEFAULT_CITIES, DEFAULT_KEYWORDS
from app.collect.fetch_boss_jobs import _search_url as boss_search_url
from app.collect.fetchers.job_sites import SITES, SiteSpec
from app.collect import browser, worker_process
from app.collect.cleaner import source_sections

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STATE_DIR = _REPO_ROOT / "data" / "local" / "collection"
_STATE_PATH = _STATE_DIR / "control-state.json"
_LOCK = threading.RLock()
_PROCESS: subprocess.Popen[str] | None = None
_START_THREAD: threading.Thread | None = None
_STARTING_RUN: str | None = None
_DONE_EVENTS: dict[str, threading.Event] = {}
_RESERVATION: object | None = None
_spawn_process = worker_process.spawn
_ACTIVE_STATUSES = {"preparing", "waiting_for_browser", "running", "waiting_next_round", "stopping"}
_QUALITY_COUNTERS = ('detail_attempted', 'detail_obtained', 'complete', 'inserted',
                     'updated', 'rejected', 'failed', 'unattempted')
_DEFAULT_CONFIG: dict[str, Any] = {
    "platform": "boss",
    "mode": "once",
    "keywords": ["Python"],
    "cities": [{"name": "北京", "code": "101010100"}],
    "pages": 1,
    "detail_limit": 5,
    "max_jobs": 5,
    "page_delay_min": 15,
    "page_delay_max": 30,
    "settle_min": 5,
    "settle_max": 10,
    "switch_interval_min": 360,
    "switch_interval_max": 720,
    "rounds": 0,
    "check_cdp_before_start": True,
    "cdp_endpoint": "http://127.0.0.1:9333",
    "user_data_dir": str(_REPO_ROOT / "data" / "local" / "edge-boss-cdp-profile"),
    "search_url_template": None,
}

_PLATFORMS = [
    {"platform": "boss", "label": "BOSS直聘", "supported": True,
     "cities": [{"name": n, "code": c} for n, c in DEFAULT_CITIES]},
    {"platform": "zhaopin", "label": "智联招聘", "supported": True,
     "cities": [{"name": "北京", "code": "530"}, {"name": "上海", "code": "538"}, {"name": "深圳", "code": "765"}]},
    {"platform": "liepin", "label": "猎聘", "supported": True,
     "cities": [{"name": n, "code": n} for n in ("北京", "上海", "深圳")]},
]


def get_platforms() -> list[dict[str, Any]]:
    return json.loads(json.dumps(_PLATFORMS))


def _validated_config(base: dict, payload: dict) -> dict:
    if set(payload) - set(_DEFAULT_CONFIG):
        raise ValueError("未知配置字段")
    if any(value is None for key, value in payload.items() if key != 'search_url_template'):
        raise ValueError("配置字段不能为 null")
    config = {**base, **payload}
    platform = config['platform']
    spec = next((p for p in _PLATFORMS if p['platform'] == platform), None)
    if spec is None:
        raise ValueError('不支持的平台')
    if platform != base.get('platform') and 'cities' not in payload:
        config['cities'] = [dict(spec['cities'][0])]
    if platform != base.get('platform') and 'search_url_template' not in payload:
        config['search_url_template'] = None
    if config['mode'] != 'once':
        raise ValueError('Gate 1 验收前仅开放单轮采集')
    for key, upper in (('pages', 1), ('max_jobs', 5), ('detail_limit', 5)):
        value = config[key]
        if type(value) is not int or not 1 <= value <= upper:
            raise ValueError(f'{key} 必须为 1..{upper} 的整数')
    if type(config['rounds']) is not int or config['rounds'] not in (0, 1):
        raise ValueError('单轮 rounds 必须为 0 或 1')
    keywords = config['keywords']
    if (not isinstance(keywords, list) or len(keywords) != 1 or not isinstance(keywords[0], str)
            or not keywords[0].strip() or len(keywords[0]) > 100 or ',' in keywords[0]):
        raise ValueError('仅允许一个非空关键词')
    config['keywords'] = [keywords[0].strip()]
    if config['cities'] not in [[city] for city in spec['cities']]:
        raise ValueError('仅允许一个当前平台支持的城市及代码')
    for prefix in ('page_delay', 'settle', 'switch_interval'):
        values = [config[f'{prefix}_{suffix}'] for suffix in ('min', 'max')]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values) or values[0] > values[1]:
            raise ValueError(f'{prefix} 时间范围无效')
    if type(config['check_cdp_before_start']) is not bool:
        raise ValueError('check_cdp_before_start 必须是布尔值')
    endpoint = config['cdp_endpoint']
    if not isinstance(endpoint, str) or (endpoint != 'auto' and (urlsplit(endpoint).hostname not in {'localhost', '127.0.0.1', '::1'} or urlsplit(endpoint).scheme not in {'http', 'ws'})):
        raise ValueError('CDP 仅允许本机回环地址')
    if not isinstance(config['user_data_dir'], str) or not config['user_data_dir'].strip():
        raise ValueError('user_data_dir 不能为空')
    template = config['search_url_template']
    if template is not None and not isinstance(template, str):
        raise ValueError('搜索模板必须是字符串')
    if template:
        host = urlsplit(template).hostname or ''
        domain = {'boss': 'zhipin.com', 'zhaopin': 'zhaopin.com', 'liepin': 'liepin.com'}[platform]
        if not isinstance(template, str) or urlsplit(template).scheme != 'https' or not (host == domain or host.endswith('.' + domain)):
            raise ValueError('搜索模板必须属于当前平台 HTTPS 域名')
    return config


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _empty_task(run_id: str | None, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "status": "preparing",
        "platform": config.get("platform", "boss"),
        "mode": config["mode"],
        "started_at": _now(),
        "finished_at": None,
        "current_keyword": None,
        "current_city": None,
        "current_round": 0,
        "total_rounds": config["rounds"] if config["mode"] == "limited" else None,
        "listed": None,
        "details": None,
        **dict.fromkeys(_QUALITY_COUNTERS),
        "quality_metrics_available": False,
        "stop_reason": None,
        "new": None,
        "skipped": None,
        "errors": 0,
        "last_error": None,
        "next_run_at": None,
        "cdp_status": "unknown",
        "browser_page_status": None,
        "database_total": None,
        "database_boss_total": None,
        "database_new_count": None,
        "pid": None,
        "log_path": None,
        "log_summary": {},
        "raw_log_tail": [],
    }


def _default_state() -> dict[str, Any]:
    return {"current_task": None, "history": [], "config": dict(_DEFAULT_CONFIG)}


def _load_state() -> dict[str, Any]:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not _STATE_PATH.exists():
        return _default_state()
    try:
        value = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("state must be an object")
        state = _default_state()
        state.update(value)
        state["config"] = {**_DEFAULT_CONFIG, **(value.get("config") or {})}
        if not state["config"].get("user_data_dir"):
            state["config"]["user_data_dir"] = _DEFAULT_CONFIG["user_data_dir"]
        return state
    except (OSError, ValueError, json.JSONDecodeError):
        return _default_state()


def _save_state(state: dict[str, Any]) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = _STATE_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(_STATE_PATH)


def _update_task(run_id: str, **changes: Any) -> None:
    with _LOCK:
        state = _load_state()
        task = state.get("current_task")
        if not task or task.get("run_id") != run_id:
            return
        if task.get('status') in {'stopped', 'stopping'}:
            changes.pop('status', None)
            changes.pop('stop_reason', None)
        if "raw_log_line" in changes:
            line = str(changes.pop("raw_log_line"))
            tail = list(task.get("raw_log_tail") or [])
            tail.append(line)
            changes["raw_log_tail"] = tail[-30:]
        task.update(changes)
        _save_state(state)


def _parse_log_line(run_id: str, line: str) -> None:
    """兼容 BOSS、智联、猎聘循环输出，并把可识别字段写入当前任务。"""
    clean = line.strip()
    if clean.startswith('TM_EVENT '):
        try:
            event = json.loads(clean[len('TM_EVENT '):])
            path = _event_path(run_id)
            with _LOCK:
                with path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(event, ensure_ascii=False) + '\n')
                state = _load_state()
                task = state.get('current_task') or {}
                if task.get('run_id') == run_id:
                    kind = event.get('event')
                    if kind == 'listed':
                        if task.get('listed') is None:
                            task.update(dict.fromkeys(('details', 'new', 'skipped', *_QUALITY_COUNTERS), 0))
                        task['listed'] = len(event.get('jobs', []))
                        task['unattempted'] = max(0, task['listed'] - (task.get('detail_attempted') or 0))
                    elif kind == 'detail_attempt':
                        task['detail_attempted'] = task['details'] = (task.get('detail_attempted') or 0) + 1
                        task['unattempted'] = max(0, (task.get('listed') or 0) - task['details'])
                    elif kind == 'detail':
                        detail = event.get('detail') or {}
                        if detail.get('description'):
                            task['detail_obtained'] = (task.get('detail_obtained') or 0) + 1
                        counter = 'rejected' if event.get('rejection') else 'complete'
                        task[counter] = (task.get(counter) or 0) + 1
                    elif kind == 'failure':
                        task['failed'] = (task.get('failed') or 0) + 1
                    elif kind == 'persisted':
                        for item in event.get('items', []):
                            counter = item.get('outcome')
                            if counter in {'inserted', 'updated', 'skipped'}:
                                task[counter] = (task.get(counter) or 0) + 1
                        task['new'] = task.get('inserted')
                    _save_state(state)
            if event.get('event') == 'finished':
                stats = event['stats']
                changes = {key: stats.get(key) for key in ('listed', 'details', 'new', 'skipped', *_QUALITY_COUNTERS)}
                changes.update(quality_metrics_available=True, stop_reason=stats.get('stop_reason'))
                if stats.get('stop_reason'):
                    changes.update(status='error', last_error=stats['stop_reason'])
                _update_task(run_id, **changes)
        except (ValueError, TypeError, KeyError):
            _update_task(run_id, last_error='任务事件格式错误')
        return
    start_match = re.search(r"(?:BOSS|zhaopin|liepin) 第 (\d+) 轮开始: ([^/]+)/([^;]+);", clean, re.I)
    if start_match:
        _update_task(run_id, status="running", current_round=int(start_match.group(1)),
                     current_city=start_match.group(2).strip(), current_keyword=start_match.group(3).strip(),
                     raw_log_line=clean)
        return
    if "等待" in clean and "后切换" in clean:
        _update_task(run_id, status="waiting_next_round", raw_log_line=clean)
        return
    complete_match = re.search(r"完成: (\{.*\})", clean)
    if complete_match:
        try:
            payload = ast.literal_eval(complete_match.group(1))
        except (ValueError, SyntaxError):
            payload = {}
        if isinstance(payload, dict):
            changes = {key: int(payload.get(key, 0) or 0) for key in ('listed', 'details', 'new', 'skipped', 'errors')}
            changes.update({key: int(payload[key] or 0) for key in _QUALITY_COUNTERS if key in payload})
            changes['quality_metrics_available'] = all(key in payload for key in _QUALITY_COUNTERS)
            if payload.get('stop_reason'):
                reason = str(payload['stop_reason'])
                changes.update(status='error', last_error=reason, stop_reason=reason,
                               errors=max(changes['errors'], changes.get('failed', 0), 1),
                               browser_page_status=next((s for s in ('verification_required', 'login_required', 'page_error') if s in reason), 'blocked'))
            _update_task(run_id, **changes, log_summary=payload, raw_log_line=clean)
            return
    if "CDP/登录状态异常" in clean or "需要人工登录" in clean or ("验证" in clean and "异常" in clean):
        _update_task(run_id, status="error", last_error=clean, raw_log_line=clean)
        return
    _update_task(run_id, raw_log_line=clean)


def _watch_process(run_id: str, process: subprocess.Popen[str]) -> None:
    global _PROCESS
    state = _load_state()
    task = state.get("current_task") or {}
    log_path = Path(task.get("log_path") or (_STATE_DIR / f"{run_id}.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _update_task(run_id, log_path=str(log_path))
    try:
        with log_path.open("a", encoding="utf-8") as log_file:
            if process.stdout:
                for line in process.stdout:
                    log_file.write(line)
                    log_file.flush()
                    _parse_log_line(run_id, line)
    finally:
        return_code = process.wait()
        with _LOCK:
            state = _load_state()
            task = state.get("current_task")
            if task and task.get("run_id") == run_id:
                stopped = task.get("status") in {"stopped", "stopping"}
                if stopped:
                    task['status'] = 'stopped'
                if not stopped:
                    task["status"] = "completed" if return_code == 0 and task.get('status') != 'error' else "error"
                    if return_code != 0 and not task.get("last_error"):
                        task["last_error"] = f"采集进程退出码: {return_code}"
                    if return_code != 0 and not task.get('stop_reason'):
                        task['stop_reason'] = f'worker_exit_{return_code}'
                task["finished_at"] = _now()
                task["next_run_at"] = None
                task["pid"] = None
                task["database_new_count"] = task.get("new", 0)
                task["log_path"] = str(log_path)
                history = state.setdefault("history", [])
                history[:] = [h for h in history if h.get('run_id') != run_id]
                history.insert(0, dict(task))
                state["history"] = history[:100]
                _save_state(state)
            if _PROCESS is process:
                _PROCESS = None
        worker_process.close(process)
        if run_id in _DONE_EVENTS:
            _DONE_EVENTS[run_id].set()


def _event_path(run_id: str) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id):
        raise ValueError('无效 run_id')
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    return _STATE_DIR / f'{run_id}.events.jsonl'


def get_results(run_id: str) -> list[dict[str, Any]]:
    path = _event_path(run_id)
    if not path.exists():
        return []
    items: dict[str, dict] = {}
    with _LOCK:
        lines = path.read_text(encoding='utf-8').splitlines()
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get('event')
        jobs = event.get('jobs', []) if kind == 'listed' else [event['job']] if event.get('job') else []
        for job in jobs:
            key = job.get('url')
            if not key:
                continue
            item = items.setdefault(key, dict(source=event.get('platform'), job_title=job.get('title'),
                source_detail=key, crawled_at=event.get('observed_at'), raw_text=None, duties=None, requirements=None,
                quality=None, rejection_reason=None, outcome='listed', jd_pool_id=None))
            if kind == 'detail':
                detail = event.get('detail') or {}
                item.update(raw_text=detail.get('description'), rejection_reason=event.get('rejection'),
                            outcome='rejected' if event.get('rejection') else 'complete')
            elif kind == 'failure':
                item.update(outcome='failed', rejection_reason=event.get('reason'))
        if kind == 'persisted':
            for saved in event.get('items', []):
                key = saved.get('source_detail')
                if key in items:
                    # A skipped old row supplies its identity only, never its old body.
                    items[key].update({k: v for k, v in saved.items() if k != 'raw_text' or saved.get('outcome') in {'inserted', 'updated'}})
    for item in items.values():
        sections = source_sections(item.get('raw_text'))
        item.update(requirements=sections['requirements'], structure_source=sections['structure_source'])
        if not item.get('duties'):
            item['duties'] = sections['duties']
    return list(items.values())


def get_raw(raw_id: int) -> dict[str, Any] | None:
    from sqlalchemy import text
    from app.db.mysql import SessionLocal
    with SessionLocal() as db:
        row = db.execute(text('SELECT id, source, source_detail, job_title, crawled_at, raw_text, duties, quality FROM jd_pool WHERE id=:id'), {'id': raw_id}).mappings().first()
        if row is None:
            return None
        sections = source_sections(row['raw_text'])
        return {**dict(row), 'jd_pool_id': row['id'], 'duties': row['duties'] or sections['duties'],
                'requirements': sections['requirements'], 'structure_source': sections['structure_source']}


def _search_target(config: dict[str, Any]) -> str:
    keyword, city = config['keywords'][0], config['cities'][0]['code']
    if config['platform'] == 'boss':
        return boss_search_url(keyword, city, 1)
    spec = SITES[config['platform']]
    if config.get('search_url_template'):
        spec = SiteSpec(**{**spec.__dict__, 'search_template': config['search_url_template']})
    return spec.search_url(keyword, city, 1)


def _ensure_browser(endpoint: str, user_data_dir: str | None, platform: str = "boss",
                    target_url: str | None = None) -> dict[str, Any]:
    prepared = browser.prepare(platform, endpoint, user_data_dir, url=target_url)
    current = get_cdp_status(prepared["endpoint"], prepared["user_data_dir"], platform,
                             prepared.get("target_url"), prepared.get("target_id"))
    current["platform_access"][platform] = prepared
    current["user_data_dir"] = prepared["user_data_dir"]
    return current


def get_cdp_status(endpoint: str | None = None, user_data_dir: str | None = None,
                   platform: str | None = None, target_url: str | None = None,
                   target_id: str | None = None) -> dict[str, Any]:
    config = get_config()
    platform = platform or config["platform"]
    target_url = target_url or _search_target(config)
    result = browser.status(
        endpoint or _DEFAULT_CONFIG["cdp_endpoint"],
        user_data_dir or _DEFAULT_CONFIG["user_data_dir"],
        platform=platform,
        target_url=target_url,
        target_id=target_id,
    )
    result["last_checked_at"] = _now()
    return result


def prepare_browser(auto_start: bool = False, platform: str | None = None,
                    config_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Prepare only. Legacy auto_start is accepted but can never start collection."""
    reservation = _reserve_tasks()
    try:
        return _prepare_browser(auto_start, platform, config_payload)
    finally:
        _release_tasks(reservation)


def _prepare_browser(auto_start: bool, platform: str | None,
                     config_payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(config_payload or {})
    if platform is not None:
        payload['platform'] = platform
    config = _validated_config(get_config(), payload)
    platform = config['platform']
    cdp = _ensure_browser(str(config.get("cdp_endpoint") or _DEFAULT_CONFIG["cdp_endpoint"]),
                          config.get("user_data_dir"), platform, _search_target(config))
    access = cdp["platform_access"][platform]
    messages = {'login_required': '需人工登录，请在独立 Edge 中完成登录后重新检查',
                'verification_required': '需人工完成安全验证，请在独立 Edge 中处理后重新检查',
                'content_limited': '游客内容受限，请在独立 Edge 中正常登录后重新检查',
                'empty_results': '目标搜索页暂无相关职位，可调整搜索条件',
                'loading': '目标页面仍在加载，请稍后重新检查'}
    message = messages.get(access['access_state'],
                           '目标搜索页已就绪；仅准备浏览器，采集须显式启动' if access['can_collect']
                           else '浏览器页面尚未就绪，请查看访问状态')
    if access.get('reason') == 'security_check_redirect':
        message = 'BOSS 自动安全校验未返回目标搜索页；当前未发现可人工操作的验证内容。系统已停止自动重试。'
    elif access.get('reason') == 'no_access_evidence':
        message = '已打开目标页，但尚未检测到职位内容；请在独立 Edge 中正常操作后重新检查'
    elif access.get('reason') == 'target_page_redirected':
        message = '目标搜索页已跳转，尚未检测到目标职位内容；请在独立 Edge 中正常操作后重新检查'
    return {"status": "ready" if access["can_collect"] else access["access_state"],
            "access_state": access["access_state"], "can_collect": access["can_collect"],
            "reason": access.get('reason'), "target_url": access.get('target_url'),
            "cdp": cdp, "message": message, "auto_start_ignored": bool(auto_start)}


def get_database_stats() -> dict[str, Any]:
    from sqlalchemy import text
    from app.db.mysql import SessionLocal

    empty = {
        "available": False,
        "error": "数据库读取失败",
        "database_total": None,
        "database_boss_total": None,
        "database_new_count": None,
        "platform_counts": [],
        "latest_crawled_at": None,
        "data_quality": {
            "empty_source_detail": None,
            "duplicate_source_detail": None,
            "placeholder_empty_url": None,
            "duties_nonempty": None,
            "status_distribution": [],
        },
    }
    db = None
    try:
        db = SessionLocal()
        total = db.execute(text("SELECT COUNT(*) FROM jd_pool")).scalar() or 0
        boss_total = db.execute(text("SELECT COUNT(*) FROM jd_pool WHERE source='boss'")).scalar() or 0
        latest = db.execute(text("SELECT MAX(crawled_at) FROM jd_pool")).scalar()
        empty_source_detail = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE source_detail IS NULL OR source_detail=''"
        )).scalar() or 0
        duplicate_source_detail = db.execute(text(
            "SELECT COUNT(*) FROM (SELECT source_detail FROM jd_pool "
            "WHERE source_detail IS NOT NULL AND source_detail<>'' "
            "GROUP BY source, source_detail HAVING COUNT(*) > 1) t"
        )).scalar() or 0
        placeholder_empty_url = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE "
            "(source_detail LIKE '%placeholder%' OR source_detail LIKE '%example.com%')"
        )).scalar() or 0
        duties_nonempty = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE duties IS NOT NULL AND duties<>''"
        )).scalar() or 0
        status_rows = db.execute(text(
            "SELECT status, COUNT(*) AS count FROM jd_pool GROUP BY status ORDER BY status"
        )).mappings().all()
        platform_rows = db.execute(text(
            "SELECT source, COUNT(*) AS count FROM jd_pool GROUP BY source ORDER BY source"
        )).mappings().all()
        return {
            "available": True,
            "error": None,
            "database_total": int(total),
            "database_boss_total": int(boss_total),
            "database_new_count": None,
            "platform_counts": [{"platform": row["source"], "label": {"boss": "BOSS", "zhaopin": "智联", "liepin": "猎聘"}.get(row["source"], row["source"]), "count": int(row["count"])} for row in platform_rows],
            "latest_crawled_at": latest.isoformat() if hasattr(latest, "isoformat") else str(latest or "") or None,
            "data_quality": {
                "empty_source_detail": int(empty_source_detail),
                "duplicate_source_detail": int(duplicate_source_detail),
                "placeholder_empty_url": int(placeholder_empty_url),
                "duties_nonempty": int(duties_nonempty),
                "status_distribution": [
                    {"status": row["status"], "count": int(row["count"])} for row in status_rows
                ],
            },
        }
    except Exception:
        return empty
    finally:
        if db is not None:
            db.close()


def get_recent_raw(limit: int = 10) -> list[dict[str, Any]]:
    """只读：返回 jd_pool 最新采集的原始 JD（默认 10 条），供采集页数据展示。"""
    from sqlalchemy import text
    from app.db.mysql import SessionLocal

    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id, source, job_title, quality, crawled_at, "
            "CASE WHEN NULLIF(duties, '') IS NOT NULL THEN duties ELSE raw_text END AS body "
            "FROM jd_pool ORDER BY crawled_at DESC, id DESC LIMIT :limit"
        ), {"limit": int(limit)}).mappings().all()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            body = str(item.pop("body", "") or "").strip()
            item["content"] = body if len(body) <= 300 else body[:300] + "…"
            crawled = item.get("crawled_at")
            if crawled is not None and hasattr(crawled, "isoformat"):
                item["crawled_at"] = crawled.isoformat()
            items.append(item)
        return items
    finally:
        db.close()


def get_status() -> dict[str, Any]:
    with _LOCK:
        state = _load_state()
        task = dict(state.get("current_task") or {**_empty_task(None, state["config"]), "status": "idle", "started_at": None})
        if _PROCESS is not None and _PROCESS.poll() is None:
            task["status"] = task.get("status") if task.get("status") in _ACTIVE_STATUSES else "running"
        elif _PROCESS is None and task.get("run_id") and task.get("status") in _ACTIVE_STATUSES and not task.get('finished_at') and task.get('run_id') != _STARTING_RUN:
            task["status"] = "error"
            task["last_error"] = task.get("last_error") or "采集进程已退出"
            task['stop_reason'] = task.get('stop_reason') or 'controller_restarted'
            task['pid'] = None
            task['finished_at'] = _now()
            state['history'] = [dict(task)] + [h for h in state.get('history', []) if h.get('run_id') != task['run_id']]
        stats = get_database_stats()
        task.update({
            "database_total": stats["database_total"],
            "database_boss_total": stats["database_boss_total"],
            "database_new_count": task.get("new", 0),
        })
        state["current_task"] = task if task.get("run_id") else None
        _save_state(state)
        return task


def get_config() -> dict[str, Any]:
    with _LOCK:
        config = dict(_load_state()['config'])
        # Present bounded defaults for pre-Gate state files; do not rewrite historical evidence.
        config.update(mode='once', rounds=0, pages=1)
        for key in ('max_jobs', 'detail_limit'):
            value = config.get(key)
            config[key] = min(5, max(1, value)) if type(value) is int else 5
        keywords = config.get('keywords')
        config['keywords'] = keywords[:1] if isinstance(keywords, list) and keywords else ['Python']
        spec = next((p for p in _PLATFORMS if p['platform'] == config.get('platform')), _PLATFORMS[0])
        config['platform'] = spec['platform']
        cities = config.get('cities')
        first = cities[0] if isinstance(cities, list) and cities else None
        config['cities'] = [first if first in spec['cities'] else dict(spec['cities'][0])]
        return config


def update_config(payload: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        state = _load_state()
        config = _validated_config(get_config(), payload)
        state['config'] = config
        _save_state(state)
        return dict(config)


def _legacy_log_files() -> list[Path]:
    log_dir = _REPO_ROOT / "data" / "local" / "logs"
    if not log_dir.exists():
        return []
    return sorted((path for path in log_dir.glob("*collect_loop*.out.log")
                   if any(token in path.name.lower() for token in ("boss", "zhaopin", "liepin"))),
                  key=lambda path: path.stat().st_mtime, reverse=True)


def _summarize_log(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        try:
            text_value = raw.decode("utf-8")
        except UnicodeDecodeError:
            text_value = raw.decode("gbk", errors="replace")
        lines = [line for line in text_value.splitlines() if not line.strip().startswith('TM_EVENT ')]
    except OSError:
        lines = []
    platform = "boss" if "boss" in path.name.lower() else "zhaopin" if "zhaopin" in path.name.lower() else "liepin" if "liepin" in path.name.lower() else "unknown"
    totals = {"listed": 0, "details": 0, "new": 0, "skipped": 0, "errors": 0}
    stop_reason = None
    parsed_rounds = quality_rounds = 0
    rounds = 0
    for line in lines:
        if "轮开始" in line:
            rounds += 1
        match = re.search(r"完成: (\{.*\})", line)
        if not match:
            continue
        try:
            payload = ast.literal_eval(match.group(1))
        except (ValueError, SyntaxError):
            continue
        if isinstance(payload, dict):
            parsed_rounds += 1
            quality_rounds += all(key in payload for key in _QUALITY_COUNTERS)
            for key in ('listed', 'details', 'new', 'skipped', 'errors'):
                totals[key] += int(payload.get(key, 0) or 0)
            for key in _QUALITY_COUNTERS:
                if key in payload:
                    totals[key] = totals.get(key, 0) + int(payload[key] or 0)
            if payload.get('stop_reason'):
                stop_reason = str(payload['stop_reason'])
                if not payload.get('errors'):
                    totals['errors'] += max(int(payload.get('failed', 0) or 0), 1)
    status = "error" if stop_reason or any("CDP/登录状态异常" in line or "需要人工登录" in line for line in lines) else "completed"
    timestamps = []
    for line in lines:
        match = re.match(r"\[([^]]+)\]", line)
        if match:
            timestamps.append(match.group(1))
    for key in _QUALITY_COUNTERS:
        if not parsed_rounds or parsed_rounds != quality_rounds:
            totals[key] = None
    if not parsed_rounds:
        totals.update(dict.fromkeys(('listed', 'details', 'new', 'skipped')))
        if status == 'completed':
            status = 'unknown'
    return {
        "run_id": f"legacy-{platform}-{path.stem}", "platform": platform, "status": status, "mode": "continuous",
        "started_at": timestamps[0] if timestamps else datetime.fromtimestamp(path.stat().st_ctime).astimezone().isoformat(timespec="seconds"),
        "finished_at": timestamps[-1] if timestamps else datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        "current_keyword": None, "current_city": None, "current_round": rounds, "total_rounds": None,
        **totals, "last_error": stop_reason or next((line.strip() for line in reversed(lines) if "异常" in line or "登录" in line), None),
        "stop_reason": stop_reason, "quality_metrics_available": bool(parsed_rounds) and parsed_rounds == quality_rounds,
        "next_run_at": None, "cdp_status": "unknown", "browser_page_status": None,
        "database_total": None, "database_boss_total": None, "database_new_count": totals["new"], "pid": None,
        "log_path": str(path), "log_summary": totals, "raw_log_tail": lines[-30:], "log_status": "parsed" if rounds or any(totals.values()) else "unrecognized",
    }


def _enrich_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known_paths = {str(item.get("log_path")) for item in history if item.get("log_path")}
    result = []
    for item in history:
        copy = dict(item)
        if copy.get("log_path") and Path(str(copy["log_path"])).exists():
            copy["log_status"] = "parsed" if copy.get("log_summary") or copy.get("raw_log_tail") else "empty"
        else:
            copy["log_status"] = "missing"
        result.append(copy)
    for path in _legacy_log_files():
        if str(path) not in known_paths:
            result.append(_summarize_log(path))
    return sorted(result, key=lambda item: str(item.get("started_at") or ""), reverse=True)

def get_history(page: int = 1, page_size: int = 20, status: str = "", mode: str = "", platform: str = "") -> dict[str, Any]:
    with _LOCK:
        history = _enrich_history(list(_load_state().get("history") or []))
    if status:
        history = [item for item in history if item.get("status") == status]
    if mode:
        history = [item for item in history if item.get("mode") == mode]
    if platform:
        history = [item for item in history if item.get("platform") == platform]
    start = max(page - 1, 0) * page_size
    return {"items": history[start:start + page_size], "total": len(history)}


def _worker_environment() -> dict[str, str]:
    from app.config import get_settings

    # Settings may come from .env without populating os.environ; workers need the same resolved target.
    env = os.environ.copy()
    env.update({key.upper(): str(value) for key, value in get_settings().model_dump().items() if value is not None})
    env['PYTHONUNBUFFERED'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    return env


def _archive_task(run_id: str, **changes) -> None:
    with _LOCK:
        state = _load_state()
        task = state.get('current_task')
        if not task or task.get('run_id') != run_id:
            return
        if task.get('status') in {'stopped', 'stopping'} and changes.get('status') != 'stopped':
            return
        task.update(changes, finished_at=_now(), pid=None, next_run_at=None)
        state['history'] = [dict(task)] + [h for h in state.get('history', []) if h.get('run_id') != run_id]
        state['history'] = state['history'][:100]
        _save_state(state)


def _reserve_tasks() -> object:
    global _RESERVATION
    with _LOCK:
        if _RESERVATION is not None or _PROCESS is not None or _STARTING_RUN is not None:
            raise RuntimeError('已有采集任务、批次或浏览器准备正在运行')
        _RESERVATION = object()
        return _RESERVATION


def _release_tasks(reservation: object) -> None:
    global _RESERVATION
    with _LOCK:
        if _RESERVATION is not reservation:
            raise RuntimeError('批次占用已失效')
        if _PROCESS is not None or _STARTING_RUN is not None:
            raise RuntimeError('采集尚未停止归档，不能释放批次占用')
        _RESERVATION = None


def _task_snapshot(run_id: str) -> dict[str, Any]:
    with _LOCK:
        state = _load_state()
        task = state.get('current_task') or {}
        if task.get('run_id') != run_id:
            task = next((h for h in state['history'] if h.get('run_id') == run_id), {})
        return dict(task)


def _wait_task_done(run_id: str, timeout: float) -> bool:
    with _LOCK:
        event = _DONE_EVENTS.get(run_id)
    return bool(event and event.wait(timeout))


def start_task(payload: dict[str, Any], *, _reservation: object | None = None) -> dict[str, Any]:
    global _START_THREAD, _STARTING_RUN
    with _LOCK:
        if _RESERVATION is not _reservation:
            raise RuntimeError('已有采集批次正在运行')
        if _PROCESS is not None or _STARTING_RUN is not None:
            raise RuntimeError('已有采集任务正在运行')
        state = _load_state()
        config = _validated_config(get_config(), payload)
        run_id = f"{config['platform']}-{uuid.uuid4().hex}"
        task = _empty_task(run_id, config)
        task['log_path'] = str(_STATE_DIR / f'{run_id}.out.log')
        state['current_task'] = task
        if _reservation is None:
            state['config'] = config
        _save_state(state)
        for previous in list(_DONE_EVENTS):
            if _DONE_EVENTS[previous].is_set():
                del _DONE_EVENTS[previous]
        _DONE_EVENTS[run_id] = threading.Event()
        _STARTING_RUN = run_id
        _START_THREAD = threading.Thread(target=_launch_task, args=(run_id, config), daemon=True)
        _START_THREAD.start()
        return {'run_id': run_id}


def _launch_task(run_id: str, config: dict[str, Any]) -> None:
    global _PROCESS, _STARTING_RUN
    spawned = False
    try:
        platform = config['platform']
        cdp = _ensure_browser(config['cdp_endpoint'], config['user_data_dir'], platform, _search_target(config))
        access = cdp['platform_access'][platform]
        with _LOCK:
            state = _load_state()
            task = state.get('current_task') or {}
            if task.get('run_id') != run_id or task.get('status') in {'stopped', 'stopping'}:
                return
            if not access['can_collect']:
                _archive_task(run_id, status='waiting_for_browser', stop_reason=access['access_state'],
                              browser_page_status=access['access_state'], last_error='请人工完成浏览器准备后重新启动')
                return
            endpoint = cdp['endpoint']
            config = {**config, 'cdp_endpoint': endpoint, 'user_data_dir': cdp['user_data_dir']}
            task['cdp_status'] = 'page_available'
            task['browser_page_status'] = access['access_state']
            env = _worker_environment()
            env['TALENTMIND_COLLECTION_EVENTS'] = '1'
            _spawn_worker(run_id, config, task, state, env)
            spawned = True
    except Exception as exc:
        _archive_task(run_id, status='error', stop_reason=type(exc).__name__, last_error=str(exc))
    finally:
        with _LOCK:
            if _STARTING_RUN == run_id:
                _STARTING_RUN = None
            if not spawned:
                state = _load_state()
                task = state.get('current_task') or {}
                if task.get('run_id') == run_id and task.get('status') == 'stopping':
                    _archive_task(run_id, status='stopped', stop_reason='user_stopped')
                if run_id in _DONE_EVENTS:
                    _DONE_EVENTS[run_id].set()


def _spawn_worker(run_id: str, config: dict, task: dict, state: dict, env: dict) -> None:
    global _PROCESS
    platform = config['platform']
    endpoint = config['cdp_endpoint']
    keywords = config.get("keywords") or list(DEFAULT_KEYWORDS)
    cities = config.get("cities") or [{"name": name, "code": code} for name, code in DEFAULT_CITIES]
    city_arg = ",".join(
        f"{item.get('name', '')}={item.get('code', '')}" if isinstance(item, dict) else str(item)
        for item in cities
    )
    module = "app.collect.boss_collect_loop" if platform == "boss" else "app.collect.cn_collect_loop"
    args = [
        sys.executable, "-m", module,
        "--platform", platform,
        "--cdp", endpoint,
        "--keywords", ",".join(str(item) for item in keywords),
        "--cities", city_arg,
        "--pages", str(int(config.get("pages", 1))),
        "--detail-limit", str(int(config.get("detail_limit", 8))),
        "--max-jobs", str(int(config.get("max_jobs", 12))),
        "--page-delay-min", str(float(config.get("page_delay_min", 15))),
        "--page-delay-max", str(float(config.get("page_delay_max", 30))),
        "--settle-min", str(float(config.get("settle_min", 5))),
        "--settle-max", str(float(config.get("settle_max", 10))),
        "--switch-interval-min", str(float(config.get("switch_interval_min", 360))),
        "--switch-interval-max", str(float(config.get("switch_interval_max", 720))),
    ]
    if platform == "boss":
        args.remove("--platform")
        args.remove(platform)
    if config.get("user_data_dir"):
        args.extend(["--user-data-dir", str(config["user_data_dir"])])
    if platform != 'boss' and config.get('search_url_template'):
        args.extend(['--search-url-template', str(config['search_url_template'])])
    if config["mode"] == "once":
        args.append("--once")
    elif config["mode"] == "limited":
        args.extend(["--rounds", str(int(config["rounds"]))])
    else:
        args.append("--forever")
    _PROCESS = _spawn_process(
        args,
        cwd=str(_REPO_ROOT / "backend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    task["status"] = "running"
    task["pid"] = _PROCESS.pid
    state["current_task"] = task
    _save_state(state)
    threading.Thread(target=_watch_process, args=(run_id, _PROCESS), daemon=True).start()


def stop_task(run_id: str | None = None) -> dict[str, Any]:
    with _LOCK:
        state = _load_state()
        task = state.get("current_task")
        if not task or (run_id and task.get("run_id") != run_id):
            raise ValueError("没有可停止的当前采集任务")
        if task.get('finished_at') and _PROCESS is None and task.get('run_id') != _STARTING_RUN:
            return {'stopped': False, 'run_id': task['run_id']}
        process = _PROCESS
        selected_run = task['run_id']
        done = _DONE_EVENTS.get(selected_run)
        task["status"] = "stopping"
        task['stop_reason'] = 'user_stopped'
        task["next_run_at"] = None
        state["current_task"] = task
        _save_state(state)
    if process is not None:
        worker_process.stop(process, timeout=10)
    if done is not None and not done.wait(timeout=5):
        if process is None:
            return {'stopped': False, 'status': 'stopping', 'run_id': selected_run}
        raise RuntimeError('采集进程已停止，任务归档尚未完成；请保留后端并重试')
    with _LOCK:
        state = _load_state()
        archived = next((h for h in state.get('history', []) if h.get('run_id') == selected_run), None)
        if archived is None:
            raise RuntimeError('无法确认停止任务已归档，请保留后端')
    return {'stopped': True, 'status': 'stopped', 'run_id': selected_run}
