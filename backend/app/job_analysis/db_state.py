"""SQLite 状态层 —— 记录级断点 / 去重 / 增量 / 模型统计。"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import DATA_DIR
from .models import JdRecord


@dataclass
class IngestStats:
    new: int = 0
    dup_skipped: int = 0
    pipeline_ready: int = 0


def simhash(text: str, n: int = 3) -> str:
    """64-bit char n-gram simhash，十六进制字符串。"""
    text = re.sub(r"\s+", " ", text.lower().strip())
    v = [0] * 64
    seen: set[str] = set()
    for i in range(len(text) - n + 1):
        gram = text[i:i + n]
        if gram in seen:
            continue
        seen.add(gram)
        h = int.from_bytes(hashlib.md5(gram.encode()).digest()[:8], "big")
        for b in range(64):
            v[b] += 1 if (h >> b) & 1 else -1
    bits = sum((1 << b) for b in range(64) if v[b] > 0)
    return f"{bits:016x}"


def _info_density(r: JdRecord) -> int:
    t = re.sub(r"\s+", "", r.raw_text + r.duties)
    return len(t)


class StateDB:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DATA_DIR / "state.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS records (
              id INTEGER PRIMARY KEY,
              content_hash TEXT,
              source TEXT, job_title TEXT, raw_text TEXT, duties TEXT,
              experience TEXT, quality REAL, dup_group TEXT, crawled_at TEXT,
              status TEXT DEFAULT 'pending',
              reject_reason TEXT,
              cross_source INTEGER DEFAULT 0,
              seg_text TEXT,
              s1_json TEXT, s2_json TEXT, s3_json TEXT, verify_json TEXT,
              created_at TEXT, updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_status ON records(status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_hash ON records(content_hash);
            CREATE TABLE IF NOT EXISTS stats (
              model TEXT, stage TEXT, day TEXT,
              calls INTEGER DEFAULT 0, ok INTEGER DEFAULT 0,
              err_429 INTEGER DEFAULT 0, err_5xx INTEGER DEFAULT 0,
              err_timeout INTEGER DEFAULT 0,
              total_latency_ms INTEGER DEFAULT 0,
              prompt_tokens INTEGER DEFAULT 0,
              completion_tokens INTEGER DEFAULT 0,
              hallucination_removed INTEGER DEFAULT 0,
              PRIMARY KEY (model, stage, day)
            );
            """
        )
        self._conn.commit()

    # ── ingest ──
    def ingest(self, records: list[JdRecord],
               cross_source_ids: set[int] | None = None,
               force: bool = False) -> IngestStats:
        cross = cross_source_ids or set()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        stats = IngestStats()
        # dup_group 内保留 quality+密度最高者
        groups: dict[str, list[JdRecord]] = {}
        singles: list[JdRecord] = []
        for r in records:
            if r.dup_group.strip():
                groups.setdefault(r.dup_group, []).append(r)
            else:
                singles.append(r)
        to_insert: list[tuple[JdRecord, bool]] = []
        for gid, group in groups.items():
            group.sort(key=lambda x: (x.quality, _info_density(x)),
                       reverse=True)
            to_insert.append((group[0], True))    # grouped: simhash 不适用
            for r in group[1:]:
                self._insert_skipped(r, now, f"dup_group={gid}", group[0].id)
                stats.dup_skipped += 1
        for r in singles:
            to_insert.append((r, False))

        for r, is_grouped in to_insert:
            existing = self.get_record(r.id)
            if existing is not None:
                if force:
                    # --force：重置已处理记录，重走各阶段
                    self._conn.execute(
                        "UPDATE records SET status='pending', "
                        "s1_json=NULL, s2_json=NULL, s3_json=NULL, "
                        "verify_json=NULL, seg_text=NULL, "
                        "reject_reason=NULL WHERE id=?", (r.id,))
                    stats.new += 1
                else:
                    # 增量：内容变了才重跑（同 id 不同指纹）
                    h = simhash(r.raw_text[:2000])
                    old_h = existing.get("content_hash")
                    if old_h is not None and old_h.startswith("g:"):
                        old_h = old_h[2:]   # grouped 记录比较时去掉前缀
                    if old_h != h:
                        self._conn.execute(
                            "UPDATE records SET raw_text=?, job_title=?, "
                            "source=?, quality=?, dup_group=?, "
                            "content_hash=?, status='pending', "
                            "s1_json=NULL, s2_json=NULL, s3_json=NULL, "
                            "verify_json=NULL, seg_text=NULL, "
                            "reject_reason=NULL WHERE id=?",
                            (r.raw_text, r.job_title, r.source, r.quality,
                             r.dup_group, h, r.id))
                        stats.new += 1      # 变化 = 需要重跑
                    else:
                        stats.dup_skipped += 1  # 未变 = 跳过
                continue
            # simhash 兜底只用于无 dup_group 的记录（唯一索引 NULL 不冲突）
            # grouped 记录用前缀假指纹（不撞唯一索引，但可做增量对比）
            h = ("g:" + simhash(r.raw_text[:2000])) if is_grouped \
                else simhash(r.raw_text[:2000])
            try:
                self._conn.execute(
                    """INSERT INTO records
                       (id, content_hash, source, job_title, raw_text, duties,
                        experience, quality, dup_group, crawled_at, status,
                        cross_source, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?, 'pending', ?, ?, ?)""",
                    (r.id, h, r.source, r.job_title, r.raw_text, r.duties,
                     r.experience, r.quality, r.dup_group, r.crawled_at,
                     1 if r.id in cross else 0, now, now))
            except sqlite3.IntegrityError:
                # simhash 指纹撞上已有记录
                stats.dup_skipped += 1
                continue
            stats.new += 1
        self._commit()
        stats.pipeline_ready = stats.new
        return stats

    def _insert_skipped(self, r: JdRecord, now: str, reason: str,
                        kept_id: int) -> None:
        if self.get_record(r.id) is not None:
            return
        self._conn.execute(
            """INSERT INTO records
               (id, content_hash, source, job_title, raw_text, duties,
                experience, quality, dup_group, crawled_at, status,
                reject_reason, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,'dup_skip',?,?,?)""",
            (r.id, None, r.source, r.job_title, r.raw_text, r.duties,
             r.experience, r.quality, r.dup_group, r.crawled_at,
             f"{reason}, kept_jd_id={kept_id}", now, now))

    # ── 记录级断点 ──
    def get_record(self, jd_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM records WHERE id=?", (jd_id,)).fetchone()
        return dict(row) if row else None

    def rows_where(self, status: str, limit: int = 0) -> list[dict]:
        q = "SELECT * FROM records WHERE status=?"
        if limit:
            q += f" LIMIT {int(limit)}"
        return [dict(r) for r in self._conn.execute(q, (status,)).fetchall()]

    def pending(self, stage: str) -> list[dict]:
        """该阶段未完成的记录（status 未到该阶段且未 reject）。"""
        if stage == "s1":
            q = "SELECT * FROM records WHERE status='pending'"
        elif stage == "s2":
            q = "SELECT * FROM records WHERE status='s1_pass'"
        elif stage == "s3":
            q = "SELECT * FROM records WHERE status='s2_pass'"
        elif stage == "verify":
            q = "SELECT * FROM records WHERE status='s3_pass'"
        else:
            return []
        return [dict(r) for r in self._conn.execute(q).fetchall()]

    def mark_done(self, jd_id: int, stage: str, verdict: str,
                  result: dict | None = None) -> None:
        col = {"s1": "s1_json", "s2": "s2_json",
               "s3": "s3_json", "verify": "verify_json"}.get(stage)
        if verdict == "reject":
            self._conn.execute(
                "UPDATE records SET status='rejected', reject_reason=? "
                "WHERE id=?", (f"{stage}_reject", jd_id))
        elif verdict == "manual":
            self._conn.execute(
                "UPDATE records SET status='manual' WHERE id=?", (jd_id,))
        else:
            nxt = {"s1": "s1_pass", "s2": "s2_pass",
                   "s3": "s3_pass", "verify": "done"}[stage]
            self._conn.execute(
                "UPDATE records SET status=? WHERE id=?", (nxt, jd_id))
        if col and result:
            self._conn.execute(
                f"UPDATE records SET {col}=? WHERE id=?",
                (json.dumps(result, ensure_ascii=False), jd_id))
        self._conn.execute(
            "UPDATE records SET updated_at=? WHERE id=?",
            (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
             jd_id))
        self._commit()

    def _commit(self) -> None:
        self._conn.commit()

    # ── 模型统计 ──
    def record_stat(self, model: str, stage: str, ok: bool, error_type: str,
                    latency_ms: int, prompt_tokens: int,
                    completion_tokens: int,
                    hallucinations_removed: int = 0) -> None:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._conn.execute(
            """INSERT INTO stats (model, stage, day, calls, ok, err_429,
                                  err_5xx, err_timeout, total_latency_ms,
                                  prompt_tokens, completion_tokens,
                                  hallucination_removed)
               VALUES (?,?,?,1,?,?,?,?,?,?,?,?)
               ON CONFLICT(model, stage, day) DO UPDATE SET
                 calls=calls+1, ok=ok+excluded.ok,
                 err_429=err_429+excluded.err_429,
                 err_5xx=err_5xx+excluded.err_5xx,
                 err_timeout=err_timeout+excluded.err_timeout,
                 total_latency_ms=total_latency_ms+excluded.total_latency_ms,
                 prompt_tokens=prompt_tokens+excluded.prompt_tokens,
                 completion_tokens=completion_tokens+excluded.completion_tokens,
                 hallucination_removed=hallucination_removed
                        +excluded.hallucination_removed""",
            (model, stage, day, 1 if ok else 0,
             1 if error_type == "err_429" else 0,
             1 if error_type == "err_5xx" else 0,
             1 if error_type == "err_timeout" else 0,
             latency_ms, prompt_tokens, completion_tokens,
             hallucinations_removed))
        self._commit()

    def stats_row(self, model: str, stage: str) -> dict:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._conn.execute(
            "SELECT *, total_latency_ms*1.0/"
            "CASE calls WHEN 0 THEN 1 ELSE calls END AS avg_latency_ms "
            "FROM stats WHERE model=? AND stage=? AND day=?",
            (model, stage, day)).fetchone()
        return dict(row) if row else {}
