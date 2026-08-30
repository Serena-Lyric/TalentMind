"""Shared visible-DOM adapters for authorized Chinese job-site sessions.

The adapter only reads the currently rendered page through CDP. It does not
intercept requests, read cookies, solve challenges, or call private APIs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin, urlsplit, urlunsplit

from app.collect.schema import RawJD


@dataclass(frozen=True)
class SiteSpec:
    source: str
    origin: str
    host_hint: str
    search_template: str
    link_selector: str
    card_selectors: tuple[str, ...]
    title_selectors: tuple[str, ...]
    company_selectors: tuple[str, ...]
    salary_selectors: tuple[str, ...]
    location_selectors: tuple[str, ...]
    experience_selectors: tuple[str, ...]
    degree_selectors: tuple[str, ...]
    description_selectors: tuple[str, ...]
    company_info_selectors: tuple[str, ...]
    detail_path_patterns: tuple[str, ...]

    def search_url(self, keyword: str, city: str, page: int) -> str:
        return self.search_template.format(
            keyword=quote_plus(keyword), city=quote_plus(city), page=page
        )


SITES: dict[str, SiteSpec] = {
    "zhaopin": SiteSpec(
        source="zhaopin",
        origin="https://www.zhaopin.com",
        host_hint="zhaopin.com",
        search_template="https://www.zhaopin.com/jobs?jl={city}&kw={keyword}&page={page}",
        link_selector='a[href*="/job/"], a[href*="/job_detail/"]',
        card_selectors=(
            ".job-card",
            ".joblist-box__item",
            ".job-card-box",
            ".job-card-container",
        ),
        title_selectors=(
            ".job-detail-summary__title-text",
            ".job-card__title-clamp",
            ".jobinfo__name",
            ".job-name",
            ".job-title",
            "[class*='jobName']",
            "[class*='title-clamp']",
        ),
        company_selectors=(
            ".job-detail-summary__company-name",
            ".job-card__company-name",
            ".companyinfo__name",
            ".company-name",
            "[class*='companyName']",
        ),
        salary_selectors=(
            ".job-detail-summary__salary",
            ".job-card__salary",
            ".jobinfo__salary",
            ".salary",
            ".job-salary",
            "[class*='salary']",
        ),
        location_selectors=(
            ".jobinfo__other-info",
            ".job-area",
            ".job-location",
            "[class*='location']",
        ),
        experience_selectors=(
            ".jobinfo__other-info",
            ".experience",
            "[class*='experience']",
        ),
        degree_selectors=(
            ".jobinfo__other-info",
            ".education",
            "[class*='education']",
        ),
        description_selectors=(
            ".job-description__content",
            ".describtion__detail",
            ".job-detail",
            ".job-description",
        ),
        company_info_selectors=(
            ".company__detail",
            ".company-info",
            "[class*='companyDetail']",
        ),
        detail_path_patterns=(r"/job/", r"/job_detail/"),
    ),
    "liepin": SiteSpec(
        source="liepin",
        origin="https://www.liepin.com",
        host_hint="liepin.com",
        search_template="https://www.liepin.com/zhaopin/?key={keyword}&dqs={city}&currentPage={page}",
        link_selector='a[href*="/job/"], a[href*="/a/"]',
        card_selectors=(
            ".job-list-item",
            ".job-card-pc-container",
            ".job-card-box",
            ".job-card",
            "[class*='job-card']",
        ),
        title_selectors=(
            ".job-title",
            ".job-name",
            "[class*='job-title']",
            "[class*='jobName']",
        ),
        company_selectors=(
            ".company-name",
            ".company__name",
            "[class*='company-name']",
            "[class*='companyName']",
        ),
        salary_selectors=(".job-salary", ".salary", "[class*='salary']"),
        location_selectors=(
            ".job-area",
            ".job-location",
            "[class*='job-dq']",
            "[class*='location']",
        ),
        experience_selectors=(
            ".job-labels",
            ".experience",
            "[class*='experience']",
        ),
        degree_selectors=(".job-labels", ".education", "[class*='education']"),
        description_selectors=(
            ".job-intro-container",
            ".job-detail",
            ".job-description",
            "article",
            "main",
        ),
        company_info_selectors=(
            ".company-intro-container",
            ".company-info",
            "[class*='companyDetail']",
        ),
        detail_path_patterns=(r"/job/", r"/a/"),
    ),
}


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def normalize_url(spec: SiteSpec, value: str) -> str:
    value = value.strip()
    dom_prefix = f"dom://{spec.source}/"
    if value.startswith(dom_prefix) and value[len(dom_prefix) :].strip("/"):
        return value[:256]

    url = urljoin(spec.origin, value or "")
    parts = urlsplit(url)
    if parts.netloc != urlsplit(spec.origin).netloc:
        return ""
    path = parts.path.rstrip("/")
    if not path or not any(re.search(pattern, path, re.IGNORECASE) for pattern in spec.detail_path_patterns):
        return ""
    if any(token in path.lower() for token in ("/zhaopin", "/sou/", "/search")):
        return ""
    return urlunsplit((parts.scheme or "https", parts.netloc, path, "", ""))


def _metadata(raw: dict, detail: dict) -> str:
    fields = [
        ("公司", detail.get("company") or raw.get("company")),
        ("薪资", detail.get("salary") or raw.get("salary")),
        ("地点", detail.get("location") or raw.get("location")),
        ("经验", detail.get("experience") or raw.get("experience")),
        ("学历", detail.get("degree") or raw.get("degree")),
        ("行业", raw.get("industry")),
        ("技能标签", "、".join(clean(x) for x in raw.get("tags", []) if clean(x))),
    ]
    return "\n".join(f"{key}: {clean(value)}" for key, value in fields if clean(value))


def merge_job(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    for key, value in incoming.items():
        if value and not merged.get(key):
            merged[key] = value
    if incoming.get("tags"):
        merged["tags"] = list(dict.fromkeys(existing.get("tags", []) + incoming["tags"]))
    return merged


def deduplicate_jobs(spec: SiteSpec, jobs: list[dict]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for job in jobs:
        url = normalize_url(spec, str(job.get("url") or ""))
        if not url:
            continue
        normalized = {**job, "url": url}
        by_url[url] = merge_job(by_url[url], normalized) if url in by_url else normalized
    return list(by_url.values())


def normalize_job(spec: SiteSpec, raw: dict, detail: dict | None = None) -> RawJD | None:
    detail = detail or {}
    url = normalize_url(spec, str(raw.get("url") or detail.get("url") or ""))
    title = clean(raw.get("title") or detail.get("title"))
    if not url or not title:
        return None

    experience = clean(detail.get("experience") or raw.get("experience"))
    description = clean(detail.get("description") or raw.get("description"))
    company_info = clean(detail.get("company_info") or raw.get("company_info"))
    raw_text = "\n\n".join(
        chunk
        for chunk in (
            _metadata({**raw, "experience": experience}, detail),
            f"职位描述:\n{description}" if description else "",
            f"公司简介: {company_info}" if company_info else "",
        )
        if chunk
    )
    job_id = url.rsplit("/", 1)[-1]
    return RawJD(
        source=spec.source,
        job_title=title[:128],
        raw_html=raw_text,
        experience=experience[:255],
        job_id=job_id[:128],
        raw_skills=[clean(x) for x in raw.get("tags", []) if clean(x)],
        source_detail=url[:128],
    )


def _js_array(values: tuple[str, ...]) -> str:
    import json

    return json.dumps(list(values), ensure_ascii=False)


def build_search_extract_js(spec: SiteSpec) -> str:
    import json

    return f"""
