"""Strict definitions and byte-bound provenance, without semantic or identity claims."""
import hashlib
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ..foundation.inputs import check_public, parse_json
from ..foundation.models import VersionName
from ..role_classification.models import StrictModel, Text, Fingerprint
from ..role_classification.governance.models import StableID
from ..role_classification.proposals.models import FAMILY_VERSIONS

Name = Annotated[str, StringConstraints(min_length=1, pattern=r'^\S(?:.*\S)?$')]


def load_json(path):
    path = Path(path)
    if path.suffix.lower() != '.json':
        raise ValueError('explicit JSON required')
    value = parse_json(path.read_bytes().decode('utf-8-sig'))
    check_public(value)
    return value


class Source(StrictModel):
    path: Text
    sha256: Fingerprint
    quote: Text


def freeze_sources(refs, root):
    root = Path(root).resolve(strict=True)
    frozen = {}
    for ref in refs:
        item = Source.model_validate(ref).model_dump()
        path = PurePosixPath(item['path'])
        if path.is_absolute() or '..' in path.parts or '\\' in item['path'] or ':' in item['path']:
            raise ValueError('source must be a relative POSIX path within explicit root')
        resolved = (root / item['path']).resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError('source escapes root')
        raw = resolved.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256'] or item['quote'] not in raw.decode('utf-8-sig'):
            raise ValueError('source hash or quote mismatch')
        frozen[item['path']] = dict(path=item['path'], sha256=item['sha256'], raw_hex=raw.hex())
    return list(frozen.values())


class Neighbor(StrictModel):
    candidate_id: StableID
    distinction: Text


class Candidate(StrictModel):
    id: StableID
    proposed_name: Name
    family_id: Name
    core_responsibilities: list[Text] = Field(min_length=1)
    deliverables: list[Text] = Field(min_length=1)
    definition_basis: list[Source] = Field(min_length=1)
    exclusions: list[Text] = Field(min_length=1)
    neighbors: list[Neighbor] = Field(min_length=1)
    proposed_aliases: list[Name]
    status: Literal['candidate']
    confirmation_status: Literal['unconfirmed']
    origin: Literal['ai_draft']


class Catalog(StrictModel):
    schema_version: Literal['c35-candidates-1']
    revision: VersionName
    family_revision: Literal['families-v1', 'families-v2', 'families-v3']
    candidates: list[Candidate] = Field(min_length=1)

    @model_validator(mode='after')
    def boundaries(self):
        ids = [c.id for c in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate candidate ID')
        names = set()
        for c in self.candidates:
            if c.family_id not in FAMILY_VERSIONS[self.family_revision]:
                raise ValueError('family not registered in selected version')
            neighbors = [n.candidate_id for n in c.neighbors]
            if c.id in neighbors or not set(neighbors) <= set(ids) or len(neighbors) != len(set(neighbors)):
                raise ValueError('invalid or duplicate boundary target')
            for name in [c.proposed_name, *c.proposed_aliases]:
                key = (c.family_id, name.casefold())
                if key in names:
                    raise ValueError('ambiguous name or alias in family; keep unresolved outside catalogue')
                names.add(key)
        return self


def validate_catalog(value, source_root):
    check_public(value)
    item = Catalog.model_validate(value).model_dump()
    return item, freeze_sources([s for c in item['candidates'] for s in c['definition_basis']], source_root)


class Review(StrictModel):
    schema_version: Literal['c35-review-1']
    snapshot_id: StableID
    candidate_id: StableID
    candidate_sha256: Fingerprint
    decision: Literal['reviewed_accepted', 'rejected', 'deferred']
    reviewer: Name
    basis: Text
    source: Source
    confirmed_responsibilities: bool
    confirmed_boundaries: bool
    confirmed_family: bool
    mode: Literal['synthetic_only', 'manual_pending']
    supersedes: StableID | None


class Approval(StrictModel):
    candidate_id: StableID
    candidate_sha256: Fingerprint
    review_id: StableID
    confirmation_source: Source


class ReleaseManifest(StrictModel):
    schema_version: Literal['c35-release-manifest-1']
    revision: VersionName
    snapshot_id: StableID
    mode: Literal['synthetic_only', 'release_proposal']
    approvals: list[Approval] = Field(min_length=1)
    previous_release_id: StableID | None
