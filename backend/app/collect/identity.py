"""Independent JD content eligibility and source-identity decisions."""
from __future__ import annotations

import hashlib
import json

from app.collect.cleaner import clean, is_valid_jd
from app.collect.fetchers.job_sites import SiteSpec, normalize_job, normalize_url

IDENTITY_STATUSES = ('verified', 'pending', 'unknown')

_FINGERPRINT_FIELDS = (
    'platform',
    'list_url',
    'card_index',
    'title',
    'company',
    'salary',
    'location',
    'description_sha256',
    'observed_at',
    'binding_policy',
)


def _text(value) -> str:
    return ' '.join(str(value or '').split())


def content_rejection(spec: SiteSpec, job: dict, detail: dict | None) -> str | None:
    """Return why extracted detail content is ineligible for analysis."""
    if not isinstance(detail, dict) or not _text(detail.get('description')):
        return 'empty_detail'
    if detail.get('description_truncated'):
        return 'truncated_description'
    raw = normalize_job(
        spec,
        {'url': job.get('url'), 'title': job.get('title')},
        {'description': detail.get('description')},
    )
    if not raw or not is_valid_jd(clean(raw)):
        return 'invalid_detail_body'
    return None


def identity_decision(
    spec: SiteSpec,
    job: dict,
    detail: dict,
    binding: dict | None,
    observed_at: str,
) -> tuple[str, dict, str | None]:
    """Return identity status, traceable evidence, and rejection reason."""
    if job.get('_dom'):
        if not isinstance(binding, dict):
            return 'unknown', {}, 'binding_evidence_missing'
        if not binding.get('target_card_found'):
            return 'unknown', {}, 'target_card_not_found'
        if not binding.get('target_active_after'):
            return 'unknown', {}, 'target_card_not_active'
        if not binding.get('panel_visible'):
            return 'unknown', {}, 'panel_not_visible'
        if int(binding.get('stable_samples') or 0) < 2:
            return 'unknown', {}, 'panel_unstable'
        if not binding.get('target_active_before') and not binding.get('panel_changed'):
            return 'unknown', {}, 'panel_not_updated'
        expected_title = _text(job.get('title')).casefold()
        if (_text(binding.get('panel_title')).casefold() != expected_title
                or _text(detail.get('title')).casefold() != expected_title):
            return 'unknown', {}, 'title_mismatch'
        if _text(binding.get('description')) != _text(detail.get('description')):
            return 'unknown', {}, 'panel_changed_during_capture'

        description = str(detail.get('description') or '')
        evidence = {
            'strategy': 'dom_panel_binding',
            'binding_policy': binding.get('binding_policy') or 'zhaopin-dom-panel-v1',
            'platform': spec.source,
            'list_url': str(binding.get('list_url') or job.get('_list_url') or ''),
            'card_index': int(job.get('_card_index', -1)),
            'title': _text(job.get('title')),
            'company': _text(binding.get('list_company') or job.get('company')),
            'salary': _text(job.get('salary')),
            'location': _text(job.get('location')),
            'description_sha256': hashlib.sha256(description.encode('utf-8')).hexdigest(),
            'observed_at': observed_at,
            'target_active_before': bool(binding.get('target_active_before')),
            'target_active_after': True,
            'panel_visible': True,
            'panel_changed': bool(binding.get('panel_changed')),
            'stable_samples': int(binding.get('stable_samples') or 0),
            'panel_title': _text(binding.get('panel_title')),
            'before_panel_title': _text(binding.get('before_panel_title')),
        }
        return 'pending', evidence, None

    detail_title = _text(detail.get('title'))
    if not detail_title:
        return 'unknown', {}, 'missing_detail_title'
    if detail_title.casefold() != _text(job.get('title')).casefold():
        return 'unknown', {}, 'title_mismatch'
    job_url = normalize_url(spec, str(job.get('url') or ''))
    detail_url = normalize_url(spec, str(detail.get('url') or ''))
    if not job_url or not detail_url or job_url != detail_url:
        return 'unknown', {}, 'identity_mismatch'
    evidence = {
        'strategy': 'source_url',
        'platform': spec.source,
        'job_url': job_url,
        'detail_url': detail_url,
        'observed_at': observed_at,
    }
    return 'verified', evidence, None


def dom_fingerprint(evidence: dict) -> str:
    """Hash a complete DOM observation; the hash is not a unique job ID."""
    if not isinstance(evidence, dict):
        raise ValueError('identity evidence must be an object')
    missing = [key for key in _FINGERPRINT_FIELDS if key not in evidence]
    if missing:
        raise ValueError('identity evidence missing: ' + ', '.join(missing))
    encoded = json.dumps(
        {key: evidence[key] for key in _FINGERPRINT_FIELDS},
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()
