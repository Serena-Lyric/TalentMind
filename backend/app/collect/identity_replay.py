"""Offline replay of Zhaopin DOM identity decisions from private event logs."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

from app.collect.fetchers.job_sites import SITES
from app.collect.identity import content_rejection, dom_fingerprint, identity_decision

ROOT = Path(__file__).resolve().parents[3]


def _base_job(event: dict) -> dict:
    job = dict(event.get('job') or {})
    detail = event.get('detail') or {}
    job['_dom'] = True
    job['_card_index'] = int(job.get('_card_index', 0))
    job['_list_url'] = job.get('_list_url') or detail.get('url') or ''
    job['_observation_key'] = job.get('_observation_key') or (
        'zhaopin:replay-' + hashlib.sha256(
            f"{job.get('_card_index')}|{job.get('title')}".encode('utf-8')
        ).hexdigest()[:16]
    )
    return job


def _binding(job: dict, detail: dict, observed_at: str, **overrides) -> dict:
    value = {
        'target_card_found': True,
        'target_active_before': False,
        'target_active_after': True,
        'panel_visible': True,
        'panel_changed': True,
        'stable_samples': 2,
        'panel_title': detail.get('title') or '',
        'before_panel_title': 'replay-before-panel',
        'list_url': detail.get('url') or job.get('_list_url') or '',
        'list_title': job.get('title') or '',
        'list_company': job.get('company') or '',
        'binding_policy': 'zhaopin-dom-panel-v1',
        'observed_at': observed_at,
    }
    value.update(overrides)
    return value


def _content_decision(spec, job: dict, detail: dict) -> dict:
    reason = content_rejection(spec, job, detail)
    return {'content_rejection': reason, 'content_eligible': reason is None}


def _identity_decision(spec, job: dict, detail: dict, observed_at: str, **binding) -> dict:
    status, evidence, rejection = identity_decision(
        spec, job, detail, _binding(job, detail, observed_at, **binding), observed_at
    )
    return {
        'identity_status': status,
        'identity_rejection': rejection,
        'identity_evidence': evidence,
    }


def replay_events(events: list[dict]) -> dict:
    cases = []
    rejects = Counter()
    valid_pending = 0
    for event in events:
        if event.get('event') != 'detail' or not event.get('job') or not event.get('detail'):
            continue
        job = _base_job(event)
        detail = dict(event.get('detail') or {})
        spec = SITES.get(event.get('platform') or job.get('platform') or '')
        if spec is None:
            continue
        observed_at = str(event.get('observed_at') or '')

        content = _content_decision(spec, job, detail)
        valid = _identity_decision(spec, job, detail, observed_at)
        valid.update(content)
        if valid['identity_status'] == 'pending' and content['content_eligible']:
            valid_pending += 1

        wrong = _identity_decision(
            spec, job, detail, observed_at, panel_title='上一个岗位'
        )
        stale = _identity_decision(
            spec, job, detail, observed_at,
            target_active_before=False, panel_changed=False,
            before_panel_title=job.get('title') or '',
        )
        empty = _content_decision(spec, job, {**detail, 'description': ''})
        truncated = _content_decision(
            spec, job, {**detail, 'description_truncated': True}
        )

        fingerprint = ''
        if valid['identity_evidence']:
            evidence = valid['identity_evidence']
            fingerprint = dom_fingerprint(evidence)
            try:
                later = datetime.fromisoformat(observed_at) + timedelta(minutes=5)
                later_at = later.isoformat()
            except ValueError:
                later_at = observed_at + '#later'
            later_evidence = {**evidence, 'observed_at': later_at}
            same_fingerprint = fingerprint == dom_fingerprint(evidence)
            later_fingerprint_same = fingerprint == dom_fingerprint(later_evidence)
        else:
            same_fingerprint = True
            later_fingerprint_same = True

        for decision in (valid, wrong, stale, empty, truncated):
            reason = decision.get('identity_rejection') or decision.get('content_rejection')
            if reason:
                rejects[reason] += 1
        checks = {
            'valid_pending': {**valid, 'fingerprint': fingerprint},
            'async_wrong_job': wrong,
            'same_title_panel_not_updated': stale,
            'empty_body': empty,
            'truncated_body': truncated,
            'same_observation_duplicate': {'fingerprint_same': same_fingerprint},
            'different_observation_time': {'fingerprint_same': later_fingerprint_same},
        }
        cases.append({
            'observation_key': job.get('_observation_key'),
            'jd_title': job.get('title'),
            'observed_at': observed_at,
            'checks': checks,
        })
    return {
        'binding_note': 'old_events_lack_panel_transition; binding cases are synthetic validation',
        'summary': {
            'cases': len(cases),
            'valid_pending': valid_pending,
            'rejections': dict(sorted(rejects.items())),
            'does_not_certify_historical_binding': True,
        },
        'cases': cases,
    }


def validate_output(path: Path) -> Path:
    path = path.resolve()
    if path.exists():
        raise ValueError('replay output must not exist')
    if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / 'data/local'):
        raise ValueError('private replay output must be under data/local')
    return path


def replay_file(events_path: Path, output_dir: Path) -> dict:
    events_path = Path(events_path).resolve()
    output_dir = validate_output(Path(output_dir))
    raw = events_path.read_bytes()
    events = [
        json.loads(line)
        for line in raw.decode('utf-8-sig').splitlines()
        if line.strip()
    ]
    result = replay_events(events)
    result['input_sha256'] = hashlib.sha256(raw).hexdigest()
    output_dir.mkdir(parents=True)
    (output_dir / 'replay.json').write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
        encoding='utf-8',
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = replay_file(args.events, args.output)
    print(json.dumps(result['summary'], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
