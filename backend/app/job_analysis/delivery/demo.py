"""Permanent integrated CLI sequence, synthetic source only, zero external services."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from ..foundation.inputs import canonical, digest
from ..foundation.store import safe_destination
from ..knowledge.catalog import load_snapshot
from ..work_candidates.demo import synthetic_analysis


def run_demo(output, knowledge):
    root = safe_destination(output)
    root.mkdir(parents=True, exist_ok=False)
    state = root / 'state'
    commands = []

    def write(name, value):
        path = root / name
        with path.open('x', encoding='utf-8') as stream: stream.write(canonical(value))
        return path

    def cli(*args):
        command = [sys.executable, '-m', 'app.job_analysis.delivery', *map(str, args)]
        run = subprocess.run(command, cwd=Path(__file__).resolve().parents[3], capture_output=True,
                             text=True, encoding='utf-8')
        commands.append(dict(command=command, exit_code=run.returncode))
        if run.returncode: raise ValueError('integrated demo command failed')
        return json.loads(run.stdout)

    initial = cli('init', '--state', state)
    a = synthetic_analysis('seed-python', ['开发订单交易接口。'], 'Python')
    b = synthetic_analysis('new-support', ['开发订单交易接口。', '执行幂等校验并维护去重记录。'], 'Go')
    c = synthetic_analysis('scope-check', ['执行幂等校验并维护去重记录。'], 'Go')
    states, paths = [], []

    def apply(values, operations=(), *, snapshot=knowledge, stopped=False):
        identity = 'batch-' + str(len(states) + 1)
        baseline = states[-1]['work']['binding'] if states else initial['binding']
        request = dict(schema_version='m2-delivery-request-1', baseline=baseline, operations=list(operations),
                       items=[dict(namespace=v['namespace'], row=v['input_row'], input_version=v['input_version'], analysis=v) for v in values])
        path = write(identity + '-request.json', request)
        args = ['run', '--state', state, '--id', identity, '--request', path, '--knowledge', snapshot, '--output', root / 'results']
        if stopped:
            marker = root / 'stop'
            marker.write_text('stop', encoding='utf-8')
            paused = cli(*args, '--stop-file', marker)
            if paused['status'] != 'stopped': raise ValueError('stop was ignored')
            marker.unlink()
            # Stopped progress exports and final exports intentionally have different destinations.
            cli('resume', '--state', state, '--id', identity, '--output', root / 'resumed')
            value = json.loads((root / 'resumed' / (identity + '.json')).read_text(encoding='utf-8'))
        else:
            cli(*args)
            value = json.loads((root / 'results' / (identity + '.json')).read_text(encoding='utf-8'))
        states.append(value)
        paths.append(args)

    apply([a], [dict(op='create', candidate_id='work-orders', description='交易工作研究种子',
                    research_question='新责任是否构成可解释的局部扩展？', core_work=[dict(analysis_sha256=digest(a), claim_id='d1')])])
    apply([b], [dict(op='link', candidate_id='work-orders', analysis_sha256=digest(b), work_ids=['d1', 'd2'],
                    reason='显式合成局部扩展，不是系统已确认同组')])
    apply([c], [dict(op='link', candidate_id='work-orders', analysis_sha256=digest(c), work_ids=['d1'],
                    reason='显式合成误关联供撤回验证；自动研究不允许传递并组')])
    old = next(r for r in states[-1]['work']['relations'].values() if r['jd_id'] == 'new-support')
    apply([a], [dict(op='correct', relation_id=old['id'], expected_sha256=digest(old), decision='weakens',
                    reason='合成反证收窄局部扩展', verification=None,
                    counterevidence=[dict(analysis_sha256=digest(a), claim_id='d1')])])
    other = next(r for r in states[-1]['work']['relations'].values() if r['jd_id'] == 'scope-check')
    apply([a], [dict(op='correct', relation_id=other['id'], expected_sha256=digest(other), decision='withdraw',
                    reason='撤回显式合成的未审提议', verification=None)])
    apply([a])
    loaded = load_snapshot(knowledge)
    updated = loaded.snapshot.model_dump()
    updated['revision'] = 'synthetic-delivery-v2'
    snapshot = root / 'knowledge-v2'
    snapshot.mkdir()
    raw = canonical(updated).encode('utf-8')
    (snapshot / 'knowledge.json').write_bytes(raw)
    (snapshot / 'manifest.json').write_text(canonical(dict(schema_version='m2-knowledge-manifest-1',
                                                           sha256=hashlib.sha256(raw).hexdigest())), encoding='utf-8')
    apply([a], snapshot=snapshot, stopped=True)
    cli(*paths[1])
    cli('read', '--state', state, '--id', 'batch-2', '--output', root / 'historical')
    old_read = json.loads((root / 'historical/batch-2.json').read_text(encoding='utf-8'))
    head = cli('head', '--state', state)['binding']
    search = states[2]['work']['report']['searches'][0]
    pairs = [p for m in search['candidate_checks']['work-orders']['members'] for p in m['comparisons']]
    core = dict(analysis_sha256=digest(b), claim_id='d2')
    summary = dict(batches=len(states), input_jd_identities=3,
                   research_versions=[s['work']['candidates']['work-orders']['research']['version'] for s in states],
                   third_batch_used_new_work=any(p['core_reference'] == core for p in pairs),
                   transitive_automatic_link_rejected=not search['matches'],
                   counterevidence_narrowed_scope=core not in states[3]['work']['candidates']['work-orders']['research']['comparison_work'],
                   exact_retry_kept_head=head == states[-1]['work']['binding'], historical_readback=old_read == states[1],
                   knowledge_changed_without_p1_change=(states[-1]['items'][0]['analysis'] == a and
                       states[-1]['knowledge'] != states[-2]['knowledge']), stopped_then_resumed=states[-1]['status'] == 'completed',
                   real_human_grouping_denominator=0, real_semantic_accuracy=None, independent_sources=None, vacancies=None,
                   explicit_inputs=['create', 'link', 'correct', 'knowledge_update'],
                   automatic=['P2-1 alignment/limited comparison', 'bounded direct-member comparison', 'research projection', 'historical replay'])
    if not all(summary[k] for k in ('third_batch_used_new_work', 'counterevidence_narrowed_scope', 'exact_retry_kept_head',
                                    'historical_readback', 'knowledge_changed_without_p1_change', 'stopped_then_resumed')):
        raise ValueError('integrated sequence self-check failed')
    write('summary.json', summary)
    write('commands.json', commands)
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(root.rglob('*')) if p.is_file() and p.suffix != '.lock'}
    write('manifest.json', dict(schema_version='m2-delivery-demo-1', files=files))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--knowledge', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_demo(args.output, args.knowledge), ensure_ascii=True))
