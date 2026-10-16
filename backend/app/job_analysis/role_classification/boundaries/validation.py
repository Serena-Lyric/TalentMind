"""Deterministic structural gates, never a semantic approval of submitted assertions."""
from ...foundation.inputs import check_public
from ..validation import validate_evidence
from ..proposals.models import resolve_taxonomy
from ..governance.validation import validate_submission as validate_candidates
from .models import Submission


def assessment_refs(item):
    refs = list(item.evidence)
    refs.extend(e for c in item.components for e in c.evidence)
    if item.shared_delivery:
        refs.append(item.shared_delivery)
    for target in item.position_targets:
        refs.extend([target.title, target.section, *target.duties, *target.requirements])
        if target.identifier:
            refs.append(target.identifier)
    return refs


def _inside(ref, section):
    return ref.field == section.field and section.start <= ref.start < ref.end <= section.end


def _disjoint(a, b):
    return a.field != b.field or a.end <= b.start or b.end <= a.start


def target_gate(targets):
    if len(targets) < 2:
        return False
    codes = [t.identifier.quote.strip().casefold() for t in targets if t.identifier]
    if len(codes) != len(set(codes)):
        return False
    for i, target in enumerate(targets):
        if any(target.raw_title.strip().casefold() == other.raw_title.strip().casefold()
               and (target.identifier is None or other.identifier is None) for other in targets[i + 1:]):
            return False
    for i, target in enumerate(targets):
        if target.section.field not in ('raw_text', 'duties') or target.title.quote != target.raw_title:
            return False
        if not target.duties or not target.requirements:
            return False
        refs = [target.title, *target.duties, *target.requirements, *([target.identifier] if target.identifier else [])]
        if any(not _inside(r, target.section) for r in refs):
            return False
        if any(not _disjoint(a, b) for j, a in enumerate(refs) for b in refs[j + 1:]):
            return False
        if any(not _disjoint(target.section, other.section) or target.section.field != other.section.field
               for other in targets[i + 1:]):
            return False
    return True


def composite_gate(item):
    refs = [e for c in item.components for e in c.evidence]
    independent = all(a.quote != b.quote and _disjoint(a, b)
        for i, c in enumerate(item.components) for other in item.components[i + 1:]
        for a in c.evidence for b in other.evidence)
    return (len(item.components) >= 2
        and len({c.domain.strip().casefold() for c in item.components}) == len(item.components)
        and independent
        and all(c.responsibility == 'core' and all(e.field in ('duties', 'raw_text') for e in c.evidence)
                for c in item.components)
        and item.shared_delivery is not None and item.shared_delivery.field in ('duties', 'raw_text')
        and all(item.shared_delivery.quote != e.quote for e in refs))


