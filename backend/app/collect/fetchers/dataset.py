import csv
from collections.abc import Iterator

from app.collect.schema import RawJD


def iter_csv_postings(path: str, *, offset: int = 0, limit: int = 0) -> Iterator[RawJD]:
    """Stream postings.csv; offset/limit count only rows with a non-empty title."""
    if offset < 0 or limit < 0:
        raise ValueError("offset 和 limit 不能为负数")

    valid_count = 0
    yielded = 0
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("title") or "").strip()
            if not title:
                continue
            if valid_count < offset:
                valid_count += 1
                continue

            yield RawJD(
                source="linkedin",   # D39：来源平台（LinkedIn 数据集，D17 仅记录平台）
                job_title=title,
                raw_html=row.get("description") or "",
                experience=(row.get("formatted_experience_level") or "").strip(),
                job_id=(row.get("job_id") or "").strip(),
                source_detail=((row.get("posting_domain") or "").strip()
                               or "linkedin_job_postings"),
            )
            valid_count += 1
            yielded += 1
            if limit > 0 and yielded >= limit:
                return


def load_csv_posting(path: str, limit: int = 100000, offset: int = 0) -> list[RawJD]:
    """Read postings.csv into memory; use iter_csv_postings for large imports."""
    return list(iter_csv_postings(path, offset=offset, limit=limit))


def load_skill_map(skills_csv: str) -> dict[str, str]:
    """Load skill_abr -> skill_name mapping."""
    mapping: dict[str, str] = {}
    with open(skills_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            abr = (row.get("skill_abr") or "").strip()
            name = (row.get("skill_name") or "").strip()
            if abr and name:
                mapping[abr] = name
    return mapping


def load_job_skills(job_skills_csv: str) -> dict[str, list[str]]:
    """Load job_id -> [skill_abr, ...] mapping."""
    mapping: dict[str, list[str]] = {}
    with open(job_skills_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            job_id = (row.get("job_id") or "").strip()
            abr = (row.get("skill_abr") or "").strip()
            if job_id and abr:
                mapping.setdefault(job_id, []).append(abr)
    return mapping
