"""Kappa math, grading, and outcome classification."""

from __future__ import annotations

from verifier_forge.runner import CandidateResult
from verifier_forge.score import cohens_kappa, grade_for, score_results
from verifier_forge.spec import Candidate


def cand(name, kind, expected):
    return Candidate(name=name, kind=kind, evidence={}, expected=expected)


def result(name, verdict, error=None):
    return CandidateResult(name=name, verdict=verdict, reasons=[], error=error)


def test_kappa_perfect_agreement():
    pairs = [("pass", "pass"), ("fail", "fail"), ("pass", "pass")]
    assert cohens_kappa(pairs) == 1.0


def test_kappa_known_value():
    # po = 3/4; marginals: expected pass 1/2, got pass 1/2 -> pe = 1/2
    # kappa = (0.75 - 0.5) / (1 - 0.5) = 0.5
    pairs = [("pass", "pass"), ("pass", "fail"), ("fail", "fail"), ("fail", "fail")]
    assert cohens_kappa(pairs) == 0.5


def test_kappa_all_one_label():
    pairs = [("pass", "pass"), ("pass", "pass")]
    assert cohens_kappa(pairs) == 1.0


def test_kappa_empty():
    assert cohens_kappa([]) == 0.0


def test_grade_thresholds():
    assert grade_for(0.85, 0) == "strong"
    assert grade_for(0.65, 0) == "usable"
    assert grade_for(0.45, 0) == "weak"
    assert grade_for(0.1, 0) == "unreliable"


def test_grade_capped_by_false_pass():
    assert grade_for(0.95, 1) == "weak"
    assert grade_for(0.65, 2) == "weak"
    assert grade_for(0.45, 1) == "weak"  # already weak, stays


def test_score_perfect_verifier():
    candidates = [cand("a", "reference", "pass"), cand("b", "empty", "fail")]
    results = [result("a", "pass"), result("b", "fail")]
    score = score_results(candidates, results)
    assert score.agreement == 1.0
    assert score.kappa == 1.0
    assert score.grade == "strong"
    assert score.per_kind["reference"] == {"total": 1, "matched": 1}


def test_score_false_pass_is_a_hole():
    candidates = [cand("a", "reference", "pass"), cand("b", "shortcut", "fail")]
    results = [result("a", "pass"), result("b", "pass")]
    score = score_results(candidates, results)
    assert score.false_passes == ["b"]
    outcomes = {c.name: c.outcome for c in score.candidates}
    assert outcomes["b"] == "false_pass"


def test_false_pass_caps_an_otherwise_strong_grade():
    # 9/10 agreement, kappa = 0.8 (would grade strong) — but the one
    # miss is a false pass, so the grade is capped at weak.
    candidates = [cand(f"p{i}", "reference", "pass") for i in range(5)]
    candidates += [cand(f"f{i}", "shortcut", "fail") for i in range(5)]
    results = [result(f"p{i}", "pass") for i in range(5)]
    results += [result(f"f{i}", "fail") for i in range(4)]
    results += [result("f4", "pass")]
    score = score_results(candidates, results)
    assert score.kappa == 0.8
    assert score.false_passes == ["f4"]
    assert score.grade == "weak"


def test_score_false_fail():
    candidates = [cand("a", "reference", "pass"), cand("b", "empty", "fail")]
    results = [result("a", "fail"), result("b", "fail")]
    score = score_results(candidates, results)
    assert score.false_fails == ["a"]
    assert score.false_passes == []


def test_score_error_candidate():
    candidates = [cand("a", "reference", "pass"), cand("b", "empty", "fail")]
    results = [result("a", None, error="ValueError: boom"), result("b", "fail")]
    score = score_results(candidates, results)
    assert score.errors == ["a"]
    assert score.matched == 1
    assert score.total == 2
