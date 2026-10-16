"""Explicit pending assertions with source evidence; no automatic semantic verdicts."""
import pytest

from test_foundation_inputs import area, load
from test_role_governance import evidence, no_network
from test_role_boundaries import taxonomy


def source(area, **changes):
    return load(area, [dict(id=1, source='synthetic', job_title='软件开发工程师 / 全栈',
        raw_text='负责前端页面与后端服务的共同设计、实现、联调和上线交付。',
        duties='开发前端页面；开发后端服务；统一负责完整应用上线。', requirements='熟悉 Java 和 Python。') | changes])


def assessment(record, kind='family_identifiable_job_unknown', **changes):
    return dict(id='assessment-a', kind=kind, origin='synthetic_assertion', proposer='fixture-author',
        basis='显式合成待审主张', evidence=[evidence(record, 'duties', record.payload['duties'])],
        components=[], shared_delivery=None, position_targets=[]) | changes


def submission(record, **changes):
    return dict(schema_version='b34-submission-1', revision='claims-v1', mode='synthetic_only',
        annotations=[dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
            origin='synthetic_assertion', proposer='fixture-author',
            family_assertions=[dict(id='family-a', family_id='software_engineering', responsibility='core',
                evidence=[evidence(record, 'duties', record.payload['duties'])])],
            candidates=[], technology_tracks=[dict(id='track-a', value='Java', evidence=[evidence(record, 'requirements', 'Java')])],
            seniority=[], assessments=[assessment(record)], conflicts=[], notes='synthetic only') | changes])


def validate(batch, marks=None):
    from app.job_analysis.role_classification.boundaries.validation import validate_submission
    return validate_submission(batch, marks or submission(batch.records[0]), taxonomy())[0]


def test_broad_title_only_supports_family_claim_and_keeps_other_dimensions(area):
    batch = source(area)
    body = validate(batch)
    assert body['canonical_job'] == dict(state='unknown', value=None, candidates=[])
    assert body['job_family']['state'] == 'pending_claim'
    assert body['technology_tracks'][0]['value'] == 'Java'
    assert body['source_payload']['job_title'] == '软件开发工程师 / 全栈'
    assert body['assessments'][0]['kind'] == 'family_identifiable_job_unknown'
    assert body['formal_admitted'] is body['formal_statistics_eligible'] is body['classification_complete'] is False


def test_competing_candidates_unresolved_and_stack_never_becomes_job(area):
    batch = source(area)
    r = batch.records[0]
    def c(identity, kind='job'):
        return dict(id=identity, raw_name='软件开发工程师', proposed_name=None, kind=kind,
            origin='synthetic_assertion', proposer='fixture-author', synthetic_only=True,
            responsibility='core', family_candidates=['software_engineering'], review_status='pending_review',
            unresolved_reason='合成候选待审核', name_evidence=[evidence(r, 'job_title', '软件开发工程师')],
            evidence=[evidence(r, 'duties', '开发后端服务')])
    body = validate(batch, submission(r, candidates=[c('job-a'), c('job-b'), c('stack-a', 'technology_stack')],
        assessments=[assessment(r, 'competing_canonical_candidates')]))
    assert body['canonical_job'] == dict(state='unresolved', value=None, candidates=['job-a', 'job-b'])
    stack = validate(batch, submission(r, candidates=[c('stack-a', 'technology_stack')]))
    assert stack['canonical_job']['state'] == 'unknown'


@pytest.mark.parametrize('weak', ['title', 'stacks', 'assist', 'missing_delivery'])
def test_composite_without_complete_cross_domain_responsibility_is_unproven(area, weak):
    batch = source(area)
    r = batch.records[0]
    mark = assessment(r, 'integrated_composite_candidate')
    if weak == 'title':
        mark['evidence'] = [evidence(r, 'job_title', '全栈')]
    elif weak == 'stacks':
        mark['evidence'] = [evidence(r, 'requirements', 'Java 和 Python')]
    elif weak == 'assist':
        mark['components'] = [dict(domain='前端', responsibility='auxiliary', evidence=[evidence(r, 'duties', '开发前端页面')]),
            dict(domain='后端', responsibility='core', evidence=[evidence(r, 'duties', '开发后端服务')])]
        mark['shared_delivery'] = evidence(r, 'duties', '统一负责完整应用上线')
    body = validate(batch, submission(r, assessments=[mark]))
    assert body['assessments'][0]['kind'] == 'composite_unproven'
    assert body['position_target_proposals'] == [] and body['canonical_job']['value'] is None


