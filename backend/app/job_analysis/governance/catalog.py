"""Read-only seed index and small reviewed overlay; ambiguous aliases never win by order."""
from collections import Counter, defaultdict
import copy
import hashlib
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..foundation.inputs import digest, parse_json
from ..foundation.runner import dictionary

Category = Literal["technical_skill", "professional_skill", "engineering_practice", "soft_skill"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Relation(Strict):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    relation: Literal["synonym", "related_to", "narrower_than", "version_of"]
    basis: str = Field(min_length=1)


class Classification(Strict):
    name: str = Field(min_length=1)
    category: Category
    tags: list[str]
    basis: str = Field(min_length=1)


class Policy(Strict):
    version: str = Field(min_length=1)
    relations: list[Relation]
    versioned_bases: list[str]
    technical_categories: list[str]
    classifications: list[Classification]


def token(raw):
    return re.sub(r"\s+", " ", raw.strip()).casefold()


class Catalog:
    def __init__(self, seed=None, policy=None):
        self.seed = copy.deepcopy(dictionary() if seed is None else seed)
        self.policy = Policy.model_validate(policy if policy is not None else
            parse_json(Path(__file__).with_name("policy.v1.json").read_text(encoding="utf-8"))).model_dump()
        self.index = defaultdict(list)
        self.canonicals = defaultdict(list)
        for i, row in enumerate(self.seed):
            name = row["canonical"]
            self.canonicals[token(name)].append(row)
            for kind, term in [("canonical", name)] + [("alias", a) for a in row.get("aliases") or []]:
                self.index[token(term)].append(dict(row=i, kind=kind, canonical=name, raw_term=term))
        self.synonyms = {}
        for edge in self.policy["relations"]:
            if edge["relation"] != "synonym":
                continue
            source, target = token(edge["source"]), token(edge["target"])
            if target not in self.canonicals:
                if policy is not None:
                    raise ValueError("synonym target must exist in seed")
                continue
            if source in self.synonyms:
                raise ValueError("duplicate or conflicting reviewed synonym")
            # Targets must themselves be canonical, not synonym chains or cycles.
            self.synonyms[source] = edge
        if any(token(e["target"]) in self.synonyms for e in self.synonyms.values()):
            raise ValueError("synonym chains are not supported")
        self.classifications = {token(c["name"]): c for c in self.policy["classifications"]}
        if len(self.classifications) != len(self.policy["classifications"]):
            raise ValueError("duplicate classification")
        self.audit = self._audit()

    def _audit(self):
        audit = []
        for term, entries in sorted(self.index.items()):
            reasons = []
            if len({e["canonical"] for e in entries}) > 1:
                reasons.append("multiple_targets")
            if any(count > 1 for count in Counter((e["row"], e["kind"], e["raw_term"]) for e in entries).values()):
                reasons.append("duplicate_entry")
            if sum(e["kind"] == "canonical" for e in entries) > 1:
                reasons.append("duplicate_canonical")
            if any(e["kind"] == "alias" for e in entries):
                reasons.append("reviewed_synonym" if term in self.synonyms else "unreviewed_alias")
                if re.search(r"\d", term):
                    reasons.append("version_alias")
            for reason in reasons:
                audit.append(dict(term=term, reason=reason, entries=copy.deepcopy(entries)))
        return audit

    def resolve(self, raw):
        key = token(raw)
        matches = sorted({e["canonical"] for e in self.index.get(key, [])})
        name, version, basis = None, None, None
        edge = self.synonyms.get(key)
        if edge:
            name, basis = edge["target"], edge["basis"]
        elif len(self.canonicals.get(key, [])) == 1:
            name, basis = self.canonicals[key][0]["canonical"], "exact_seed_canonical"
        else:
            for base in self.policy["versioned_bases"]:
                hit = re.fullmatch(re.escape(token(base)) + r"\s*v?(\d+(?:\.\d+)*(?:\.x)?)", key)
                if hit and len(self.canonicals.get(token(base), [])) == 1:
                    name, version, basis = self.canonicals[token(base)][0]["canonical"], hit[1], "explicit_version_suffix"
                    break
            if name is None:
                for base in sorted(self.index, key=len, reverse=True):
                    hit = re.fullmatch(re.escape(base) + r"\s*((?:v|[<>=~^]+)?\s*\d.*)", key)
                    if hit:
                        version, basis = hit[1], "unsupported_version_expression"
                        matches = sorted({e["canonical"] for e in self.index[base]})
                        break
        return dict(raw_name=raw, canonical=name, version=version,
                    key=name + ("@" + version if version else "") if name else None,
                    status="known" if name else "needs_review", basis=basis, baseline_matches=matches)

    def classification(self, name):
        if token(name) in self.classifications:
            c = self.classifications[token(name)]
            return c["category"], c["tags"], c["basis"]
        rows = self.canonicals.get(token(name), [])
        if len(rows) == 1 and rows[0].get("category") in self.policy["technical_categories"]:
            return "technical_skill", [rows[0]["category"]], "seed_technical_category:" + rows[0]["category"]
        return None, [], "classification_pending_review"

    def manifest(self):
        implementations = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(Path(__file__).parent.glob("*.py"))}
        root = Path(__file__).resolve().parents[1]
        for relative in ("foundation/inputs.py", "foundation/models.py", "foundation/store.py", "foundation/runner.py",
                         "semantics/rules.py", "semantics/models.py", "semantics/runner.py"):
            implementations[relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        return dict(schema="b22-1", dictionary=digest(self.seed), policy=copy.deepcopy(self.policy), implementation=implementations)
