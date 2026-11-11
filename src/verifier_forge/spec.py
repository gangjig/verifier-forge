"""Task specs: what a verifier is generated from and tested against.

A spec is a JSON document with four parts, following the structure of
the Veritas paper (arXiv:2611.13336):

- ``task`` — what the agent was supposed to do, in plain words.
- ``evidence`` — the *evidence head*: the field names a verifier is
  allowed to see. Nothing else reaches the verifier, so a verdict can
  only rest on declared evidence.
- ``rules`` — the *domain rule library*: requirements the task
  statement leaves implicit ("a refund must be confirmed before it is
  issued"), which the verifier must enforce.
- ``candidates`` — constructed example runs with known-correct
  verdicts, used to self-test the verifier. Kinds are free-form;
  ``reference`` (known-good), ``empty``, ``shortcut`` and ``corrupted``
  are the useful defaults: a verifier that cannot catch a shortcut or
  a corrupted run has a hole exactly where it matters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PASS = "pass"
FAIL = "fail"
VERDICTS = (PASS, FAIL)


class SpecError(ValueError):
    """A task spec could not be read or is invalid."""


@dataclass(frozen=True)
class Candidate:
    name: str
    kind: str
    evidence: dict[str, Any]
    expected: str  # PASS | FAIL


@dataclass(frozen=True)
class Spec:
    name: str
    task: str
    evidence: list[str]
    rules: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)


def load_spec(path: str | Path) -> Spec:
    """Load and validate a task spec from a JSON file."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError(f"cannot read spec file {file_path}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpecError(f"{file_path}: invalid JSON: {exc}") from exc
    return parse_spec(data, where=str(file_path))


def parse_spec(data: Any, where: str = "spec") -> Spec:
    """Validate raw parsed JSON into a :class:`Spec`."""
    if not isinstance(data, dict):
        raise SpecError(f"{where}: top level must be a JSON object")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SpecError(f"{where}: 'name' must be a non-empty string")
    task = data.get("task")
    if not isinstance(task, str) or not task.strip():
        raise SpecError(f"{where}: 'task' must be a non-empty string")

    evidence = data.get("evidence")
    if (
        not isinstance(evidence, list)
        or not evidence
        or not all(isinstance(item, str) and item for item in evidence)
    ):
        raise SpecError(
            f"{where}: 'evidence' must be a non-empty list of field names"
        )

    rules = data.get("rules", [])
    if not isinstance(rules, list) or not all(
        isinstance(item, str) for item in rules
    ):
        raise SpecError(f"{where}: 'rules' must be a list of strings")

    raw_candidates = data.get("candidates")
    if not isinstance(raw_candidates, list) or len(raw_candidates) < 2:
        raise SpecError(
            f"{where}: 'candidates' must be a list of at least two candidates"
        )
    candidates: list[Candidate] = []
    seen_names: set[str] = set()
    for i, raw in enumerate(raw_candidates):
        candidates.append(_parse_candidate(raw, i, evidence, where, seen_names))

    return Spec(
        name=name,
        task=task,
        evidence=list(evidence),
        rules=list(rules),
        candidates=candidates,
    )


def _parse_candidate(
    raw: Any,
    index: int,
    evidence_fields: list[str],
    where: str,
    seen_names: set[str],
) -> Candidate:
    label = f"{where}: candidate {index}"
    if not isinstance(raw, dict):
        raise SpecError(f"{label} is not a JSON object")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SpecError(f"{label}: 'name' must be a non-empty string")
    if name in seen_names:
        raise SpecError(f"{label}: duplicate candidate name {name!r}")
    seen_names.add(name)
    kind = raw.get("kind", "candidate")
    if not isinstance(kind, str) or not kind:
        raise SpecError(f"{label} ({name}): 'kind' must be a non-empty string")
    cand_evidence = raw.get("evidence")
    if not isinstance(cand_evidence, dict):
        raise SpecError(f"{label} ({name}): 'evidence' must be a JSON object")
    undeclared = sorted(set(cand_evidence) - set(evidence_fields))
    if undeclared:
        raise SpecError(
            f"{label} ({name}): evidence fields not declared in the "
            f"evidence head: {', '.join(undeclared)}"
        )
    expected = raw.get("expected")
    if expected not in VERDICTS:
        raise SpecError(
            f"{label} ({name}): 'expected' must be one of {VERDICTS}, "
            f"got {expected!r}"
        )
    return Candidate(name=name, kind=kind, evidence=cand_evidence, expected=expected)
