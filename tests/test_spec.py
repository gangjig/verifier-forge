"""Spec loading and validation."""

from __future__ import annotations

import pytest

from verifier_forge.spec import SpecError, load_spec, parse_spec

BASE = {
    "name": "t",
    "task": "do the thing",
    "evidence": ["actions"],
    "rules": ["rule one"],
    "candidates": [
        {"name": "a", "kind": "reference", "evidence": {"actions": []}, "expected": "pass"},
        {"name": "b", "kind": "empty", "evidence": {"actions": []}, "expected": "fail"},
    ],
}


def test_parse_minimal_spec():
    spec = parse_spec(BASE)
    assert spec.name == "t"
    assert len(spec.candidates) == 2
    assert spec.candidates[0].expected == "pass"


def test_rules_default_empty():
    data = {k: v for k, v in BASE.items() if k != "rules"}
    assert parse_spec(data).rules == []


def test_kind_defaults():
    data = json_clone(BASE)
    del data["candidates"][0]["kind"]
    assert parse_spec(data).candidates[0].kind == "candidate"


def json_clone(data):
    import copy

    return copy.deepcopy(data)


@pytest.mark.parametrize("field", ["name", "task"])
def test_missing_required_strings(field):
    data = json_clone(BASE)
    data[field] = "  "
    with pytest.raises(SpecError, match=field):
        parse_spec(data)


def test_evidence_head_must_be_nonempty():
    data = json_clone(BASE)
    data["evidence"] = []
    with pytest.raises(SpecError, match="evidence"):
        parse_spec(data)


def test_candidate_evidence_must_stay_inside_head():
    data = json_clone(BASE)
    data["candidates"][0]["evidence"] = {"actions": [], "secret_field": 1}
    with pytest.raises(SpecError, match="not declared"):
        parse_spec(data)


def test_candidate_expected_must_be_a_verdict():
    data = json_clone(BASE)
    data["candidates"][0]["expected"] = "maybe"
    with pytest.raises(SpecError, match="expected"):
        parse_spec(data)


def test_duplicate_candidate_names_rejected():
    data = json_clone(BASE)
    data["candidates"][1]["name"] = "a"
    with pytest.raises(SpecError, match="duplicate"):
        parse_spec(data)


def test_too_few_candidates_rejected():
    data = json_clone(BASE)
    data["candidates"] = data["candidates"][:1]
    with pytest.raises(SpecError, match="at least two"):
        parse_spec(data)


def test_load_spec_roundtrip(tmp_path):
    import json

    path = tmp_path / "spec.json"
    path.write_text(json.dumps(BASE), encoding="utf-8")
    assert load_spec(path).name == "t"


def test_load_spec_missing_file(tmp_path):
    with pytest.raises(SpecError, match="cannot read"):
        load_spec(tmp_path / "nope.json")


def test_load_spec_bad_json(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SpecError, match="invalid JSON"):
        load_spec(path)


def test_example_spec_is_valid():
    from pathlib import Path

    spec = load_spec(Path(__file__).parent.parent / "examples" / "refund-spec.json")
    assert spec.name == "refund-request"
    assert len(spec.candidates) == 6
