# verifier-forge

Generate a verifier for an agent task — then grade the verifier before you trust it.

Self-improvement loops, eval harnesses, and acceptance checks all stand on one component: the **verifier** that decides whether a run was good. Most real tasks don't have one, and hand-writing one is slow, so teams either skip verification or trust a verifier nobody ever tested. verifier-forge attacks both halves:

1. **Generate** — from a small task spec (what the agent had to do, an *evidence head* naming the only fields the verifier may see, and a *domain rule library* of the requirements the task statement leaves implicit), it builds a generation prompt carrying those three pieces plus authoring principles, and produces a Python verifier via Simon Willison's `llm` CLI — or prints the prompt for you to paste into any model.
2. **Check** — the spec also carries **constructed candidates**: example runs with known-correct verdicts (a reference run, an empty run, runs that take shortcuts, a corrupted run). The forge runs the verifier against all of them and reports agreement, chance-corrected agreement (Cohen's kappa), a per-kind breakdown, and — most important — the **verifier holes**: known-bad candidates the verifier passed. Any false pass caps the grade at `weak`, no matter how high the agreement: a verifier that certifies bad work is worse than no verifier.

## Credits / motivation

The spec structure (evidence head + domain rule library + authoring principles) and the chance-corrected agreement grading follow **Veritas** (arXiv:2611.13336), which generates verifiers with a coding agent and evaluates them by agreement with official verdicts across execution-based benchmarks: https://arxiv.org/abs/2611.13336

## Install

```bash
pip install -e .   # from a clone; Python 3.10+, no runtime dependencies
```

`generate` additionally needs the `llm` CLI on PATH (`pip install llm`) — or use `--prompt-only` and any model you like.

## The spec

A spec is one JSON file:

```json
{
  "name": "refund-request",
  "task": "The agent handles a customer refund request...",
  "evidence": ["actions", "final_message"],
  "rules": [
    "A refund must be confirmed with the customer before it is issued...",
    "After a refund is issued, a summary report must be sent..."
  ],
  "candidates": [
    {"name": "reference-full-flow", "kind": "reference",
     "evidence": {"actions": ["ask_confirmation", "issue_refund", "send_report"],
                  "final_message": "..."},
     "expected": "pass"},
    {"name": "shortcut-no-confirmation", "kind": "shortcut",
     "evidence": {"actions": ["issue_refund", "send_report"],
                  "final_message": "Refund issued."},
     "expected": "fail"}
  ]
}
```

- `evidence` is the evidence head: candidate evidence may not use undeclared fields (the loader rejects them), because a verifier that reads undeclared evidence is grading on things you didn't agree it could see.
- `candidates` need at least two entries with unique names and `expected` of `pass` or `fail`. `kind` is free-form; `reference` / `empty` / `shortcut` / `corrupted` are the useful defaults. Construct candidates that probe the rules — especially the shortcuts a lazy agent (or a lazy verifier) would take.
- See `examples/refund-spec.json` for a complete spec.

## Usage

```bash
# See the generation prompt for a spec (paste it into any model)
verifier-forge generate examples/refund-spec.json --prompt-only

# Generate a verifier with your llm CLI setup
verifier-forge generate examples/refund-spec.json -m gpt-5 -o my_verifier.py

# Self-test a verifier (hand-written or generated) against the spec
verifier-forge check examples/refund-spec.json examples/good_verifier.py

# Machine-readable report
verifier-forge check examples/refund-spec.json examples/weak_verifier.py --json
```

Example output (the deliberately weak verifier in `examples/`, which only checks that the agent said *something*):

```
agreement: 3/6 (50%)
kappa:     0.18 (chance-corrected agreement)
grade:     UNRELIABLE

candidates:
  [        ok] reference-full-flow (reference): expected pass, got pass
  ...
  [FALSE PASS] shortcut-no-confirmation (shortcut): expected fail, got pass
  [FALSE PASS] shortcut-no-report (shortcut): expected fail, got pass
  [FALSE PASS] corrupted-transcript (corrupted): expected fail, got pass

verifier holes — known-bad candidates the verifier PASSED: shortcut-no-confirmation, shortcut-no-report, corrupted-transcript
```

The hand-written `examples/good_verifier.py`, which actually enforces the rules, grades `STRONG` at 6/6, kappa 1.00.

## How it works

- **Generation prompt.** Task + evidence head + one candidate's evidence as a shape example + the numbered rule library + authoring principles (decide from evidence only; fail closed when evidence for a rule is missing; report every violation; an outcome without the required steps is a shortcut, not a success; be deterministic). The model's reply is unwrapped from its code fence and must parse as Python defining `verify()` — anything else is an error, never a silently saved file. The `llm` call passes `--no-log`, so spec material doesn't land in your llm logs.
- **Verifier contract.** A verifier is a Python module defining `verify(evidence: dict)`. It should return `{"verdict": "pass" | "fail", "reasons": [str, ...]}`; bare `"pass"`/`"fail"` strings and booleans are also accepted, because generated code varies.
- **Runner.** The verifier runs in a subprocess with a timeout (default 30s for the whole candidate set): a looping verifier is a failed verifier, and one candidate's exception is reported as that candidate's error instead of aborting the batch.
- **Scoring.** Agreement is the raw match rate. Kappa corrects it for chance agreement given the verdict marginals — a candidate set of mostly failures makes a fail-everything verifier look good on agreement alone. Grades: kappa ≥ 0.8 `strong`, ≥ 0.6 `usable`, ≥ 0.4 `weak`, below that `unreliable` — and any false pass caps the grade at `weak`. Candidates the verifier errored on count in the total but earn no kappa pair.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | `check`: the verifier graded `strong` or `usable`. `generate`: success |
| 1 | `check`: the verifier graded `weak` or `unreliable` |
| 2 | Usage/spec/runner/generation error (missing file, invalid spec, verifier failed to load, `llm` CLI missing or failing) |

Exit 1 makes `check` usable as a gate: a verifier that regresses below `usable` on its candidate set fails CI before it grades real runs.

## Limitations

verifier-forge is honest about what it cannot do:

- **Agreement on constructed candidates is evidence, not proof.** Your candidates cover the failure modes you imagined. A verifier can ace the set and still have holes on real outputs — grow the candidate set from every real mis-grade you catch, the way you'd grow a test suite from bugs.
- **The candidates' verdicts are yours.** If a candidate's `expected` is wrong, the forge will dutifully grade a correct verifier down. The spec is a claim about the task; argue with it there first.
- **The runner is not a sandbox.** The verifier runs in a subprocess with a timeout but with your permissions — model-written code included. Read a generated verifier before you check it, the way you'd read any generated code before running it.
- **Kappa on small sets is coarse.** With a handful of candidates, one disagreement swings kappa a lot. Treat the grade as a smoke alarm, not a measurement; the per-candidate listing is the real report.
- **Generation quality is the model's.** The prompt structure (evidence head, rules, principles) is the part this tool contributes; a weak model will still write a weak verifier. That's what `check` is for.

## Development

```bash
python3 -m pytest -q
```

## Build your own

Prompt an LLM with: "Build a small Python CLI called verifier-forge that helps me create and validate verifiers for agent tasks. It reads a JSON task spec containing a task description, an evidence head (the list of evidence field names a verifier is allowed to see — candidate evidence using undeclared fields must be rejected), a list of domain rules the task statement leaves implicit, and at least two constructed candidate runs, each with a name, a free-form kind (reference, empty, shortcut, corrupted), an evidence object, and an expected pass/fail verdict. One subcommand builds a generation prompt from the spec — task, evidence head, one candidate's evidence as a shape example, the numbered rules, and authoring principles (decide from evidence only, fail closed when evidence is missing, report every violation, an outcome without the required steps is a fail, be deterministic) — and either prints it or sends it to Simon Willison's llm CLI (with --no-log), extracting the returned Python code from its fence and validating that it parses and defines verify(). The other subcommand runs a verifier module (verify(evidence) returning a verdict dict; bare strings and booleans also accepted) against all candidates in a subprocess with a timeout, classifying each result as match, false pass, false fail, or error, then reports raw agreement, Cohen's kappa against the expected verdicts, a per-kind breakdown, the list of false passes (named verifier holes), and a grade (strong/usable/weak/unreliable by kappa thresholds, with any false pass capping the grade at weak), as text or JSON, with exit code 0 only for strong/usable. Standard library only, with a pytest suite and a worked refund-request example including a rule-following verifier that grades strong and a naive one that grades unreliable with named holes."

## License

MIT
