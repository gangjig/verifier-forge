"""End-to-end CLI behavior on the shipped examples."""

from __future__ import annotations

import json
from pathlib import Path

from verifier_forge.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"
SPEC = str(EXAMPLES / "refund-spec.json")
GOOD = str(EXAMPLES / "good_verifier.py")
WEAK = str(EXAMPLES / "weak_verifier.py")


def test_check_good_verifier_exits_0(capsys):
    assert main(["check", SPEC, GOOD]) == 0
    out = capsys.readouterr().out
    assert "STRONG" in out
    assert "6/6" in out


def test_check_weak_verifier_exits_1_and_names_holes(capsys):
    assert main(["check", SPEC, WEAK]) == 1
    out = capsys.readouterr().out
    assert "verifier holes" in out
    assert "shortcut-no-confirmation" in out
    assert "corrupted-transcript" in out


def test_check_json_output(capsys):
    assert main(["check", SPEC, GOOD, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["spec"] == "refund-request"
    assert payload["score"]["grade"] == "strong"
    assert payload["score"]["kappa"] == 1.0
    assert payload["score"]["false_passes"] == []


def test_check_missing_spec_exits_2(capsys):
    assert main(["check", "nope.json", GOOD]) == 2
    assert "error" in capsys.readouterr().err


def test_check_missing_verifier_exits_2(capsys):
    assert main(["check", SPEC, "nope.py"]) == 2


def test_generate_prompt_only(capsys):
    assert main(["generate", SPEC, "--prompt-only"]) == 0
    out = capsys.readouterr().out
    assert "ask_confirmation" in out  # domain rules reach the prompt
    assert "def verify(evidence: dict) -> dict:" in out


def test_generate_writes_file_with_fake_llm(tmp_path, capsys, monkeypatch):
    fake = tmp_path / "llm"
    fake.write_text(
        "#!/bin/sh\ncat > /dev/null\necho '```python'\necho 'def verify(evidence):'\necho '    return {\"verdict\": \"fail\", \"reasons\": [\"stub\"]}'\necho '```'\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    out_file = tmp_path / "gen_verifier.py"
    assert main(["generate", SPEC, "-o", str(out_file)]) == 0
    assert "def verify" in out_file.read_text(encoding="utf-8")
