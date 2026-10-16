"""Closed synthetic boundary examples, never a semantic accuracy benchmark."""
import hashlib

import pytest

from test_foundation_inputs import area
from test_role_proposals import CATALOG, record, no_network

V3 = CATALOG.with_name('families.v3.json')
HARDWARE = 'hardware_integrated_circuits'


def taxonomy():
    from app.job_analysis.role_classification.proposals.models import load_taxonomy
    return load_taxonomy(V3)


def test_v3_preserves_old_catalog_bytes_and_eight_family_identity():
    from app.job_analysis.role_classification.proposals.models import load_taxonomy
    assert hashlib.sha256(CATALOG.read_bytes().replace(b'\r\n', b'\n')).hexdigest() == '10194ea96ec0b3a82759ccabef1e7fe9fc82382db6789cde83964c9383ed9519'
    old = load_taxonomy(CATALOG.with_name('families.v2.json'))
    new = taxonomy()
    assert new['revision'] == 'families-v3'
    assert [(f['id'], f['label']) for f in new['job_family']] == [(f['id'], f['label']) for f in old['job_family']]
    assert new['job_family'][-1]['scope'] != old['job_family'][-1]['scope']
    assert new['canonical_job'] == new['technology_tracks'] == new['seniority'] == []


@pytest.mark.parametrize('work', ['开发半导体工艺并交付验证报告', '优化封装工艺并交付工程方案', '改进制造良率并交付分析方案'])
def test_v3_engineering_deliveries_are_pending_and_not_reinterpreted_in_v2(work):
    from app.job_analysis.role_classification.proposals.models import load_taxonomy
    from app.job_analysis.role_classification.proposals.rules import suggest
    item = record('核心职责：' + work)
    body = suggest(item, taxonomy())
    assert body['primary_family_hint'] == HARDWARE
    assert body['review_status'] == 'pending_review'
    assert body['canonical_job'] == dict(state='unknown', value=None)
    assert body['classification_complete'] is body['formal_statistics_eligible'] is False
    assert suggest(item, load_taxonomy(CATALOG.with_name('families.v2.json')))['candidates'] == []


@pytest.mark.parametrize('text', ['负责产线操作', '负责日常重复性设备操作', '工厂宣传：先进半导体工艺',
    '负责销售封装设备', '历史项目：核心职责：开发半导体工艺并交付验证报告',
    '培训内容：核心职责：优化封装工艺并交付工程方案', '公司介绍：核心职责：改进制造良率并交付分析方案',
    '半导体 / 封装 / 制造 / 良率', '不负责开发半导体工艺并交付验证报告'])
def test_v3_title_industry_operations_and_noncurrent_work_are_not_family_evidence(text):
    from app.job_analysis.role_classification.proposals.rules import suggest
    body = suggest(record(text, '半导体工艺工程师'), taxonomy())
    assert body['candidates'] == [] and body['primary_family_hint'] is None


@pytest.mark.parametrize('text', ['负责优化封装工艺并交付工程方案',
    '核心职责：改进制造良率并交付分析方案。核心职责：开发嵌入式驱动并交付固件',
    '核心职责：开发半导体工艺并交付验证报告。设备维护职责待定'])
def test_v3_cross_family_unclear_or_unparsed_work_stays_unresolved(text):
    from app.job_analysis.role_classification.proposals.rules import suggest
    body = suggest(record(text), taxonomy())
    assert body['resolution'] == 'unresolved' and body['primary_family_hint'] is None
