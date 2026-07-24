import csv
from app.collect.schema import RawJD


def load_csv_posting(path: str, limit: int = 100000) -> list[RawJD]:
    """Read postings.csv, yield RawJD per row. limit=0 means full."""
    rows: list[RawJD] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("title") or "").strip()
            if not title:
                continue
            rows.append(RawJD(
                source="dataset",
                job_title=title,
                raw_html=row.get("description") or "",
                experience=(row.get("formatted_experience_level") or "").strip(),
                job_id=(row.get("job_id") or "").strip(),
            ))
            if limit > 0 and len(rows) >= limit:
                break
    return rows


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
