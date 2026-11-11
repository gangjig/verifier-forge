"""Generation prompt construction and code extraction."""

from __future__ import annotations

import pytest

from verifier_forge.generate import (
    GenerationError,
    build_generation_prompt,
    extract_verifier_code,
    generate_with_llm_cli,
)
from verifier_forge.spec import parse_spec

SPEC = parse_spec(
    {
        "name": "refund-request",
        "task": "Handle a refund request.",
        "evidence": ["actions", "final_message"],
        "rules": ["Confirm before issuing.", "Send a report after."],
        "candidates": [
            {"name": "a", "evidence": {"actions": [], "final_message": "x"}, "expected": "pass"},
            {"name": "b", "evidence": {"actions": [], "final_message": ""}, "expected": "fail"},
        ],
    }
)


def test_prompt_carries_task_evidence_and_rules():
    prompt = build_generation_prompt(SPEC)
    assert "Handle a refund request." in prompt
    assert "actions, final_message" in prompt
    assert "Confirm before issuing." in prompt
    assert "Send a report after." in prompt


def test_prompt_states_contract_and_principles():
    prompt = build_generation_prompt(SPEC)
    assert "def verify(evidence: dict) -> dict:" in prompt
    assert "Fail closed" in prompt
    assert "Standard library only" in prompt


def test_prompt_includes_example_evidence_shape():
    prompt = build_generation_prompt(SPEC)
    assert '"final_message": "x"' in prompt


def test_extract_fenced_code():
    text = "Here you go:\n```python\ndef verify(evidence):\n    return {'verdict': 'pass', 'reasons': []}\n```\nDone."
    code = extract_verifier_code(text)
    assert "def verify" in code


def test_extract_bare_code():
    code = extract_verifier_code("def verify(evidence):\n    return {'verdict': 'fail', 'reasons': ['x']}\n")
    assert code.startswith("def verify")


def test_extract_rejects_prose():
    with pytest.raises(GenerationError, match="not valid Python|does not define"):
        extract_verifier_code("Sorry, I cannot write that verifier.")


def test_extract_rejects_code_without_verify():
    with pytest.raises(GenerationError, match="does not define"):
        extract_verifier_code("```python\ndef check(evidence):\n    return {}\n```")


def test_generate_without_llm_cli(monkeypatch):
    monkeypatch.setattr("verifier_forge.generate.shutil.which", lambda _: None)
    with pytest.raises(GenerationError, match="not found"):
        generate_with_llm_cli(SPEC)


def test_generate_with_fake_llm_cli(tmp_path, monkeypatch):
    fake = tmp_path / "llm"
    fake.write_text(
        "#!/bin/sh\ncat > /dev/null\nprintf '```python\\ndef verify(evidence):\\n    return {\"verdict\": \"pass\", \"reasons\": []}\\n```\\n'\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setattr(
        "verifier_forge.generate.shutil.which", lambda _: str(fake)
    )
    code = generate_with_llm_cli(SPEC)
    assert "def verify" in code
