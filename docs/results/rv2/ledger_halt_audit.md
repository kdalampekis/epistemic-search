# Spend-ledger halt: audit and clearance

**What happened.** During RV2-D (`rv2-d-retrieval-v1`) one model request failed in flight after
its cost reservation was made (an HTTP-level error; the provider stores no error body). The
ledger's safeguard marked the charge uncertain, retained its **maximum reservation** and halted
the project (`API failure with uncertain charge; maximum reservation retained`). RV2-D stopped
at 46 of 144 planned questions.

**Clearance (performed by the user, 2026-10-30, after I described the action).** The
permission system blocked me from editing the ledger, so the user ran it themselves:

1. Copied `artifacts/research/spending.sqlite3` to `spending.sqlite3.bak`.
2. Set charge `4bc72cbdc7e347419728ad8245c0d951` (run `rv2-d-retrieval-v1`) to `settled`, with
   `actual = reserved = $0.002116375`.
3. Set the project-level `halted` flag to NULL.

I verified afterwards, read-only: `halted` is NULL, 0 pending charges, the charge is settled at
its reserved maximum, no run is halted. Not changed: the $50 project cap, the $5 validation
reserve, every run cap, every other charge, the response cache and the halting logic.

**Worst case.** At most $0.002116375 of provider charge the ledger cannot confirm; it is already
counted as spent in every cumulative figure. The stored usage record of that charge still has
an unknown cost, which affects no total (totals read `actual`).

## Second halt (RV2-E), not cleared

After the clearance above, the ledger halted again during RV2-E with
`Cancelled API attempt; any pending maximum charge remains reserved` (one pending reservation,
run `rv2-e-pivot-v1`). A request was cancelled in flight, most likely by a time limit. RV2-E had
already completed 27 examples, above its committed minimum of 24, so no resumption was needed
and the halt was left in place. Any further paid run needs the same explicit audit and
clearance.
