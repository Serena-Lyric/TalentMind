"""Position verification and rule conformance are separate checks; neither is human truth."""
from ..foundation.inputs import check_public, parse_json
from .models import Document
from .rules import extract


def validate(raw, record, analyzer):
    value = parse_json(raw) if isinstance(raw, str) else raw
    check_public(value)
    value = Document.model_validate(value).model_dump()

    def check(item):
        if isinstance(item, dict):
            if {"quote", "start", "end", "field", "namespace", "jd_id", "fingerprint"} <= item.keys():
                if (item["namespace"], item["jd_id"], item["fingerprint"]) != (record.namespace, record.jd_id, record.fingerprint):
                    raise ValueError("foreign JD evidence")
                text = record.payload.get(item["field"], "")
                if not 0 <= item["start"] < item["end"] <= len(text) or text[item["start"]:item["end"]] != item["quote"]:
                    raise ValueError("evidence offset mismatch")
            for child in item.values():
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)
    check(value)
    # Do not trust an analyzer-supplied state just because its quotation matched.
    # This verifies the bounded grammar, not its accuracy on real recruitment language.
    if value != extract(record, analyzer.aliases):
        raise ValueError("result does not conform to versioned semantic rules")
    return value
