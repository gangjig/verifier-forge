# Changelog

## 0.1.0 — 2026-11-11

- Initial release. `verifier-forge generate` builds a verifier
  generation prompt from a JSON task spec — task description,
  evidence head, domain rule library, authoring principles — and
  either prints it (`--prompt-only`) or sends it through Simon
  Willison's `llm` CLI (`--no-log`), extracting and validating the
  returned `verify()` module. `verifier-forge check` runs a verifier
  against the spec's constructed candidates (reference / empty /
  shortcut / corrupted runs with known verdicts) in a subprocess with
  a timeout, and grades it: raw agreement, Cohen's kappa, per-kind
  breakdown, false passes named as verifier holes, and a
  strong/usable/weak/unreliable grade with any false pass capping
  the grade at weak. Text and JSON reports; exit 0 only for
  strong/usable, so the check works as a CI gate for verifiers.
  Ships a refund-request example spec with a rule-following verifier
  (grades strong) and a naive one (grades unreliable, three holes).
  Structure and grading follow Veritas (arXiv:2611.13336):
  https://arxiv.org/abs/2611.13336
