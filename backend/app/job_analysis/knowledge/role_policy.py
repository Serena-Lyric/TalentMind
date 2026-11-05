"""Versioned, bounded Chinese comparison rules; never occupational definitions."""
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from ..foundation.inputs import check_public, digest, parse_json
from .models import Sha256, Strict, Text


class Frame(Strict):
    reference_id: Text
    actions: list[Text] = Field(min_length=1)
    objects: list[Text] = Field(min_length=1)


class RoleRule(Strict):
    role_id: Text
    family: Text | None
    canonical_candidate: bool
    composite_reference: bool = False
    frames: list[Frame]
    boundary_frames: list[Frame] = Field(default_factory=list)
    deliveries: list[Text]
    adaptation_note: Text


class AttributionPolicy(Strict):
    schema_version: Literal["m2-role-policy-1"]
    revision: Text
    knowledge_sha256: Sha256
    family_source: Text
    roles: list[RoleRule]
    track_terms: list[Text]
    scope_limitation: Text

    @model_validator(mode="after")
    def unique_rules(self):
        if len({r.role_id for r in self.roles}) != len(self.roles):
            raise ValueError("duplicate role rule")
        for rule in self.roles:
            refs = [f.reference_id for f in rule.frames + rule.boundary_frames]
            if len(set(refs)) != len(refs):
                raise ValueError("duplicate comparison frame")
        if len(set(self.track_terms)) != len(self.track_terms):
            raise ValueError("duplicate technology track")
        return self


@dataclass(frozen=True)
class BoundPolicy:
    path: Path
    policy: AttributionPolicy
    sha256: str


def default_policy_path() -> Path:
    return Path(__file__).parent / "policies" / "role-attribution.v1.json"


def bind_policy(value: dict, path: Path = Path(".")) -> BoundPolicy:
    check_public(value)
    policy = AttributionPolicy.model_validate(value)
    return BoundPolicy(path, policy, digest(policy.model_dump()))


def load_policy(path: Path | str) -> BoundPolicy:
    path = Path(path).resolve(strict=True)
    return bind_policy(parse_json(path.read_text(encoding="utf-8-sig")), path)
