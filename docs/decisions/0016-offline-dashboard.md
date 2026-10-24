# ADR 0016 — Local saved-trace dashboard

Status: accepted for Phase 22.

Use one generated HTML file with embedded native JavaScript/CSS and validated
saved traces. Reuse the statistical reader for complete-run integrity checks;
replay event snapshots rather than infer unrecorded intermediate states. The
final answer is explicitly labelled as the recorded final outcome at every step.

This satisfies the demo acceptance criteria without a server, additional runtime
dependencies or accidental paid execution. Input text uses textContent, embedded
JSON escapes HTML delimiters and CSP permits only the hashed application script.
Hashes bind the output to its inputs and renderer. Static assets ship in the wheel.

Limits: no live execution or editing, no incomplete-run dashboard (Phase 21 can
inspect interrupted runs), no scalability claim beyond small research artifacts.
The graph describes extracted-model derivability and heuristic beliefs, not
real-world proof or calibrated probability. The UI is not a research contribution.