def validate_submission(batch, submission, taxonomy):
    check_public(submission)
    marks = Submission.model_validate(submission)
    families = {f['id'] for f in resolve_taxonomy(taxonomy)['job_family']}
    # Reuse B32's strict identity, full input-byte, candidate and conflict verification, without writing it.
    old_marks = dict(schema_version='b32-submission-1', revision=marks.revision, mode=marks.mode,
        annotations=[dict(namespace=a.namespace, jd_id=a.jd_id, fingerprint=a.fingerprint,
            candidates=[c.model_dump() for c in a.candidates], relations=[], material_kind='undetermined',
            material_evidence=[], conflicts=[c.model_dump() for c in a.conflicts], notes=a.notes) for a in marks.annotations])
    old = validate_candidates(batch, old_marks, dict(schema_version='b32-catalog-1', revision='empty-v1', formal_jobs=[]), taxonomy=taxonomy)
    annotations = {a.jd_id: a for a in marks.annotations}
    all_ids, bodies = set(), []
    for record, base in zip(batch.records, old, strict=True):
        if record.payload['source'] != 'synthetic':
            raise ValueError('B3-4 accepts explicitly synthetic sources only')
        mark = annotations.get(record.jd_id)
        family, tracks, seniority, assessments, targets = [], [], [], [], []
        canonical_ids = [c['id'] for c in base['candidates'] if c['kind'] != 'technology_stack']
        reasons = list(base['reasons'])
        conflict = bool(base['conflicts'])
        if mark:
            objects = [*mark.family_assertions, *mark.candidates, *mark.technology_tracks, *mark.seniority, *mark.assessments,
                       *(t for a in mark.assessments for t in a.position_targets)]
            ids = [o.id for o in objects]
            if len(set(ids)) != len(ids) or all_ids.intersection(ids):
                raise ValueError('boundary IDs must be unique across the submission')
            all_ids.update(ids)
            for assertion in mark.family_assertions:
                if assertion.family_id not in families:
                    raise ValueError('family outside explicit taxonomy')
                for ref in assertion.evidence:
                    validate_evidence(record, ref.model_dump())
                family.append(assertion.model_dump() | dict(origin=mark.origin, proposer=mark.proposer,
                    review_status='pending_review', formal_admitted=False))
            for collection, output in ((mark.technology_tracks, tracks), (mark.seniority, seniority)):
                for assertion in collection:
                    for ref in assertion.evidence:
                        validate_evidence(record, ref.model_dump())
                    output.append(assertion.model_dump() | dict(origin=mark.origin, proposer=mark.proposer,
                        review_status='pending_review', formal_admitted=False))
            for claim in mark.assessments:
                if claim.origin != 'synthetic_assertion':
                    raise ValueError('synthetic submission cannot impersonate manual review')
                for ref in assessment_refs(claim):
                    validate_evidence(record, ref.model_dump())
                if claim.kind != 'possible_multiple_positions' and claim.position_targets:
                    raise ValueError('position targets require a multiple-position claim')
                if claim.kind not in ('integrated_composite_candidate', 'composite_unproven') and (claim.components or claim.shared_delivery):
                    raise ValueError('composite evidence requires a composite claim')
                kind, gate_reasons = claim.kind, []
                if kind == 'integrated_composite_candidate' and (conflict or not composite_gate(claim)):
                    kind = 'composite_unproven'
                    gate_reasons.append('complete_integrated_responsibility_not_established')
                if kind == 'family_identifiable_job_unknown' and (not family or canonical_ids or conflict):
                    gate_reasons.append('family_only_claim_not_established')
                if kind == 'competing_canonical_candidates' and len(canonical_ids) < 2:
                    gate_reasons.append('competing_candidates_not_established')
                if kind == 'possible_multiple_positions':
                    if not conflict and target_gate(claim.position_targets):
                        targets.extend(t.model_dump() | dict(assessment_id=claim.id, review_status='pending_review', formal_admitted=False)
                                       for t in claim.position_targets)
                    else:
                        gate_reasons.append('independent_position_targets_not_established')
                assessments.append(dict(id=claim.id, kind=kind, submitted_claim=claim.model_dump(),
                    gate_reasons=gate_reasons, review_status='pending_review', formal_admitted=False))
        # Multiple separate target interpretations cannot jointly constitute a segmentation.
        if sum(a['kind'] == 'possible_multiple_positions' for a in assessments) > 1:
            targets = []
            reasons.append('competing_position_segmentations')
        family_ids = {f['family_id'] for f in family if f['responsibility'] == 'core'}
        has_duties = bool(family) and all(all(e['field'] in ('duties', 'raw_text') for e in f['evidence']) for f in family)
        family_state = ('pending_claim' if len(family_ids) == 1 and has_duties and not conflict
            and all(f['responsibility'] != 'unspecified' for f in family) else 'unresolved' if family or conflict else 'unknown')
        bodies.append(dict(schema_version='b34-boundary-1', namespace=record.namespace, jd_id=record.jd_id,
            fingerprint=record.fingerprint, source_payload=record.payload,
            job_family=dict(state=family_state, assertions=family), candidates=base['candidates'],
            canonical_job=dict(state='unresolved' if canonical_ids or conflict else 'unknown', value=None, candidates=canonical_ids),
            technology_tracks=tracks, seniority=seniority, assessments=assessments,
            position_target_proposals=targets, material_resolution='pending_target_review' if targets else
                'unresolved' if any(a['kind'] == 'possible_multiple_positions' for a in assessments) else 'undetermined',
            conflicts=base['conflicts'], reasons=reasons, notes=base['notes'],
            review_status='pending_review', semantic_validation='not_performed', evidence_validation='source_spans_matched',
            evidence_origin='explicit_synthetic_assertions', formal_jobs=[], formal_admitted=False,
            classification_complete=False, formal_statistics_eligible=False))
    return bodies
