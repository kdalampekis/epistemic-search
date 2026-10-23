"""Project-wide cost reservations and exact-request reuse, without credentials."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

from epistemic_search.config import ExperimentSpend
from epistemic_search.models import Usage
from epistemic_search.providers import ModelResponse, ProviderBudgetExceeded


class SpendStopped(ProviderBudgetExceeded):
    def __init__(self, reason: str) -> None:
        super().__init__(reason, Usage(cost_usd=Decimal(0)), usage_complete=True)


class SpendLedger:
    """Serialized generations; an interrupted request retains its maximum charge.

    Reuse this file across all project phases. Run IDs and caps are immutable.
    Cache stores outputs and usage, never credentials or request headers.
    """

    def __init__(self, settings: ExperimentSpend) -> None:
        self.settings = settings.model_copy(deep=True)
        settings.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS project (id INTEGER PRIMARY KEY, "
                "policy TEXT, halted TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, policy TEXT, halted TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS charges (id TEXT PRIMARY KEY, run_id TEXT, "
                "stage TEXT, model TEXT, effort TEXT, reserved TEXT, actual TEXT, "
                "state TEXT, usage TEXT)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, response TEXT)")
            policy = json.dumps(
                {
                    k: str(getattr(settings, k))
                    for k in ("total_usd", "prior_spend_usd", "validation_reserve_usd")
                },
                sort_keys=True,
            )
            row = db.execute("SELECT policy FROM project WHERE id=1").fetchone()
            if row is None:
                db.execute("INSERT INTO project VALUES (1, ?, NULL)", (policy,))
            elif row[0] != policy:
                raise ValueError("Project budget policy differs from the persistent ledger")
            run_policy = json.dumps([str(settings.run_usd), settings.stage])
            row = db.execute("SELECT policy FROM runs WHERE id=?", (settings.run_id,)).fetchone()
            if row is None:
                db.execute("INSERT INTO runs VALUES (?, ?, NULL)", (settings.run_id, run_policy))
            elif row[0] != run_policy:
                raise ValueError("Existing run budget/stage cannot change")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.settings.ledger_path, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def stop_reason(self) -> str | None:
        with self.transaction() as db:
            (reason,) = db.execute("SELECT halted FROM project WHERE id=1").fetchone()
            if reason:
                return str(reason)
            if db.execute("SELECT 1 FROM charges WHERE state='pending'").fetchone():
                return "Unsettled API attempt; maximum charge retained, audit required"
            (reason,) = db.execute(
                "SELECT halted FROM runs WHERE id=?", (self.settings.run_id,)
            ).fetchone()
            return str(reason) if reason else None

    def halt(self, reason: str) -> None:
        with self.transaction() as db:
            db.execute("UPDATE project SET halted=COALESCE(halted, ?) WHERE id=1", (reason,))

    def reserve(self, maximum: Decimal, attempt: Usage, model: str, effort: str) -> str:
        if not maximum.is_finite() or maximum < 0:
            raise ValueError("Invalid cost reservation")
        identifier, reason = uuid4().hex, None
        with self.transaction() as db:
            (halted,) = db.execute("SELECT halted FROM project WHERE id=1").fetchone()
            (run_halted,) = db.execute(
                "SELECT halted FROM runs WHERE id=?", (self.settings.run_id,)
            ).fetchone()
            rows = db.execute(
                "SELECT run_id, stage, reserved, actual, state FROM charges"
            ).fetchall()
            total = self.settings.prior_spend_usd + sum(
                (Decimal(a if a is not None else r) for _, _, r, a, _ in rows), Decimal(0)
            )
            run_total = sum(
                (
                    Decimal(a if a is not None else r)
                    for run, _, r, a, _ in rows
                    if run == self.settings.run_id
                ),
                Decimal(0),
            )
            primary = self.settings.prior_spend_usd + sum(
                (
                    Decimal(a if a is not None else r)
                    for _, stage, r, a, _ in rows
                    if stage != "validation"
                ),
                Decimal(0),
            )
            validation_total = total - primary
            if halted or run_halted:
                reason = str(halted or run_halted)
            elif any(state == "pending" for _, _, _, _, state in rows):
                reason = "Unsettled or concurrent API attempt; no further generation allowed"
            elif total + maximum > self.settings.total_usd:
                reason = "Project cost cap: next maximum charge exceeds remaining funds"
            elif (
                self.settings.stage != "validation"
                and primary + maximum
                > self.settings.total_usd - self.settings.validation_reserve_usd
            ):
                reason = "Primary budget exhausted; final validation reserve protected"
            elif (
                self.settings.stage == "validation"
                and validation_total + maximum > self.settings.validation_reserve_usd
            ):
                reason = "Final validation cost cap exhausted"
            elif run_total + maximum > self.settings.run_usd:
                reason = "Run cost cap: next maximum charge exceeds remaining funds"
            if reason:
                db.execute(
                    "UPDATE runs SET halted=COALESCE(halted, ?) WHERE id=?",
                    (reason, self.settings.run_id),
                )
            else:
                db.execute(
                    "INSERT INTO charges VALUES (?, ?, ?, ?, ?, ?, NULL, 'pending', ?)",
                    (
                        identifier,
                        self.settings.run_id,
                        self.settings.stage,
                        model,
                        effort,
                        str(maximum),
                        attempt.model_dump_json(),
                    ),
                )
        if reason:
            raise SpendStopped(reason)
        return identifier

    def settle(self, identifier: str, usage: Usage) -> None:
        if usage.cost_usd is None:
            raise ValueError("Cannot settle unknown charges")
        with self.transaction() as db:
            row = db.execute(
                "SELECT reserved, state FROM charges WHERE id=?", (identifier,)
            ).fetchone()
            if row is None or row[1] != "pending":
                raise ValueError("Unknown or already settled reservation")
            db.execute(
                "UPDATE charges SET actual=?, state='settled', usage=? WHERE id=?",
                (str(usage.cost_usd), usage.model_dump_json(), identifier),
            )
            if usage.cost_usd > Decimal(row[0]):
                db.execute(
                    "UPDATE project SET halted=? WHERE id=1",
                    ("Provider charge exceeded reserved bound; audit required",),
                )

    def cached(self, key: str) -> ModelResponse | None:
        with self.transaction() as db:
            row = db.execute("SELECT response FROM responses WHERE key=?", (key,)).fetchone()
        return ModelResponse.model_validate_json(row[0]) if row else None

    def cache(self, key: str, response: ModelResponse) -> None:
        with self.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO responses VALUES (?, ?)", (key, response.model_dump_json())
            )

    def report(self) -> dict[str, object]:
        with self.transaction() as db:
            rows = db.execute("SELECT run_id, reserved, actual, state FROM charges").fetchall()
            settled = db.execute(
                "SELECT run_id, usage FROM charges WHERE state='settled'"
            ).fetchall()
        physical = {}
        for scope in ("project", "run"):
            usages = [
                Usage.model_validate_json(value)
                for run, value in settled
                if scope == "project" or run == self.settings.run_id
            ]
            counts: dict[str, int | float | None] = {}
            for name in (
                "prompt_tokens",
                "completion_tokens",
                "cached_input_tokens",
                "cache_write_tokens",
                "reasoning_tokens",
                "model_calls",
                "api_calls",
                "preflight_calls",
                "latency_seconds",
            ):
                values = [getattr(u, name) for u in usages]
                counts[name] = None if None in values else sum(values)
            physical[scope] = counts
        total = self.settings.prior_spend_usd + sum(
            (Decimal(a if a is not None else r) for _, r, a, _ in rows), Decimal(0)
        )
        run_total = sum(
            (
                Decimal(a if a is not None else r)
                for run, r, a, _ in rows
                if run == self.settings.run_id
            ),
            Decimal(0),
        )
        return {
            "total_cap_usd": str(self.settings.total_usd),
            "run_id": self.settings.run_id,
            "run_cap_usd": str(self.settings.run_usd),
            "run_spent_plus_reserved_usd": str(run_total),
            "validation_reserve_usd": str(self.settings.validation_reserve_usd),
            "cumulative_project_cost_usd": str(total),
            "remaining_usd": str(max(Decimal(0), self.settings.total_usd - total)),
            "settled_physical_usage": physical,
            "generation_attempts": len(rows),
            "pending_attempts": sum(s == "pending" for _, _, _, s in rows),
            "halted": self.stop_reason(),
        }
