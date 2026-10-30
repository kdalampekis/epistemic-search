# Ledger halt audit before RV2-F

Performed before any RV2-F model call. Everything below was read from the ledger read-only.

**Halt reason (project level):** `Cancelled API attempt; any pending maximum charge remains reserved`.
No individual run is halted.

**Pending reservation (exactly one):**

| Field | Value |
| --- | --- |
| Charge id | `9ed25a3b9123408abcd21f1ef401c027` |
| Run | `rv2-e-pivot-v1` (stage `development`, `gpt-6-luna`, medium) |
| Reserved maximum | **$0.00210525** |
| Actual | none recorded |
| Usage record | `api_calls: 2`, `preflight_calls: 1`, `model_calls: 1`: the token pre-count ran and the generation request was **sent**, then the attempt was cancelled before a response was recorded |

**Is the charge settled, cancelled or uncertain?** Genuinely uncertain. A request that was
cancelled client-side after being sent may or may not have been billed by the provider, and the
ledger stores no response for it. The ledger therefore keeps its maximum reservation, which can
only overstate spend. Totals already include it: project $0.396241 of $50.

**Likely cause (not proven).** The only way this halt is raised is `asyncio.CancelledError`
inside the provider call, which means the process or task was cancelled externally, not that the
API rejected the request. RV2-E's detached shell job stopped at about the time my 30-minute
progress monitor expired, which is consistent with a signal reaching the job. It is a
hypothesis. Mitigation for RV2-F: run paid steps as managed background tasks, not detached
shell chains, and avoid progress monitors that can kill them.

**Policy check.** The ledger's rule is "retain the maximum reservation; audit required". Settling
this one charge at its maximum and lifting the project flag keeps that guarantee: no cap, run
reservation, other charge, cache entry or halting logic changes, and no historical record is
deleted. The clearance is the same one used after the RV2-D halt (see
[../ledger_halt_audit.md](../ledger_halt_audit.md)).

## Clearance

Performed 2026-10-30, as instructed, after the audit above:

1. Backed up the ledger (`artifacts/research/spending.sqlite3.pre-rv2f-20261030T223742Z.bak`,
   git-ignored).
2. Settled charge `9ed25a3b9123408abcd21f1ef401c027` at its reserved maximum, **$0.00210525**
   (`actual = reserved`; the usage record's cost set to the same value).
3. Cleared the project-level halt flag.

Verified afterwards, read-only: `halted` is NULL, 0 pending charges, no run halted. Project
total unchanged at $0.396241 (the reservation was already counted). Not changed: the $50
project cap, the $5 validation reserve, every run cap, every other charge, the response cache,
and the halting logic; no record was deleted.

Worst case: at most $0.00210525 of provider charge the ledger cannot confirm.
