"""Running a verifier against candidates, in a subprocess.

The verifier is model-written (or hand-written) Python; the forge runs
it in a child process with a timeout so a looping or crashing verifier
cannot hang or kill the tool, and one candidate's exception is
reported as that candidate's error instead of aborting the batch.

This is isolation for robustness, NOT a security sandbox: the child
runs with the caller's permissions. Only run verifiers you have read.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .spec import FAIL, PASS

_RUNNER_SRC = r"""
import importlib.util
import json
import sys

def _load(path):
    spec = importlib.util.spec_from_file_location("candidate_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _normalize(result):
    if isinstance(result, dict):
        verdict = result.get("verdict")
        reasons = result.get("reasons", [])
    elif isinstance(result, bool):
        verdict, reasons = ("pass" if result else "fail"), []
    elif isinstance(result, str):
        verdict, reasons = result, []
    else:
        raise TypeError(f"verify() returned {type(result).__name__}, expected dict")
    if verdict not in ("pass", "fail"):
        raise ValueError(f"verify() returned verdict {verdict!r}, expected 'pass' or 'fail'")
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    return verdict, [str(r) for r in reasons]

def main():
    module = _load(sys.argv[1])
    verify = getattr(module, "verify", None)
    if not callable(verify):
        raise TypeError("verifier module does not define a callable verify()")
    candidates = json.load(sys.stdin)
    out = []
    for cand in candidates:
        try:
            verdict, reasons = _normalize(verify(cand["evidence"]))
            out.append({"name": cand["name"], "verdict": verdict, "reasons": reasons, "error": None})
        except Exception as exc:
            out.append({"name": cand["name"], "verdict": None, "reasons": [], "error": f"{type(exc).__name__}: {exc}"})
    json.dump(out, sys.stdout)

main()
"""


class RunnerError(RuntimeError):
    """The verifier could not be run at all (load failure, timeout)."""


@dataclass(frozen=True)
class CandidateResult:
    name: str
    verdict: str | None  # PASS | FAIL | None when the verifier errored
    reasons: list[str]
    error: str | None


def run_verifier(
    verifier_path: str | Path,
    candidates: list[dict[str, Any]],
    timeout: float = 30.0,
) -> list[CandidateResult]:
    """Run ``verify`` from *verifier_path* over *candidates*.

    *candidates* are ``{"name": ..., "evidence": {...}}`` dicts. A
    verifier that fails to load, or a run that exceeds *timeout*
    seconds, raises :class:`RunnerError`; per-candidate exceptions
    come back as results with ``error`` set.
    """
    path = Path(verifier_path)
    if not path.is_file():
        raise RunnerError(f"verifier file not found: {path}")
    try:
        result = subprocess.run(
            [sys.executable, "-c", _RUNNER_SRC, str(path)],
            input=json.dumps(candidates),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerError(
            f"verifier did not finish within {timeout:g}s "
            "(a looping verifier is a failed verifier)"
        ) from exc
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-3:])
        raise RunnerError(f"verifier failed to load or run:\n{tail}")
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RunnerError(f"verifier runner returned invalid output: {exc}") from exc
    return [
        CandidateResult(
            name=item["name"],
            verdict=item["verdict"],
            reasons=list(item.get("reasons", [])),
            error=item.get("error"),
        )
        for item in raw
    ]


__all__ = ["CandidateResult", "RunnerError", "run_verifier", "PASS", "FAIL"]
