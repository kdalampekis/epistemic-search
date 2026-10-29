# Superseded RV2-B probe (code `epistemic-search-v1.1`)

Kept, not deleted. This 2-arm probe on one EntailmentBank example ran before the no-progress
guard's state comparison was corrected (see `docs/experiments/RV2_V1_1_FREEZE.md`, section
"v1.1.1"). Under v1.1 the guard did not fire (evidence ids hash the query, so re-reading the
same span looked like a changed state) and the oracle arm ran three searches before the
budget stopped it. Outcomes (answer / abstain, blocker = removed leaf) were the same as under
v1.1.1; only the search count and the stop reason differ. The generated arm failed
structural validation on this example (a `claim_id` on the CONCLUSION node). The estimate was
re-measured under v1.1.1 in `../rv2_b/`.
