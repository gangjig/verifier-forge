"""Generating a verifier from a spec.

The generation prompt is the product: it hands the model the task, the
evidence head (the only fields the verifier may read), the domain rule
library, and a short list of authoring principles, and asks for one
Python module defining ``verify(evidence)``. Two ways to run it:

- ``--prompt-only`` prints the prompt; paste it into any model.
- the default backend shells out to Simon Willison's ``llm`` CLI
  (``llm`` on PATH), so the model choice stays with the user's own
  llm setup. The call passes ``--no-log``: a spec can quote sensitive
  task material, and it should not land in the caller's llm logs.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess

from .spec import Spec

AUTHORING_PRINCIPLES = [
    "Decide from the evidence only. Never assume a fact that is not in "
    "the evidence, and never use outside knowledge about the task.",
    "Fail closed: if the evidence needed to check a rule is missing, "
    "the verdict is fail, with a reason naming the missing evidence.",
    "Check every rule, and report every violation found — not just "
    "the first. Reasons must name the rule or the missing step.",
    "An outcome achieved without the required steps is a fail: a "
    "refund that appears without a prior confirmation is a shortcut, "
    "not a success.",
    "Be deterministic: same evidence, same verdict. No randomness, "
    "no clocks, no network, no file access.",
]


class GenerationError(RuntimeError):
    """Verifier generation or code extraction failed."""


def build_generation_prompt(spec: Spec) -> str:
    """Build the full generation prompt for a spec."""
    rules_block = (
        "\n".join(f"{i}. {rule}" for i, rule in enumerate(spec.rules, start=1))
        if spec.rules
        else "(no domain rules beyond the task statement)"
    )
    principles_block = "\n".join(f"- {p}" for p in AUTHORING_PRINCIPLES)
    example_evidence = (
        json.dumps(spec.candidates[0].evidence, indent=2, ensure_ascii=False)
        if spec.candidates
        else "{}"
    )
    return f"""Write a verifier for an agent task.

A verifier is a Python module that judges one finished run of the task
from recorded evidence. Output ONLY the Python code, in a single
```python fenced block, with no explanation before or after.

Contract:
- Define exactly one entry point: `def verify(evidence: dict) -> dict:`
- Return {{"verdict": "pass" | "fail", "reasons": [str, ...]}}.
  On "pass", reasons may be empty. On "fail", give at least one reason.
- Standard library only. No imports beyond the standard library.

The task:
{spec.task}

Evidence head — the verifier may read ONLY these fields of the
evidence dict:
{", ".join(spec.evidence)}

Example evidence (one recorded run; values show the shape, not the
verdict):
{example_evidence}

Domain rules — requirements the task statement leaves implicit.
Enforce every one:
{rules_block}

Authoring principles:
{principles_block}
"""


_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_verifier_code(text: str) -> str:
    """Extract and validate verifier code from a model response.

    Accepts a ```python fenced block, or a bare response that is
    itself valid Python. The code must define a top-level ``verify``
    function; anything else raises :class:`GenerationError`.
    """
    match = _FENCE_RE.search(text)
    code = match.group(1) if match else text
    code = code.strip() + "\n"
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise GenerationError(f"extracted code is not valid Python: {exc}") from exc
    if not any(
        isinstance(node, ast.FunctionDef) and node.name == "verify"
        for node in tree.body
    ):
        raise GenerationError("extracted code does not define a verify() function")
    return code


def generate_with_llm_cli(spec: Spec, model: str | None = None) -> str:
    """Generate verifier code via the ``llm`` CLI; return the code.

    Raises :class:`GenerationError` when the CLI is missing or fails,
    or when its output contains no usable verifier.
    """
    llm = shutil.which("llm")
    if llm is None:
        raise GenerationError(
            "the 'llm' CLI was not found on PATH; install Simon "
            "Willison's llm (pip install llm) or use --prompt-only and "
            "paste the prompt into a model yourself"
        )
    command = [llm, "--no-log"]
    if model:
        command += ["-m", model]
    try:
        result = subprocess.run(
            command,
            input=build_generation_prompt(spec),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        raise GenerationError("the llm CLI did not answer within 600s") from exc
    if result.returncode != 0:
        tail = result.stderr.strip().splitlines()[-1:] or ["(no stderr)"]
        raise GenerationError(f"the llm CLI failed: {tail[0]}")
    return extract_verifier_code(result.stdout)
