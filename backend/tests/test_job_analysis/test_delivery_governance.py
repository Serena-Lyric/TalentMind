import asyncio

from app.job_analysis.delivery import DeliveryStore, execute
from app.job_analysis.knowledge.candidates import CandidateRegistry
from test_delivery import request
from test_foundation_inputs import area
from test_knowledge_governance import unknown_case, shipped


def test_delivery_observes_projects_and_consumes_candidates_without_rewriting_history(area):
    first, _ = unknown_case(raw_text='要求：使用 Flink SQL 开发实时数据任务。',
                            jd_id='one', row_extra={'source_identity': 'employer-a'})
    second, _ = unknown_case(raw_text='岗位需要具备 Flink SQL 实现流式任务的能力。',
                             jd_id='two', row_extra={'source_identity': 'employer-b'})
    with DeliveryStore(area / 'delivery', create=True) as store:
        one = asyncio.run(execute(store, 'one', request(store, [first]), shipped()))
        assert one['items'][0]['skill_candidates'][0]['status'] == 'observing'
        two = asyncio.run(execute(store, 'two', request(store, [second]), shipped()))
        item = two['items'][0]
        assert item['skill_candidates'][0]['status'] == 'corroborated'
        assert item['alignment']['requirements'][0]['alignments'][0]['concept_source'] == 'candidate'
        assert item['alignment']['candidate_projection_sha256'] == item['knowledge_projection']['sha256']
        registry = CandidateRegistry(store.root / 'skill-candidates')
        registry.withdraw(item['skill_candidates'][0]['candidate_id'], 'source correction')
        three = asyncio.run(execute(store, 'three', request(store, [second]), shipped()))
        assert three['items'][0]['skill_candidates'][0]['status'] == 'withdrawn'
        assert three['items'][0]['alignment']['requirements'][0]['alignments'][0]['state'] == 'unknown'
        assert store.read('two') == two
        assert store.read('one') == one
