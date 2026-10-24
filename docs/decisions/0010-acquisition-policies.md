# ADR 0010 — Shared acquisition constraints, configurable ranking

Status: accepted for Phase 16.

All four policies use `choose_action`, the same sufficiency result, the same
selected minimal repair frontier, the same signed stance obligations and the
same acquisition/provider budget guards. Existing conflict/contrary-state
priority is preserved. Only ranking within that candidate set changes.

- `importance`: highest claim importance, then stable claim ID. This remains
  the default and preserves the historical action policy.
- `random`: highest independently drawn pseudorandom score. The local RNG seed
  derives from run seed, query ID and acquisition round; candidates are sorted
  before drawing. Case/input order does not change a case's selection.
- `uncertainty`: highest existing heuristic uncertainty, then claim ID.
- `voi`: importance × uncertainty × criticality × retrievability / cost.

Criticality is the fraction of enumerated minimal repair alternatives containing
the claim. Retrievability and positive acquisition cost come from configured
estimates, with declared provenance and units. Defaults are uniform, explicitly
uninformative estimates. Unknown claims, nonfinite/zero/negative costs and invalid
scores are rejected. Costs are ranking estimates, not reservations or actual
charges; they never substitute for provider token accounting or the spending
ledger. All paid calls still use exact input preflight and monetary reservations.

This VOI formula is a **heuristic priority**, not measured expected information
gain, a calibrated probability or an optimal policy. Uncertainty is currently
uncalibrated. Selecting only within the preexisting repair frontier does not
optimize over all repair plans. An opposed pure belief can have zero uncertainty;
an all-zero rank still selects a candidate rather than inventing sufficiency or
abstention. No new value threshold changes stopping behavior.

Each acquisition Decision records policy, seed/round/context ID, all candidate
scores, criticalities, uncertainties, estimates, units and estimate provenance.
The existing target/required-stance query trace completes the audit trail.

`RunConfig.controller` is omitted from serialization only when exactly equal to
the historical defaults. This preserves existing Phase 12 config/cache hashes
and avoids invalidating paid outputs. Any changed controller setting is serialized
and hashed. Tests cover default and nondefault round trips; the saved Phase 14
report was reproduced byte-for-byte after this change.

Example (the controller applies to the full epistemic method):

```yaml
controller:
  policy: voi
  cost_unit: relative_work
  estimate_provenance: uniform-uninformative-default-v1
  default_estimate:
    retrievability: 1.0
    cost: 1.0
  estimates: {}
```

Per-claim overrides use stable canonical claim IDs. They must come from a frozen
estimation protocol, never test answer labels. The current implementation does
not learn retrievability/cost from outcomes. Offline checks establish execution,
accounting and selection semantics only; no efficiency gain is claimed.
