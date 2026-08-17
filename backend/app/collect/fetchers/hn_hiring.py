"""HN "Who is hiring" 采集（D40）：Algolia 官方公开 API → 技术岗 JD → RawJD（source=hn）。

合规：hn.algolia.com 为官方公开 API，无需登录、无 robots 限制；限速抓取。
"""
from __future__ import annotations
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.collect.schema import RawJD

ALGOLIA = "https://hn.algolia.com/api/v1"
HIRING_QUERY = "Who is hiring"
MIN_COMMENT_LEN = 80  # 岗位评论足够长；过短视为讨论


def _month_start_ts() -> int:
    now = datetime.now(timezone.utc)
    return int(datetime(now.year, now.month, 1, tzinfo=timezone.utc).timestamp())


def find_current_hiring_post(client: httpx.Client,
                             month_start: int | None = None) -> str | None:
    """返回当月 'Ask HN: Who is hiring? (Month Year)' 帖 objectID。"""
    month_start = month_start or _month_start_ts()
    resp = client.get(ALGOLIA + "/search", params={
        "tags": "story", "query": HIRING_QUERY,
        "numericFilters": f"created_at_i>{month_start}", "hitsPerPage": 10,
    })
    if resp.status_code != 200:
        return None
    for h in resp.json().get("hits", []):
        title = (h.get("title") or "").lower()
        if "who is hiring" in title and "ask hn" in title:
            return str(h["objectID"])
    return None


def fetch_hiring_comments(client: httpx.Client, object_id: str) -> list[dict]:
    """Algolia items API 返回帖子及其评论树；展平为顶层岗位评论。"""
    resp = client.get(f"{ALGOLIA}/items/{object_id}")
    if resp.status_code != 200:
        return []
    data = resp.json()
    out: list[dict] = []
    for child in data.get("children", []):
        text = (child.get("text") or "").strip()
        if len(text) >= MIN_COMMENT_LEN:
            out.append({"author": child.get("author", ""), "text": text})
    return out


def _strip_html(text: str) -> str:
    """HN 评论为 HTML（<p>/<a> 等），剥离为纯文本（换行保留），避免污染 job_title/raw_text。"""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text("\n")


def comments_to_rawjds(comments: list[dict], item_id: str) -> list[RawJD]:
    """每条岗位评论 → RawJD。先剥 HTML，job_title 取首行（可能含公司名，M1/M2 后续清洗）。"""
    raws: list[RawJD] = []
    for c in comments:
        text = _strip_html(c["text"]).strip()
        if not text:
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        title = lines[0][:128] if lines else "HN hiring"
        raws.append(RawJD(
            source="hn",
            job_title=title,
            raw_html=text,
            source_detail=f"https://news.ycombinator.com/item?id={item_id}",
        ))
    return raws


def fetch_hn_hiring_rawjds(client: httpx.Client,
                           limit: int = 0) -> tuple[list[RawJD], str | None]:
    """抓取当月 Who-is-hiring 帖 → RawJD 列表 + 帖 objectID。"""
    item_id = find_current_hiring_post(client)
    if not item_id:
        return [], None
    comments = fetch_hiring_comments(client, item_id)
    raws = comments_to_rawjds(comments, item_id)
    if limit > 0:
        raws = raws[:limit]
    return raws, item_id
