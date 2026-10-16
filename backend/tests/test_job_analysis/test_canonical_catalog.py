"""B3-5 draft definitions are proposals, never JD classification or user approval."""
from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from test_foundation_inputs import area

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'backend/app/job_analysis/canonical_catalog'


def source(root, path='basis.md', text='Synthetic definition basis'):
    file = root / path
    file.write_text(text, encoding='utf-8')
    return dict(path=path, sha256=hashlib.sha256(file.read_bytes()).hexdigest(), quote=text)


def draft(root):
    ref = source(root)
    def item(identity, family, name, other):
        return dict(id=identity, proposed_name=name, family_id=family, core_responsibilities=['交付独立技术成果'],
            deliverables=['工程系统'], definition_basis=[ref], exclusions=['只有工具使用不能确定职业'],
            neighbors=[dict(candidate_id=other, distinction='按主要成果责任区分，主次不清未决')],
            proposed_aliases=[], status='candidate', confirmation_status='unconfirmed', origin='ai_draft')
    return dict(schema_version='c35-candidates-1', revision='draft-v1', family_revision='families-v3',
        candidates=[item('role-a', 'software_engineering', '工程师', 'role-b'),
                    item('role-b', 'data_ai', '工程师', 'role-a')])


def test_repository_draft_covers_eight_families_and_empty_release():
    from app.job_analysis.canonical_catalog.models import validate_catalog, load_json
    from app.job_analysis.role_classification.proposals.models import FAMILY_VERSIONS
    value, refs = validate_catalog(load_json(ASSETS / 'candidates.v1.json'), ROOT)
    families = [c['family_id'] for c in value['candidates']]
    assert set(families) == set(FAMILY_VERSIONS['families-v3'])
    assert len({families.count(f) for f in families}) > 1
    assert all(c['status'] == 'candidate' and c['confirmation_status'] == 'unconfirmed' for c in value['candidates'])
    assert refs and load_json(ASSETS / 'release.empty.v1.json')['formal_jobs'] == []
    by_id = {c['id']: c for c in value['candidates']}
    for left, right in [('automation-test', 'sdet'), ('devops', 'sre'), ('data-analyst', 'bi-engineer'),
                        ('bi-engineer', 'data-engineer'), ('ml-engineer', 'algorithm-research'),
                        ('security-development', 'secops'), ('backend-development', 'frontend-development')]:
        assert by_id[left]['core_responsibilities'] != by_id[right]['core_responsibilities']
        assert right in [n['candidate_id'] for n in by_id[left]['neighbors']]


def test_cross_family_same_name_has_independent_ids(area):
    from app.job_analysis.canonical_catalog.models import validate_catalog
    value, _ = validate_catalog(draft(area), area)
    assert len(value['candidates']) == 2


@pytest.mark.parametrize('field', ['id', 'family_id', 'core_responsibilities', 'deliverables',
                                   'definition_basis', 'exclusions', 'neighbors'])
def test_required_definition_parts_cannot_be_omitted(area, field):
    from app.job_analysis.canonical_catalog.models import validate_catalog
    value = draft(area)
    del value['candidates'][0][field]
    with pytest.raises(ValueError):
        validate_catalog(value, area)


@pytest.mark.parametrize('change', ['duplicate_id', 'same_family_name', 'alias_collision', 'unknown_family',
    'unknown_neighbor', 'self_neighbor', 'empty_boundary', 'admitted', 'confirmed', 'technology_tracks',
    'vacancy_count', 'wrong_hash', 'missing_quote', 'path_escape', 'absolute_path'])
def test_invalid_or_falsely_confirmed_definitions_rejected(area, change):
    from app.job_analysis.canonical_catalog.models import validate_catalog
    value = draft(area)
    a, b = value['candidates']
    if change == 'duplicate_id': b['id'] = a['id']
    if change == 'same_family_name': b['family_id'] = a['family_id']
    if change == 'alias_collision':
        b['family_id'] = a['family_id']; b['proposed_name'] = '其他岗位'; b['proposed_aliases'] = ['工程师']
    if change == 'unknown_family': a['family_id'] = 'unknown'
    if change == 'unknown_neighbor': a['neighbors'][0]['candidate_id'] = 'missing'
    if change == 'self_neighbor': a['neighbors'][0]['candidate_id'] = a['id']
    if change == 'empty_boundary': a['neighbors'][0]['distinction'] = ' '
    if change == 'admitted': a['status'] = 'admitted'
    if change == 'confirmed': a['confirmation_status'] = 'confirmed'
    if change in ('technology_tracks', 'vacancy_count'): a[change] = []
    if change == 'wrong_hash': a['definition_basis'][0]['sha256'] = '0' * 64
    if change == 'missing_quote': a['definition_basis'][0]['quote'] = 'not present'
    if change == 'path_escape': a['definition_basis'][0]['path'] = '../basis.md'
    if change == 'absolute_path': a['definition_basis'][0]['path'] = str(area / 'basis.md')
    with pytest.raises((ValueError, OSError)):
        validate_catalog(value, area)


def test_basis_bytes_are_frozen_and_definition_changes_do_not_alias(area):
    from app.job_analysis.canonical_catalog.models import validate_catalog
    from app.job_analysis.foundation.inputs import digest
    value = draft(area)
    valid, refs = validate_catalog(value, area)
    before = digest(valid['candidates'][0])
    changed = deepcopy(value)
    changed['candidates'][0]['deliverables'] = ['新的工程成果']
    after, _ = validate_catalog(changed, area)
    assert before != digest(after['candidates'][0])
    assert bytes.fromhex(refs[0]['raw_hex']) == (area / 'basis.md').read_bytes()


def test_nine_product_rules_documented():
    text = (ROOT / 'docs/PRODUCT_DECISIONS.md').read_text(encoding='utf-8')
    assert all(f'M2-{n}' in text for n in range(52, 61))
    assert '一般原则确认' in text and '逐项' in text


def test_shipped_source_hash_matches_a_fresh_LF_checkout(area):
    from app.job_analysis.canonical_catalog.models import validate_catalog, load_json
    (area / 'docs').mkdir()
    raw = (ROOT / 'docs/PRODUCT_DECISIONS.md').read_bytes().replace(b'\r\n', b'\n')
    (area / 'docs/PRODUCT_DECISIONS.md').write_bytes(raw)
    assert validate_catalog(load_json(ASSETS / 'candidates.v1.json'), area)[0]['revision'] == 'draft-v1'