def integrated(r):
    return assessment(r, 'integrated_composite_candidate',
        components=[dict(domain='前端', responsibility='core', evidence=[evidence(r, 'duties', '开发前端页面')]),
            dict(domain='后端', responsibility='core', evidence=[evidence(r, 'duties', '开发后端服务')])],
        shared_delivery=evidence(r, 'raw_text', r.payload['raw_text']))


def test_integrated_delivery_is_only_pending_composite_not_canonical_or_vacancies(area):
    batch = source(area)
    body = validate(batch, submission(batch.records[0], assessments=[integrated(batch.records[0])]))
    assert body['assessments'][0]['kind'] == 'integrated_composite_candidate'
    assert body['assessments'][0]['review_status'] == 'pending_review'
    assert body['canonical_job']['value'] is None and body['position_target_proposals'] == []
    assert 'headcount' not in body and 'vacancies' not in body


MULTI = '职位甲【A01】\n职责：开发甲系统\n要求：掌握甲技术\n职位乙【B02】\n职责：测试乙系统\n要求：掌握乙技术'


def multiple(area):
    batch = source(area, job_title='独立职位招聘材料', raw_text=MULTI)
    r = batch.records[0]
    targets = []
    for identity, title, code, duty, requirement, section in [
        ('target-a', '职位甲', 'A01', '开发甲系统', '掌握甲技术', MULTI.split('职位乙')[0]),
        ('target-b', '职位乙', 'B02', '测试乙系统', '掌握乙技术', '职位乙' + MULTI.split('职位乙')[1])]:
        targets.append(dict(id=identity, raw_title=title, title=evidence(r, 'raw_text', title),
            identifier=evidence(r, 'raw_text', code), section=evidence(r, 'raw_text', section),
            duties=[evidence(r, 'raw_text', duty)], requirements=[evidence(r, 'raw_text', requirement)]))
    mark = assessment(r, 'possible_multiple_positions', position_targets=targets)
    return batch, submission(r, assessments=[mark])


def test_independent_position_sections_form_proposals_without_publishing_or_headcount(area):
    batch, marks = multiple(area)
    body = validate(batch, marks)
    assert [t['raw_title'] for t in body['position_target_proposals']] == ['职位甲', '职位乙']
    assert body['material_resolution'] == 'pending_target_review'
    assert all(t['formal_admitted'] is False for t in body['position_target_proposals'])
    assert body['source_payload']['raw_text'] == MULTI
    assert 'headcount' not in body and 'vacancy_count' not in body


@pytest.mark.parametrize('bad', ['missing_requirement', 'overlap', 'same_title', 'same_identifier', 'foreign_section', 'conflict'])
def test_inadequate_or_inconsistent_sections_preserve_jd_unresolved(area, bad):
    batch, marks = multiple(area)
    r = batch.records[0]
    ann = marks['annotations'][0]
    targets = ann['assessments'][0]['position_targets']
    if bad == 'missing_requirement':
        targets[1]['requirements'] = []
    elif bad == 'overlap':
        targets[0]['section'] = evidence(r, 'raw_text', MULTI)
    elif bad == 'same_title':
        targets[1]['raw_title'], targets[1]['title'] = targets[0]['raw_title'], targets[0]['title']
    elif bad == 'same_identifier':
        targets[1]['identifier'] = targets[0]['identifier']
    elif bad == 'foreign_section':
        targets[1]['duties'] = targets[0]['duties']
    else:
        ann['conflicts'] = [dict(title=evidence(r, 'job_title', r.payload['job_title']),
            duties=evidence(r, 'raw_text', MULTI), reason='分段招聘含义冲突待审')]
    body = validate(batch, marks)
    assert body['position_target_proposals'] == [] and body['material_resolution'] == 'unresolved'
    assert body['assessments'][0]['submitted_claim']['position_targets'] == targets


@pytest.mark.parametrize('bad', ['jd_id', 'namespace', 'fingerprint', 'start', 'end', 'quote', 'field', 'headcount', 'formal', 'credentials', 'duplicate'])
def test_invalid_boundary_input_is_rejected(area, bad):
    batch, marks = multiple(area)
    a = marks['annotations'][0]
    ref = a['assessments'][0]['position_targets'][0]['duties'][0]
    if bad in ('jd_id', 'namespace', 'fingerprint', 'quote', 'field'):
        ref[bad] = '0' * 64 if bad == 'fingerprint' else 'foreign'
    elif bad in ('start', 'end'):
        ref[bad] = 999
    elif bad == 'duplicate':
        a['assessments'] *= 2
    else:
        a[dict(headcount='headcount', formal='formal_admitted', credentials='api_key')[bad]] = 2
    with pytest.raises(ValueError):
        validate(batch, marks)


