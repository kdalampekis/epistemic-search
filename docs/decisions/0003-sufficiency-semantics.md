# ADR 0003 — Conservative four-state sufficiency semantics

Status: accepted for Phase 7. These are explicit engineering semantics over the
extracted model, not a theorem about real-world truth or a calibration guarantee.

NOT swaps SUPPORTED/CONTRADICTED and preserves UNKNOWN/MIXED. AND is CONTRADICTED
if any child is CONTRADICTED; otherwise MIXED if any is MIXED; otherwise UNKNOWN
if any is UNKNOWN; otherwise SUPPORTED. OR is the dual: a SUPPORTED alternative
settles it, otherwise MIXED takes precedence over UNKNOWN, then CONTRADICTED.
CONCLUSION forwards its one child. Missing beliefs are UNKNOWN. Only an entirely
SUPPORTED root licenses `sufficient=True`. No rule derives arbitrary conclusions
from contradictions or turns missing evidence into refutation.

Blockers are claim obligations that must change to establish a supported root.
They may include a currently contradicted claim, not only unknown claims. NOT
reverses the desired stance. AND combines required child repair sets; OR offers
alternatives (dually when seeking refutation). Superset repair sets are removed;
the smallest remaining set, with stable ID tie-breaking, is the selected frontier.
Each obligation includes its required stance. Complete satisfying assignments are
combined before removing currently satisfied obligations, so a repair cannot break
an already-supported sibling. Opposite requirements on the same claim are rejected;
`A AND NOT A` has no repair frontier under any current belief state.
Shared premises are considered globally. All inclusion-minimal alternatives remain
available. Exceeding the configured enumeration bound raises an error rather than
silently presenting an incomplete frontier as exact. These are structural repair
obligations, not evidence that new retrieval can actually repair a premise.
