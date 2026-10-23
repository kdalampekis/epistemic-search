# Phase 6 — Belief state v1

## Implementation and decisions

Each claim retains independent maximum SUPPORT and CONTRADICT stance scores.
Both reaching the configured positive threshold gives MIXED; only one gives
SUPPORTED or CONTRADICTED; neither gives UNKNOWN. No evidence and neutral-only
evidence remain UNKNOWN. The heuristic uncertainty is `1 - abs(support - contradiction)`;
it represents lack of a decisive margin, not a probability. Every result has
`calibrated=False` and preserves all contributing evidence IDs, including neutral.

Max-per-stance is intentionally conservative: repeating a document cannot inflate
support and conflicting evidence never cancels out. It also does not reward
independent corroboration. Calibration/alternative aggregation belong to Phase 15.
The default threshold 0.5 is a configurable engineering default, not test-set tuned.

## Tests and acceptance

Required synthetic cases cover no evidence, support only, contradiction only,
mixed, neutral, weak evidence and duplicates. Additional tests cover ordering,
threshold boundaries, unknown claim references and invalid thresholds.
Full suite: 97 tests; locked install, lint/format, strict mypy, pytest and build.

## Limitations and next dependencies

Scores inherit extraction errors, do not establish truth, and are not calibrated.
The conservative maximum deliberately discards corroboration strength. No formal
sufficiency or controller is included. Next: **Phase 7 — Structured sufficiency
reasoner**, with explicit UNKNOWN propagation, blockers and derivation trace.