def test_explicit_conflicts_keep_family_and_canonical_unresolved_without_erasing_tracks(area):
    batch = source(area)
    r = batch.records[0]
    marks = submission(r, assessments=[integrated(r)], conflicts=[dict(title=evidence(r, 'job_title', '全栈'),
        duties=evidence(r, 'duties', '开发后端服务'), reason='责任冲突')])
    body = validate(batch, marks)
    assert body['job_family']['state'] == body['canonical_job']['state'] == 'unresolved'
    assert body['assessments'][0]['kind'] == 'composite_unproven'
    assert body['technology_tracks'][0]['value'] == 'Java'


@pytest.mark.parametrize('bad', ['same_span', 'same_domain', 'delivery_is_component'])
def test_duplicate_component_evidence_cannot_establish_integrated_responsibility(area, bad):
    batch = source(area)
    r = batch.records[0]
    mark = integrated(r)
    if bad == 'same_span':
        mark['components'][1]['evidence'] = mark['components'][0]['evidence']
    elif bad == 'same_domain':
        mark['components'][1]['domain'] = mark['components'][0]['domain']
    else:
        mark['shared_delivery'] = mark['components'][0]['evidence'][0]
    body = validate(batch, submission(r, assessments=[mark]))
    assert body['assessments'][0]['kind'] == 'composite_unproven'


@pytest.mark.parametrize('text', ['Java 与 Python', '核心职责：开发前端页面；开发后端服务', '偶尔协助后端模块'])
def test_skills_modules_and_assistance_alone_never_produce_position_targets(area, text):
    batch = source(area, raw_text=text)
    r = batch.records[0]
    body = validate(batch, submission(r, assessments=[assessment(r, 'possible_multiple_positions',
        evidence=[evidence(r, 'raw_text', text)])]))
    assert body['position_target_proposals'] == [] and body['material_resolution'] == 'unresolved'


@pytest.mark.parametrize('family', ['software_engineering', 'test_quality_engineering', 'data_ai',
    'infrastructure_operations', 'network_information_security', 'embedded_system_software',
    'technical_services_delivery', 'hardware_integrated_circuits'])
def test_each_confirmed_family_can_be_explicitly_claimed_without_publishing_jobs(area, family):
    batch = source(area)
    r = batch.records[0]
    marks = submission(r)
    marks['annotations'][0]['family_assertions'][0]['family_id'] = family
    body = validate(batch, marks)
    assert body['job_family']['assertions'][0]['family_id'] == family
    assert body['job_family']['state'] == 'pending_claim'
    assert body['canonical_job']['state'] == 'unknown' and body['formal_jobs'] == []


@pytest.mark.parametrize('has_identifiers', [True, False])
def test_same_title_independent_targets_can_be_distinguished_by_position_codes(area, has_identifiers):
    text = MULTI.replace('职位甲', '工程师').replace('职位乙', '工程师')
    batch = source(area, job_title='独立职位招聘材料', raw_text=text)
    r = batch.records[0]
    second = text.index('工程师', 1)
    targets = []
    for identity, start, end, code, duty, requirement in [
        ('target-a', 0, second, 'A01', '开发甲系统', '掌握甲技术'),
        ('target-b', second, len(text), 'B02', '测试乙系统', '掌握乙技术')]:
        title_ref = evidence(r, 'raw_text', '工程师') | dict(start=start, end=start + 3)
        targets.append(dict(id=identity, raw_title='工程师', title=title_ref,
            identifier=evidence(r, 'raw_text', code) if has_identifiers else None,
            section=evidence(r, 'raw_text', text[start:end]), duties=[evidence(r, 'raw_text', duty)],
            requirements=[evidence(r, 'raw_text', requirement)]))
    mark = assessment(r, 'possible_multiple_positions', position_targets=targets)
    body = validate(batch, submission(r, assessments=[mark]))
    assert len(body['position_target_proposals']) == (2 if has_identifiers else 0)
    assert body['material_resolution'] == ('pending_target_review' if has_identifiers else 'unresolved')
    assert body['formal_admitted'] is False and 'headcount' not in body


@pytest.mark.parametrize('field,value', [('proposer', None), ('proposer', ' '), ('origin', 'manual_confirmed')])
def test_dimension_assertions_require_attributed_pending_origin(area, field, value):
    batch = source(area)
    marks = submission(batch.records[0])
    if value is None:
        marks['annotations'][0].pop(field, None)
    else:
        marks['annotations'][0][field] = value
    with pytest.raises(ValueError):
        validate(batch, marks)
