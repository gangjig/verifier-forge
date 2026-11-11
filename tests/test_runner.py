"""Subprocess runner: normalization, isolation, failure modes."""

from __future__ import annotations

import pytest

from verifier_forge.runner import RunnerError, run_verifier

CANDIDATES = [
    {"name": "a", "evidence": {"x": 1}},
    {"name": "b", "evidence": {"x": 2}},
]


def write_verifier(tmp_path, body):
    path = tmp_path / "verifier.py"
    path.write_text(body, encoding="utf-8")
    return path


def test_runs_dict_verdicts(tmp_path):
    path = write_verifier(
        tmp_path,
        "def verify(evidence):\n"
        "    ok = evidence['x'] == 1\n"
        "    return {'verdict': 'pass' if ok else 'fail', 'reasons': []}\n",
    )
    results = run_verifier(path, CANDIDATES)
    assert [r.verdict for r in results] == ["pass", "fail"]
    assert all(r.error is None for r in results)


def test_accepts_bool_and_string_returns(tmp_path):
    path = write_verifier(
        tmp_path,
        "def verify(evidence):\n"
        "    return True if evidence['x'] == 1 else 'fail'\n",
    )
    results = run_verifier(path, CANDIDATES)
    assert [r.verdict for r in results] == ["pass", "fail"]


def test_per_candidate_exception_is_reported_not_raised(tmp_path):
    path = write_verifier(
        tmp_path,
        "def verify(evidence):\n"
        "    if evidence['x'] == 2:\n"
        "        raise ValueError('boom')\n"
        "    return {'verdict': 'pass', 'reasons': []}\n",
    )
    results = run_verifier(path, CANDIDATES)
    assert results[0].error is None
    assert "ValueError: boom" in (results[1].error or "")


def test_bad_verdict_value_is_an_error(tmp_path):
    path = write_verifier(
        tmp_path, "def verify(evidence):\n    return {'verdict': 'maybe'}\n"
    )
    results = run_verifier(path, CANDIDATES)
    assert all(r.error for r in results)


def test_missing_verify_fails_the_run(tmp_path):
    path = write_verifier(tmp_path, "def check(evidence):\n    return {}\n")
    with pytest.raises(RunnerError, match="failed to load or run"):
        run_verifier(path, CANDIDATES)


def test_syntax_error_fails_the_run(tmp_path):
    path = write_verifier(tmp_path, "def verify(:\n")
    with pytest.raises(RunnerError):
        run_verifier(path, CANDIDATES)


def test_missing_file(tmp_path):
    with pytest.raises(RunnerError, match="not found"):
        run_verifier(tmp_path / "nope.py", CANDIDATES)


def test_timeout(tmp_path):
    path = write_verifier(
        tmp_path,
        "import time\ndef verify(evidence):\n    time.sleep(30)\n    return {'verdict': 'pass'}\n",
    )
    with pytest.raises(RunnerError, match="did not finish"):
        run_verifier(path, CANDIDATES, timeout=1.0)
