"""Compare saved runs without interpreting explanation drift as a market trend."""


def _layer(kind, before, after, comparable):
    available = comparable and before is not None and after is not None
    return dict(kind=kind, before=before, after=after, available=available,
                changed=before != after if available else None,
                reason='saved_version_comparison' if available else 'missing_or_unrelated_source')


def compare_runs(before: dict, after: dict) -> dict:
    old = {(item['namespace'], item['jd_id']): item for item in before['items']}
    new = {(item['namespace'], item['jd_id']): item for item in after['items']}
    items = []
    for identity in sorted(old.keys() | new.keys()):
        left, right = old.get(identity, {}), new.get(identity, {})
        comparable = bool(left and right)
        def source_text(item):
            row = item.get('input')
            return {key: row.get(key) for key in ('job_title', 'raw_text', 'duties', 'requirements', 'experience')} if row is not None else None
        layers = [_layer('input', source_text(left), source_text(right), comparable)]
        layers.extend(_layer(kind, left.get(field), right.get(field), comparable)
                      for kind, field in [('analysis', 'analysis'), ('skill_governance', 'knowledge_projection')])
        layers.append(_layer('knowledge', dict(snapshot=before.get('knowledge'), alignment=left.get('alignment'), roles=left.get('roles')) if left.get('alignment') is not None else None,
                             dict(snapshot=after.get('knowledge'), alignment=right.get('alignment'), roles=right.get('roles')) if right.get('alignment') is not None else None, comparable))
        items.append(dict(namespace=identity[0], jd_id=identity[1], source_comparable=comparable,
                          before_input_version=left.get('input_version'), after_input_version=right.get('input_version'),
                          before_analysis_sha256=left.get('analysis_sha256'), after_analysis_sha256=right.get('analysis_sha256'), layers=layers))
    old_work, new_work = before.get('work') or {}, after.get('work') or {}
    old_binding, new_binding = old_work.get('binding') or {}, new_work.get('binding') or {}
    same_registry = bool(old_binding.get('registry_id')) and old_binding.get('registry_id') == new_binding.get('registry_id')
    research = _layer('work_research', old_work.get('candidates'), new_work.get('candidates'), same_registry)
    research.update(before_binding=old_binding, after_binding=new_binding,
                    before_causes=(old_work.get('report') or {}).get('evolution'), after_causes=(new_work.get('report') or {}).get('evolution'))
    return dict(before_run=before['run_id'], after_run=after['run_id'],
                before_request_sha256=before['request_sha256'], after_request_sha256=after['request_sha256'],
                before_created_at=before.get('created_at'), after_created_at=after.get('created_at'),
                items=items, research=research,
                change_nature='saved_analysis_and_research_comparison', market_change_verified=False,
                interpretation='原文、模型/知识解释与候选研究分别比较；差异不代表已核实的市场需求变化。')
