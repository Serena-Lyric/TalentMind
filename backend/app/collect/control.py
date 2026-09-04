"""M1 中文平台采集控制器。

只负责把现有采集循环包装为可观察的本地任务，不重写采集器。
运行状态和历史写入 `data/local/collection/`，该目录属于本地运行态，不入库。
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.collect.boss_collect_loop import DEFAULT_CITIES, DEFAULT_KEYWORDS
from app.collect.fetchers.job_sites import SITES
from app.collect.fetchers.cdp import CdpClient, CdpError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STATE_DIR = _REPO_ROOT / "data" / "local" / "collection"
_STATE_PATH = _STATE_DIR / "control-state.json"
_LOCK = threading.RLock()
_PROCESS: subprocess.Popen[str] | None = None
_ACTIVE_STATUSES = {"preparing", "waiting_for_browser", "running", "waiting_next_round"}
_DEFAULT_CONFIG: dict[str, Any] = {
    "platform": "boss",
    "mode": "once",
    "keywords": list(DEFAULT_KEYWORDS),
    "cities": [{"name": name, "code": code} for name, code in DEFAULT_CITIES],
    "pages": 1,
    "detail_limit": 8,
    "max_jobs": 12,
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
}


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
        "listed": 0,
        "details": 0,
        "new": 0,
        "skipped": 0,
        "errors": 0,
        "last_error": None,
        "next_run_at": None,
        "cdp_status": "unknown",
        "browser_page_status": None,
        "database_total": 0,
        "database_boss_total": 0,
        "database_new_count": 0,
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
    start_match = re.search(r"(?:BOSS|zhaopin|liepin) 第 (\d+) 轮开始: ([^/]+)/([^;]+);", clean, re.I)
    if start_match:
        _update_task(run_id, status="running", current_round=int(start_match.group(1)),
                     current_city=start_match.group(2).strip(), current_keyword=start_match.group(3).strip(),
                     raw_log_line=clean)
        return
    if "等待" in clean and "后切换" in clean:
        _update_task(run_id, status="waiting_next_round", raw_log_line=clean)
        return
    if "CDP/登录状态异常" in clean or "需要人工登录" in clean or ("验证" in clean and "异常" in clean):
        _update_task(run_id, status="error", last_error=clean, raw_log_line=clean)
        return
    complete_match = re.search(r"完成: (\{.*\})", clean)
    if complete_match:
        try:
            payload = ast.literal_eval(complete_match.group(1))
        except (ValueError, SyntaxError):
            payload = {}
        if isinstance(payload, dict):
            _update_task(run_id, listed=int(payload.get("listed", 0) or 0), details=int(payload.get("details", 0) or 0),
                         new=int(payload.get("new", 0) or 0), skipped=int(payload.get("skipped", 0) or 0),
                         errors=int(payload.get("errors", 0) or 0), log_summary=payload, raw_log_line=clean)
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
                stopped = task.get("status") == "stopped"
                if not stopped:
                    task["status"] = "completed" if return_code == 0 else "error"
                    if return_code != 0 and not task.get("last_error"):
                        task["last_error"] = f"采集进程退出码: {return_code}"
                task["finished_at"] = _now()
                task["next_run_at"] = None
                task["pid"] = None
                task["database_new_count"] = task.get("new", 0)
                task["log_path"] = str(log_path)
                history = state.setdefault("history", [])
                history.insert(0, dict(task))
                state["history"] = history[:100]
                _save_state(state)
            _PROCESS = None


def _find_edge_executable() -> str | None:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _launch_edge(endpoint: str, user_data_dir: str | None, platform: str = "boss") -> int:
    executable = _find_edge_executable()
    if not executable:
        raise RuntimeError("未找到 Microsoft Edge，无法自动拉起浏览器")
    port = endpoint.rsplit(":", 1)[-1].split("/", 1)[0]
    profile = Path(user_data_dir or (_REPO_ROOT / "data" / "local" / "edge-boss-cdp-profile")).expanduser()
    profile.mkdir(parents=True, exist_ok=True)
    entry_url = {"boss": "https://www.zhipin.com/", "zhaopin": "https://www.zhaopin.com/", "liepin": "https://www.liepin.com/"}.get(platform, "https://www.zhipin.com/")
    process = subprocess.Popen(
        [executable, f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", "--new-window", entry_url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return int(process.pid)


def _ensure_browser(endpoint: str, user_data_dir: str | None, platform: str = "boss") -> dict[str, Any]:
    current = get_cdp_status(endpoint, user_data_dir)
    if current["reachable"]:
        return current
    _launch_edge(endpoint, user_data_dir, platform)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        time.sleep(0.5)
        current = get_cdp_status(endpoint, user_data_dir)
        if current["reachable"]:
            return current
    return current


def _page_login_state(endpoint: str, user_data_dir: str | None, pages: list[dict[str, Any]], host_hint: str = "zhipin.com") -> bool:
    """Inspect visible page text only for a login gate; never reads credentials."""
    if not pages:
        return False
    try:
        client = CdpClient.connect_first_page(endpoint, target_url_contains=host_hint, user_data_dir=user_data_dir)
        try:
            snapshot = client.evaluate("""({url: location.href, title: document.title, text: (document.body?.innerText || '').slice(0, 3000)})""") or {}
        finally:
            client.close()
        url = str(snapshot.get("url", "")).lower()
        text_value = f"{url} {snapshot.get('title', '')} {snapshot.get('text', '')}".lower()
        markers = ("请先登录", "登录后", "手机号登录", "扫码登录", "密码登录", "登录/注册")
        return any(marker in text_value for marker in markers) or any(marker in url for marker in ("/login", "passport"))
    except (CdpError, OSError, ValueError, KeyError):
        return False


def get_cdp_status(endpoint: str | None = None, user_data_dir: str | None = None) -> dict[str, Any]:
    import httpx

    endpoint = (endpoint or _DEFAULT_CONFIG["cdp_endpoint"]).rstrip("/")
    user_data_dir = user_data_dir or _DEFAULT_CONFIG["user_data_dir"]
    checked_at = _now()
    try:
        response = httpx.get(f"{endpoint}/json/list", timeout=3, trust_env=False)
        response.raise_for_status()
        targets = response.json()
        if not isinstance(targets, list):
            targets = []
        pages = [target for target in targets if target.get("type") == "page"]
        page_groups = {"boss": [target for target in pages if "zhipin.com" in str(target.get("url", "")) or "boss.com" in str(target.get("url", "")) or "BOSS" in str(target.get("title", ""))]}
        for source, spec in SITES.items():
            page_groups[source] = [target for target in pages if spec.host_hint in str(target.get("url", ""))]
        boss_pages = page_groups["boss"]
        login_required = _page_login_state(endpoint, user_data_dir, boss_pages, "zhipin.com")
        platform_login_required = {"boss": login_required}
        for source, spec in SITES.items():
            platform_login_required[source] = _page_login_state(endpoint, user_data_dir, page_groups[source], spec.host_hint)
        return {
            "endpoint": endpoint,
            "reachable": True,
            "boss_page_count": len(boss_pages),
            "platform_pages": {source: len(items) for source, items in page_groups.items()},
            "platform_login_required": platform_login_required,
            "login_required": login_required,
            "last_checked_at": checked_at,
            "page_targets": [
                {"type": t.get("type", ""), "url": t.get("url", ""), "title": t.get("title", "")}
                for t in pages[:20]
            ],
        }
    except Exception as exc:
        return {
            "endpoint": endpoint,
            "reachable": False,
            "boss_page_count": 0,
            "platform_pages": {"boss": 0, **{source: 0 for source in SITES}},
            "platform_login_required": {"boss": False, **{source: False for source in SITES}},
            "last_checked_at": checked_at,
            "page_targets": [],
            "login_required": False,
            "error": str(exc),
        }


def prepare_browser(auto_start: bool = False, platform: str | None = None) -> dict[str, Any]:
    """Open the controlled Edge profile, inspect login state, and optionally start one task."""
    config = {**get_config(), **({"platform": platform} if platform else {})}
    endpoint = str(config.get("cdp_endpoint") or _DEFAULT_CONFIG["cdp_endpoint"])
    platform = str(config.get("platform") or "boss")
    try:
        cdp = _ensure_browser(endpoint, config.get("user_data_dir"), platform)
    except TypeError:
        cdp = _ensure_browser(endpoint, config.get("user_data_dir"))
    if not cdp.get("reachable"):
        return {"status": "cdp_unavailable", "cdp": cdp, "message": "无法连接 Edge CDP"}
    platform = str(config.get("platform") or "boss")
    platform_pages = cdp.get("platform_pages", {})
    login_required = (cdp.get("platform_login_required") or {}).get(platform, cdp.get("login_required", False))
    if login_required or not platform_pages.get(platform, cdp.get("boss_page_count", 0)):
        label = {"boss": "BOSS", "zhaopin": "智联", "liepin": "猎聘"}.get(platform, platform)
        return {"status": "login_required", "cdp": cdp, "message": f"请在已打开的 Edge {label} 页面完成登录并打开岗位页面"}
    if auto_start:
        try:
            # 自动进入页面只触发单轮，持续采集仍需用户在控制台显式选择并启动。
            task = start_task({"mode": "once", "rounds": 0, **({"platform": platform} if platform != "boss" else {})})
            return {"status": "started", "cdp": cdp, "task": task, "message": "已登录，单轮采集任务已启动"}
        except (ValueError, RuntimeError) as exc:
            return {"status": "start_failed", "cdp": cdp, "message": str(exc)}
    return {"status": "ready", "cdp": cdp, "message": "浏览器已连接，可以启动采集"}

def get_database_stats() -> dict[str, Any]:
    from sqlalchemy import text
    from app.db.mysql import SessionLocal

    empty = {
        "database_total": 0,
        "database_boss_total": 0,
        "database_new_count": 0,
        "platform_counts": [],
        "latest_crawled_at": None,
        "data_quality": {
            "empty_source_detail": 0,
            "duplicate_source_detail": 0,
            "placeholder_empty_url": 0,
            "duties_nonempty": 0,
            "status_distribution": [],
        },
    }
    db = SessionLocal()
    try:
        total = db.execute(text("SELECT COUNT(*) FROM jd_pool")).scalar() or 0
        boss_total = db.execute(text("SELECT COUNT(*) FROM jd_pool WHERE source='boss'")).scalar() or 0
        latest = db.execute(text("SELECT MAX(crawled_at) FROM jd_pool WHERE source='boss'")).scalar()
        empty_source_detail = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE source='boss' AND (source_detail IS NULL OR source_detail='')"
        )).scalar() or 0
        duplicate_source_detail = db.execute(text(
            "SELECT COUNT(*) FROM (SELECT source_detail FROM jd_pool "
            "WHERE source='boss' AND source_detail IS NOT NULL AND source_detail<>'' "
            "GROUP BY source_detail HAVING COUNT(*) > 1) t"
        )).scalar() or 0
        placeholder_empty_url = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE source='boss' AND "
            "(source_detail LIKE '%placeholder%' OR source_detail LIKE '%example.com%')"
        )).scalar() or 0
        duties_nonempty = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE source='boss' AND duties IS NOT NULL AND duties<>''"
        )).scalar() or 0
        status_rows = db.execute(text(
            "SELECT status, COUNT(*) AS count FROM jd_pool WHERE source='boss' GROUP BY status ORDER BY status"
        )).mappings().all()
        platform_rows = db.execute(text(
            "SELECT source, COUNT(*) AS count FROM jd_pool WHERE source IN ('boss','zhaopin','liepin') GROUP BY source ORDER BY source"
        )).mappings().all()
        return {
            "database_total": int(total),
            "database_boss_total": int(boss_total),
            "database_new_count": 0,
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
        elif task.get("run_id") and task.get("status") in _ACTIVE_STATUSES:
            task["status"] = "error"
            task["last_error"] = task.get("last_error") or "采集进程已退出"
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
        return dict(_load_state()["config"])


def update_config(payload: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        state = _load_state()
        config = state["config"]
        for key in _DEFAULT_CONFIG:
            if key in payload and payload[key] is not None:
                config[key] = payload[key]
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
        lines = text_value.splitlines()
    except OSError:
        lines = []
    platform = "boss" if "boss" in path.name.lower() else "zhaopin" if "zhaopin" in path.name.lower() else "liepin" if "liepin" in path.name.lower() else "unknown"
    totals = {"listed": 0, "details": 0, "new": 0, "skipped": 0, "errors": 0}
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
            for key in totals:
                totals[key] += int(payload.get(key, 0) or 0)
    status = "error" if any("CDP/登录状态异常" in line or "需要人工登录" in line for line in lines) else "completed"
    timestamps = []
    for line in lines:
        match = re.match(r"\[([^]]+)\]", line)
        if match:
            timestamps.append(match.group(1))
    return {
        "run_id": f"legacy-{platform}-{path.stem}", "platform": platform, "status": status, "mode": "continuous",
        "started_at": timestamps[0] if timestamps else datetime.fromtimestamp(path.stat().st_ctime).astimezone().isoformat(timespec="seconds"),
        "finished_at": timestamps[-1] if timestamps else datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        "current_keyword": None, "current_city": None, "current_round": rounds, "total_rounds": None,
        **totals, "last_error": next((line.strip() for line in reversed(lines) if "异常" in line or "登录" in line), None),
        "next_run_at": None, "cdp_status": "unknown", "browser_page_status": None,
        "database_total": 0, "database_boss_total": 0, "database_new_count": totals["new"], "pid": None,
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


def start_task(payload: dict[str, Any]) -> dict[str, Any]:
    global _PROCESS
    with _LOCK:
        if _PROCESS is not None and _PROCESS.poll() is None:
            raise RuntimeError("已有采集任务正在运行")
        config = {**get_config(), **{k: v for k, v in payload.items() if v is not None}}
        config["mode"] = payload.get("mode") or config.get("mode") or "once"
        if config["mode"] not in {"once", "limited", "continuous"}:
            raise ValueError("mode 必须为 once、limited 或 continuous")
        if config["mode"] == "limited" and int(config.get("rounds", 0) or 0) < 1:
            raise ValueError("有限轮模式需要 rounds >= 1")
        platform = str(config.get("platform") or "boss")
        if platform not in {"boss", "zhaopin", "liepin"}:
            raise ValueError("platform 必须为 boss、zhaopin 或 liepin")
        endpoint = str(config.get("cdp_endpoint") or _DEFAULT_CONFIG["cdp_endpoint"])
        if bool(config.get("check_cdp_before_start", True)):
            cdp = _ensure_browser(endpoint, config.get("user_data_dir"), platform)
            if not cdp["reachable"]:
                raise RuntimeError("浏览器已尝试启动但 CDP 仍不可达，请检查 Edge 是否被策略阻止")
            pages = cdp.get("platform_pages", {})
            login_required = (cdp.get("platform_login_required") or {}).get(platform, cdp.get("login_required", False))
            if login_required or not pages.get(platform, cdp.get("boss_page_count", 0)):
                label = {"boss": "BOSS", "zhaopin": "智联", "liepin": "猎聘"}[platform]
                raise RuntimeError(f"浏览器已打开，请先登录{label}并打开岗位页面，再点击启动采集")
        run_id = f"{platform}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        state = _load_state()
        task = _empty_task(run_id, config)
        task["log_path"] = str(_STATE_DIR / f"{run_id}.out.log")
        task["cdp_status"] = "page_available"
        state["config"] = config
        state["current_task"] = task
        _save_state(state)

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
        if config["mode"] == "once":
            args.append("--once")
        elif config["mode"] == "limited":
            args.extend(["--rounds", str(int(config["rounds"]))])
        else:
            args.append("--forever")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        _PROCESS = subprocess.Popen(
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
        return {"run_id": run_id}


def stop_task(run_id: str | None = None) -> dict[str, Any]:
    global _PROCESS
    with _LOCK:
        state = _load_state()
        task = state.get("current_task")
        if not task or (run_id and task.get("run_id") != run_id):
            raise ValueError("没有可停止的当前采集任务")
        if _PROCESS is None or _PROCESS.poll() is not None:
            task["status"] = "stopped"
            task["finished_at"] = _now()
            state["current_task"] = task
            _save_state(state)
            return {"stopped": False, "run_id": task.get("run_id")}
        _PROCESS.terminate()
        task["status"] = "stopped"
        task["finished_at"] = _now()
        task["next_run_at"] = None
        state["current_task"] = task
        _save_state(state)
        return {"stopped": True, "run_id": task.get("run_id")}