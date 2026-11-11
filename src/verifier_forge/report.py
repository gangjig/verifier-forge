"""Rendering a verifier quality report as text or JSON."""

from __future__ import annotations

import json

from .score import (
    ERROR,
    FALSE_FAIL,
    FALSE_PASS,
    GRADE_STRONG,
    GRADE_USABLE,
    VerifierScore,
)
from .spec import Spec

_OUTCOME_MARKS = {
    "match": "ok",
    FALSE_PASS: "FALSE PASS",
    FALSE_FAIL: "false fail",
    ERROR: "error",
}


def render_json(spec: Spec, verifier_path: str, score: VerifierScore) -> str:
    payload = {
        "spec": spec.name,
        "verifier": verifier_path,
        "score": score.to_dict(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_text(spec: Spec, verifier_path: str, score: VerifierScore) -> str:
    lines: list[str] = ["verifier-forge report", "=" * 21]
    lines.append(f"spec:     {spec.name}")
    lines.append(f"verifier: {verifier_path}")
    lines.append("")
    lines.append(
        f"agreement: {score.matched}/{score.total} ({score.agreement:.0%})"
    )
    lines.append(f"kappa:     {score.kappa:.2f} (chance-corrected agreement)")
    lines.append(f"grade:     {score.grade.upper()}")
    lines.append("")
    lines.append("candidates:")
    for cand in score.candidates:
        got = cand.got if cand.got is not None else "—"
        line = (
            f"  [{_OUTCOME_MARKS[cand.outcome]:>10}] {cand.name} "
            f"({cand.kind}): expected {cand.expected}, got {got}"
        )
        lines.append(line)
        if cand.error:
            lines.append(f"               error: {cand.error}")
    lines.append("")
    lines.append("by kind:")
    for kind, bucket in score.per_kind.items():
        lines.append(f"  {kind}: {bucket['matched']}/{bucket['total']} matched")
    if score.false_passes:
        lines.append("")
        lines.append(
            "verifier holes — known-bad candidates the verifier PASSED: "
            + ", ".join(score.false_passes)
        )
    if score.false_fails:
        lines.append(
            "over-strict — known-good candidates the verifier failed: "
            + ", ".join(score.false_fails)
        )
    if score.errors:
        lines.append("errored candidates: " + ", ".join(score.errors))
    lines.append("")
    if score.grade in (GRADE_STRONG, GRADE_USABLE):
        lines.append(
            f"verdict: verifier is {score.grade} on this candidate set "
            "(agreement on constructed candidates is evidence, not proof — "
            "see Limitations in the README)"
        )
    else:
        lines.append(
            f"verdict: verifier is {score.grade} on this candidate set — "
            "do not trust it to grade real runs yet"
        )
    return "\n".join(lines)