(() => {{
  const text = (node) => (node?.innerText || node?.textContent || '').replace(/\\s+/g, ' ').trim();
  const visible = (node) => {{
    if (!node) return false;
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  }};
  const first = (root, selectors) => {{
    for (const selector of selectors) {{
      const node = root?.querySelector(selector);
      if (node && text(node)) return text(node);
    }}
    return '';
  }};
  const hash = (value) => {{
    let result = 2166136261;
    for (let i = 0; i < value.length; i++) {{
      result ^= value.charCodeAt(i);
      result = Math.imul(result, 16777619);
    }}
    return (result >>> 0).toString(16);
  }};
  const cards = {json.dumps(', '.join(spec.card_selectors), ensure_ascii=False)};
  const linkSelector = {json.dumps(spec.link_selector, ensure_ascii=False)};
  const titleSelectors = {_js_array(spec.title_selectors)};
  const companySelectors = {_js_array(spec.company_selectors)};
  const salarySelectors = {_js_array(spec.salary_selectors)};
  const locationSelectors = {_js_array(spec.location_selectors)};
  const cardNodes = [...document.querySelectorAll(cards)];
  const titleRequired = {str(spec.source != "zhaopin").lower()};
  const seen = new Set();
  return cardNodes.map((card, cardIndex) => {{
    if (!visible(card)) return null;
    const tags = [...(card.querySelectorAll('[class*="tag"], [class*="label"], [class*="skill"]') || [])]
      .map(text).filter(Boolean).slice(0, 30);
    const title = first(card, titleSelectors);
    const company = first(card, companySelectors);
    const salary = first(card, salarySelectors);
    const location = first(card, locationSelectors);
    const anchor = [...card.querySelectorAll(linkSelector)]
      .find((node) => node.href && /\\/(job|a|job_detail)\\//i.test(node.href));
    const key = [title, company, salary, location, tags.join('|')].join('|');
    const url = anchor?.href || 'dom://{spec.source}/' + hash(key);
    return {{
      url,
      title: title || text(anchor),
      company,
      salary,
      location,
      tags,
      _card_index: cardIndex,
      _dom: !anchor,
    }};
  }}).filter((job) => {{
    if (!job || !job.url || (titleRequired && !job.title) || seen.has(job.url)) return false;
    seen.add(job.url);
    return true;
  }});
}})()
"""


def build_activate_card_js(spec: SiteSpec, card_index: int) -> str:
    import json

    return f"""
(() => {{
  const cards = [...document.querySelectorAll({json.dumps(', '.join(spec.card_selectors), ensure_ascii=False)})];
  const card = cards[{int(card_index)}];
  if (!card) return {{clicked: false, reason: 'card-not-found'}};
  card.scrollIntoView({{block: 'center', inline: 'nearest'}});
  card.click();
  return {{clicked: true, title: (card.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 200)}};
}})()
"""


def build_detail_extract_js(spec: SiteSpec) -> str:
    return f"""
(() => {{
  const text = (node) => (node?.innerText || node?.textContent || '').replace(/\\s+/g, ' ').trim();
  const visible = (node) => {{
    if (!node) return false;
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  }};
  const root = {"document.querySelector('.job-detail-panel') || document" if spec.source == "zhaopin" else "document"};
  const first = (selectors) => {{
    for (const selector of selectors) {{
      const nodes = root.querySelectorAll(selector);
      for (const node of nodes) if (visible(node) && text(node)) return text(node);
    }}
    return '';
  }};
  return {{
    url: location.href,
    title: first({_js_array(spec.title_selectors)}),
    company: first({_js_array(spec.company_selectors)}),
    salary: first({_js_array(spec.salary_selectors)}),
    location: first({_js_array(spec.location_selectors)}),
    experience: first({_js_array(spec.experience_selectors)}),
    degree: first({_js_array(spec.degree_selectors)}),
    description: first({_js_array(spec.description_selectors)}),
    company_info: first({_js_array(spec.company_info_selectors)}),
  }};
}})()
"""
