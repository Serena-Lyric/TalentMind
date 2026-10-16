"""Offline review and release proposals. Human identity is never authenticated here."""
import hashlib
from pathlib import Path

from pydantic import TypeAdapter

from ..foundation.inputs import canonical, check_public, digest, parse_json
from ..foundation.models import VersionName
from ..foundation.runner import publish, _output_path as output_path
from ..foundation.store import now
from ..role_classification.proposals.models import load_taxonomy
from .models import validate_catalog, freeze_sources, Review, ReleaseManifest


def checkpoint(stage):
    """Transaction/publication instrumentation for real process recovery tests."""


def raw_source(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), raw_hex=raw.hex())


def parsed_input(raw):
    value = parse_json(bytes.fromhex(raw['raw_hex']).decode('utf-8-sig'))
    check_public(value)
    return value


def version_manifest(revision, family_revision):
    TypeAdapter(VersionName).validate_python(revision)
    root = Path(__file__).resolve().parents[1]
    paths = sorted(Path(__file__).parent.glob('*.py')) + [root / name for name in (
        'foundation/inputs.py', 'foundation/models.py', 'foundation/store.py', 'foundation/runner.py',
        'role_classification/models.py', 'role_classification/proposals/models.py',
        'role_classification/governance/models.py')]
    taxonomy_path = root / 'role_classification/proposals' / (family_revision.replace('families-', 'families.') + '.json')
    paths.append(taxonomy_path)
    return dict(schema_version='c35-dependencies-1', revision=revision,
        family_taxonomy=load_taxonomy(taxonomy_path),
        source_sha256={p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        interpretation='structural_contract_only', real_release_gate='individual_user_confirmation_and_controlled_PR',
        identity_verified=False, jd_classification='not_performed')


def checked_destination(store, output, paths):
    if output is None:
        return None
    destination = output_path(store, output)
    for path in paths:
        output_path(store, destination, Path(path))
    return destination


def execute(store, catalog_path, source_root, *, revision='v1', output=None):
    raw = raw_source(catalog_path)
    catalog, sources = validate_catalog(parsed_input(raw), source_root)
    paths = [raw['path'], *[str((Path(source_root) / s['path']).resolve()) for s in sources]]
    destination = checked_destination(store, output, paths)
    manifest = version_manifest(revision, catalog['family_revision'])
    body = dict(schema_version='c35-snapshot-1', catalog=catalog,
        candidate_versions={c['id']: digest(c) for c in catalog['candidates']}, manifest=manifest, version_id=digest(manifest),
        input=raw, sources=sources, input_paths=paths, dependencies=[],
        formal_jobs=[], formal_admitted=False, classification_complete=False, formal_statistics_eligible=False)
    with store.conn:
        revision_key = 'candidate:' + catalog['revision']
        existing = store.conn.execute('SELECT catalog_sha256 FROM c35_revisions WHERE revision=?', (revision_key,)).fetchone()
        if existing and existing[0] != digest(catalog):
            raise ValueError('named candidate revision is immutable; supply a new revision')
        store.conn.execute('INSERT OR IGNORE INTO c35_revisions VALUES (?,?)', (revision_key, digest(catalog)))
        report = store.save('snapshot', body)
        checkpoint('before_commit')
    checkpoint('after_commit')
    if destination is not None:
        publish(report, destination, report['run_id'])
        checkpoint('after_output')
    return report


def replay(store, artifact_id, _seen=None):
    seen = set() if _seen is None else _seen
    if artifact_id in seen:
        raise ValueError('cyclic catalogue history')
    seen.add(artifact_id)
    row = store.conn.execute('SELECT * FROM c35_artifacts WHERE id=?', (artifact_id,)).fetchone()
    if row is None:
        raise ValueError('catalogue artifact not found')
    result = parse_json(row['body'])
    payload = {k: v for k, v in result.items() if k != 'run_id'}
    if digest(result) != row['sha256'] or row['id'] != row['kind'] + '-' + digest(payload)[:48] or result['run_id'] != row['id']:
        raise ValueError('catalogue artifact integrity mismatch')
    for source in [*result.get('sources', []), *([result['input']] if result.get('input') else [])]:
        if hashlib.sha256(bytes.fromhex(source['raw_hex'])).hexdigest() != source['sha256']:
            raise ValueError('catalogue original source integrity mismatch')
    for dependency in result['dependencies']:
        replay(store, dependency, set(seen))
    return result


def snapshot(store, identity):
    result = replay(store, identity)
    if result['schema_version'] != 'c35-snapshot-1':
        raise ValueError('original catalogue snapshot required')
    return result


def review_events(store, identity):
    rows = store.conn.execute("SELECT id,candidate_id FROM c35_artifacts WHERE kind='review' AND snapshot_id=? ORDER BY rowid", (identity,))
    result = []
    for row in rows:
        saved = replay(store, row['id'])
        if saved['event']['candidate_id'] != row['candidate_id'] or saved['event']['snapshot_id'] != identity:
            raise ValueError('review index integrity mismatch')
        result.append(saved)
    return result


def review(store, snapshot_id, event_path, source_root):
    report = snapshot(store, snapshot_id)
    raw = raw_source(event_path)
    item = Review.model_validate(parsed_input(raw)).model_dump()
    candidates = {c['id']: c for c in report['catalog']['candidates']}
    if item['snapshot_id'] != snapshot_id or item['candidate_id'] not in candidates or item['candidate_sha256'] != digest(candidates[item['candidate_id']]):
        raise ValueError('review must bind exact candidate definition and snapshot version')
    sources = freeze_sources([item['source']], source_root)
    if not all(text in item['source']['quote'] for text in (item['candidate_id'], item['candidate_sha256'], snapshot_id)):
        raise ValueError('review source must identify exact candidate, definition and snapshot')
    if item['decision'] == 'reviewed_accepted' and not all(item[k] for k in (
            'confirmed_responsibilities', 'confirmed_boundaries', 'confirmed_family')):
        raise ValueError('individual definition, boundary and family confirmation required')
    events = [e for e in review_events(store, snapshot_id) if e['event']['candidate_id'] == item['candidate_id']]
    expected = events[-1]['run_id'] if events else None
    if item['supersedes'] != expected:
        raise ValueError('new decision must explicitly supersede current event on same target and version')
    body = dict(schema_version='c35-review-record-1', event=item, input=raw, sources=sources,
        input_paths=[*report['input_paths'], raw['path'], *[str((Path(source_root) / s['path']).resolve()) for s in sources]],
        dependencies=[snapshot_id, *([expected] if expected else [])], identity_verified=False, formal_admitted=False, created_at=now())
    with store.conn:
        saved = store.save('review', body, snapshot_id, item['candidate_id'])
        checkpoint('before_commit')
    checkpoint('after_commit')
    return saved['run_id']


def export(store, snapshot_id, manifest_path=None, source_root=None, *, output=None):
    report = snapshot(store, snapshot_id)
    events = review_events(store, snapshot_id)
    latest = {r['event']['candidate_id']: r for r in events}
    candidates = {c['id']: c for c in report['catalog']['candidates']}
    states = {key: latest[key]['event']['decision'] if key in latest else 'candidate' for key in candidates}
    paths = [*report['input_paths'], *[p for event in events for p in event['input_paths']]]
    item, raw, sources = None, None, []
    simulated, proposed = [], []
    dependencies = [snapshot_id, *[e['run_id'] for e in events]]
    if manifest_path is not None:
        raw = raw_source(manifest_path)
        item = ReleaseManifest.model_validate(parsed_input(raw)).model_dump()
        if item['snapshot_id'] != snapshot_id:
            raise ValueError('release manifest must bind exact catalogue snapshot')
        approvals = item['approvals']
        if len({a['candidate_id'] for a in approvals}) != len(approvals):
            raise ValueError('duplicate release candidate')
        sources = freeze_sources([a['confirmation_source'] for a in approvals], source_root)
        paths += [raw['path'], *[str((Path(source_root) / s['path']).resolve()) for s in sources]]
        if item['previous_release_id']:
            previous = replay(store, item['previous_release_id'])
            if previous['schema_version'] != 'c35-export-1' or previous['release_manifest'] is None or previous['release_manifest']['mode'] != item['mode']:
                raise ValueError('previous release must be an explicit same-mode release export')
            if previous['release_manifest']['revision'] == item['revision']:
                raise ValueError('release changes require a new release revision')
            previous_ids = {c['id'] for c in previous['simulated_jobs'] + previous['proposed_jobs']}
            if not previous_ids <= {a['candidate_id'] for a in approvals}:
                raise ValueError('release may not silently drop previous jobs')
            dependencies.append(item['previous_release_id'])
        for approval in approvals:
            key = approval['candidate_id']
            reviewed = latest.get(key)
            if reviewed is None or reviewed['run_id'] != approval['review_id'] or reviewed['event']['decision'] != 'reviewed_accepted':
                raise ValueError('current accepted individual review required')
            expected_mode = 'synthetic_only' if item['mode'] == 'synthetic_only' else 'manual_pending'
            if reviewed['event']['mode'] != expected_mode or approval['candidate_sha256'] != digest(candidates[key]):
                raise ValueError('approval mode or complete definition hash mismatch')
            ref = approval['confirmation_source']
            excluded = {s['path'] for c in report['catalog']['candidates'] for s in c['definition_basis']}
            excluded_hashes = {s['sha256'] for c in report['catalog']['candidates'] for s in c['definition_basis']}
            excluded_hashes.add(report['input']['sha256'])
            for event in events:
                excluded.add(event['event']['source']['path'])
                excluded.add(event['input']['path'])
                excluded_hashes.update([event['event']['source']['sha256'], event['input']['sha256'],
                    hashlib.sha256(canonical(event).encode('utf-8')).hexdigest(),
                    hashlib.sha256((canonical(event) + '\n').encode('utf-8')).hexdigest()])
            if ref['path'] in excluded or ref['sha256'] in excluded_hashes or ref['sha256'] == raw['sha256'] or Path(source_root, ref['path']).resolve() == Path(manifest_path).resolve():
                raise ValueError('release confirmation must be independent of draft, review and manifest')
            # A structural link prevents reusing an unrelated or old-version source; it does not authenticate a person.
            if not all(text in ref['quote'] for text in (key, approval['candidate_sha256'], snapshot_id)):
                raise ValueError('confirmation source must explicitly identify candidate, definition and snapshot')
            if item['mode'] == 'synthetic_only':
                simulated.append(candidates[key]); states[key] = 'admitted'
            else:
                proposed.append(candidates[key]); states[key] = 'awaiting_external_approval'
    destination = checked_destination(store, output, paths)
    body = dict(schema_version='c35-export-1', snapshot_id=snapshot_id, version_id=report['version_id'],
        states=states, reviews=events, release_manifest=item, input=raw, sources=sources, input_paths=paths,
        dependencies=dependencies, synthetic_only=item is not None and item['mode'] == 'synthetic_only',
        simulated_jobs=simulated, proposed_jobs=proposed, formal_jobs=[], formal_admitted=False,
        identity_verified=False, classification_complete=False, formal_statistics_eligible=False, created_at=now())
    with store.conn:
        if item is not None:
            key = item['mode'] + ':' + item['revision']
            existing = store.conn.execute('SELECT catalog_sha256 FROM c35_revisions WHERE revision=?', (key,)).fetchone()
            if existing and existing[0] != digest(item):
                raise ValueError('release revision is immutable; new manifest requires a new revision')
            store.conn.execute('INSERT OR IGNORE INTO c35_revisions VALUES (?,?)', (key, digest(item)))
        saved = store.save('export', body, snapshot_id)
        checkpoint('before_commit')
    checkpoint('after_commit')
    if destination is not None:
        publish(saved, destination, saved['run_id'])
        checkpoint('after_output')
    return saved
