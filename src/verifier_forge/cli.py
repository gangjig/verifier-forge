"""Command-line interface: generate a verifier, or check one."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .generate import GenerationError, build_generation_prompt, generate_with_llm_cli
from .report import render_json, render_text
from .runner import RunnerError, run_verifier
from .score import GRADE_STRONG, GRADE_USABLE, score_results
from .spec import SpecError, load_spec

EXIT_OK = 0
EXIT_WEAK = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verifier-forge",
        description=(
            "Generate a verifier for an agent task from a spec "
            "(evidence head + domain rules), then self-test it against "
            "constructed candidates with known verdicts and grade "
            "the agreement."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"verifier-forge {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser(
        "generate", help="generate a verifier from a spec via the llm CLI"
    )
    gen.add_argument("spec", help="task spec JSON file")
    gen.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="write the verifier code to FILE (default: print to stdout)",
    )
    gen.add_argument(
        "-m", "--model", help="model for the llm CLI (default: llm's own default)"
    )
    gen.add_argument(
        "--prompt-only",
        action="store_true",
        help="print the generation prompt instead of calling a model",
    )

    check = sub.add_parser(
        "check", help="self-test a verifier against its spec's candidates"
    )
    check.add_argument("spec", help="task spec JSON file")
    check.add_argument("verifier", help="verifier Python file (defines verify())")
    check.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        metavar="S",
        help="seconds the verifier may take over all candidates (default: 30)",
    )
    check.add_argument(
        "--json", action="store_true", help="print the report as JSON"
    )
    return parser


def _cmd_generate(args: argparse.Namespace) -> int:
    try:
        spec = load_spec(args.spec)
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if args.prompt_only:
        print(build_generation_prompt(spec))
        return EXIT_OK
    try:
        code = generate_with_llm_cli(spec, model=args.model)
    except GenerationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if args.output:
        Path(args.output).write_text(code, encoding="utf-8")
        print(f"wrote verifier to {args.output}", file=sys.stderr)
    else:
        print(code, end="")
    return EXIT_OK


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        spec = load_spec(args.spec)
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    payload = [
        {"name": cand.name, "evidence": cand.evidence} for cand in spec.candidates
    ]
    try:
        results = run_verifier(args.verifier, payload, timeout=args.timeout)
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    score = score_results(spec.candidates, results)
    print(
        render_json(spec, args.verifier, score)
        if args.json
        else render_text(spec, args.verifier, score)
    )
    return EXIT_OK if score.grade in (GRADE_STRONG, GRADE_USABLE) else EXIT_WEAK


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        return _cmd_generate(args)
    return _cmd_check(args)
