"""Scoring a verifier against its spec's candidates.

The headline number is **agreement**: how often the verifier's verdict
matches the candidate's known verdict. Because a candidate set is
usually imbalanced (most constructed cases are failures), raw
agreement flatters a verifier that fails everything, so the report
also carries **Cohen's kappa** — agreement corrected for the
agreement two verdicts would reach by chance given their marginals —
the same chance-corrected style of statistic the Veritas paper
reports (κ*).

The dangerous cell gets its own name: a **false pass** — a candidate
known to be bad that the verifier passed. A verifier with a hole
there certifies bad work, so any false pass caps the grade at
``weak`` no matter how high the agreement is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .runner import CandidateResult
from .spec import FAIL, PASS, Candidate

GRADE_STRONG = "strong"
GRADE_USABLE = "usable"
GRADE_WEAK = "weak"
GRADE_UNRELIABLE = "unreliable"

MATCH = "match"
FALSE_PASS = "false_pass"
FALSE_FAIL = "false_fail"
ERROR = "error"


@dataclass(frozen=True)
class ScoredCandidate:
    name: str
    kind: str
    expected: str
    got: str | None
    outcome: str  # MATCH | FALSE_PASS | FALSE_FAIL | ERROR
    reasons: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class VerifierScore:
    total: int
    matched: int
    agreement: float
    kappa: float
    grade: str
    false_passes: list[str]
    false_fails: list[str]
    errors: list[str]
    per_kind: dict[str, dict[str, int]]
    candidates: list[ScoredCandidate]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "matched": self.matched,
            "agreement": round(self.agreement, 3),
            "kappa": round(self.kappa, 3),
            "grade": self.grade,
            "false_passes": self.false_passes,
            "false_fails": self.false_fails,
            "errors": self.errors,
            "per_kind": self.per_kind,
            "candidates": [
                {
                    "name": c.name,
                    "kind": c.kind,
                    "expected": c.expected,
                    "got": c.got,
                    "outcome": c.outcome,
                    "reasons": c.reasons,
                    "error": c.error,
                }
                for c in self.candidates
            ],
        }


def cohens_kappa(pairs: list[tuple[str, str]]) -> float:
    """Cohen's kappa for binary (expected, got) verdict pairs.

    Returns 1.0 for perfect agreement. When the marginals make chance
    agreement certain (pe == 1), returns 1.0 if observed agreement is
    also perfect and 0.0 otherwise.
    """
    if not pairs:
        return 0.0
    n = len(pairs)
    po = sum(1 for expected, got in pairs if expected == got) / n
    pe = 0.0
    for label in (PASS, FAIL):
        p_expected = sum(1 for expected, _ in pairs if expected == label) / n
        p_got = sum(1 for _, got in pairs if got == label) / n
        pe += p_expected * p_got
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1 - pe)


def grade_for(kappa: float, false_passes: int) -> str:
    """Map kappa to a grade; any false pass caps the grade at weak."""
    if kappa >= 0.8:
        grade = GRADE_STRONG
    elif kappa >= 0.6:
        grade = GRADE_USABLE
    elif kappa >= 0.4:
        grade = GRADE_WEAK
    else:
        grade = GRADE_UNRELIABLE
    if false_passes and grade in (GRADE_STRONG, GRADE_USABLE):
        grade = GRADE_WEAK
    return grade


def score_results(
    candidates: list[Candidate], results: list[CandidateResult]
) -> VerifierScore:
    """Combine spec candidates with verifier results into a score."""
    by_name = {result.name: result for result in results}
    scored: list[ScoredCandidate] = []
    per_kind: dict[str, dict[str, int]] = {}
    pairs: list[tuple[str, str]] = []
    false_passes: list[str] = []
    false_fails: list[str] = []
    errors: list[str] = []

    for cand in candidates:
        result = by_name.get(cand.name)
        bucket = per_kind.setdefault(cand.kind, {"total": 0, "matched": 0})
        bucket["total"] += 1
        if result is None or result.error is not None or result.verdict is None:
            outcome = ERROR
            errors.append(cand.name)
            scored.append(
                ScoredCandidate(
                    name=cand.name,
                    kind=cand.kind,
                    expected=cand.expected,
                    got=None,
                    outcome=outcome,
                    error=(result.error if result else "verifier returned no result"),
                )
            )
            continue
        got = result.verdict
        pairs.append((cand.expected, got))
        if got == cand.expected:
            outcome = MATCH
            bucket["matched"] += 1
        elif cand.expected == FAIL and got == PASS:
            outcome = FALSE_PASS
            false_passes.append(cand.name)
        else:
            outcome = FALSE_FAIL
            false_fails.append(cand.name)
        scored.append(
            ScoredCandidate(
                name=cand.name,
                kind=cand.kind,
                expected=cand.expected,
                got=got,
                outcome=outcome,
                reasons=result.reasons,
            )
        )

    total = len(candidates)
    matched = sum(1 for c in scored if c.outcome == MATCH)
    agreement = matched / total if total else 0.0
    kappa = cohens_kappa(pairs)
    return VerifierScore(
        total=total,
        matched=matched,
        agreement=agreement,
        kappa=kappa,
        grade=grade_for(kappa, len(false_passes)),
        false_passes=false_passes,
        false_fails=false_fails,
        errors=errors,
        per_kind=per_kind,
        candidates=scored,
    )
