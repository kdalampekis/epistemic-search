"""RV2-A: the current stance component against official gold labels. No retrieval, no controller.

System under test = ``classify_evidence`` (Luna prompt) followed by the deterministic
``aggregate_beliefs`` with its default threshold. The gold claim and gold evidence go in; a
SUPPORT / CONTRADICT / NEUTRAL (or MIXED / ERROR) prediction comes out.
"""

import asyncio
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from epistemic_search.belief import aggregate_beliefs
from epistemic_search.config import BeliefConfig, RagConfig
from epistemic_search.evidence import classify_evidence
from epistemic_search.execution import configured_model, configured_spend
from epistemic_search.models import Claim, Source
from epistemic_search.providers import SearchResult
from epistemic_search.rv2_adapters import StanceExample
from epistemic_search.rv2_metrics import bootstrap_ci, pair_metrics, stance_metrics
from epistemic_search.rv2_run import CONFIG_DIR, SAMPLING_SEED, SEED, ledger_report

STATUS_TO_LABEL = {
    "SUPPORTED": "SUPPORT",
    "CONTRADICTED": "CONTRADICT",
    "UNKNOWN": "NEUTRAL",
    "MIXED": "MIXED",
}
SNAPSHOT = datetime(2026, 10, 29, tzinfo=UTC)


def document_for(example: StanceExample) -> SearchResult:
    source = Source(
        id=f"gold-{example.id}",
        uri=f"gold://{example.dataset}/{example.id}",
        title=example.dataset,
        retrieved_at=SNAPSHOT,
        source_type="benchmark",
    )
    return SearchResult(source=source, text=example.evidence, query=example.claim, rank=1)


async def predict(example: StanceExample, rag: RagConfig, model: Any) -> dict[str, Any]:
    claim = Claim(id="claim", text=example.claim)
    started = perf_counter()
    batch = await classify_evidence(example.id, claim, document_for(example), rag, model, SEED)
    belief = aggregate_beliefs([claim], batch.items, BeliefConfig())[0]
    label = "ERROR" if batch.errors else STATUS_TO_LABEL[belief.status.value]
    usage = batch.usage
    return {
        "id": example.id,
        "dataset": example.dataset,
        "group": example.group,
        "claim": example.claim,
        "gold": example.gold,
        "source_label": example.source_label,
        "predicted": label,
        "belief_status": belief.status.value,
        "support_score": belief.support_score,
        "contradiction_score": belief.contradiction_score,
        "items": [
            {
                "span": i.span,
                "stance": i.stance,
                "stance_score": i.stance_score,
                "alignment": i.metadata.get("alignment", "exact"),
            }
            for i in batch.items
        ],
        "rejections": [r.model_dump(mode="json") for r in batch.rejections],
        "errors": batch.errors,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "reasoning_tokens": usage.reasoning_tokens,
            "model_calls": usage.model_calls,
            "cost_usd": None if usage.cost_usd is None else str(usage.cost_usd),
            "reused_cost_usd": str(usage.reused_cost_usd),
            "model_cache_hits": usage.model_cache_hits,
            "latency_seconds": usage.latency_seconds,
        },
        "wall_seconds": perf_counter() - started,
    }


def stopped(record: dict[str, Any], rag: RagConfig) -> bool:
    """True when the failure is the ledger refusing a request (a cap), not a model error."""
    spend = configured_spend(rag, CONFIG_DIR)
    return bool(spend and spend.stop_reason() and record["errors"])


async def run_examples(
    examples: list[StanceExample], rag: RagConfig
) -> tuple[list[dict[str, Any]], str | None]:
    """Serial by design (the ledger forbids concurrent generations). Stops at the first cap."""
    records: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        model = configured_model(rag, CONFIG_DIR, client)
        for example in examples:
            record = await predict(example, rag, model)
            if stopped(record, rag):
                spend = configured_spend(rag, CONFIG_DIR)
                return records, spend.stop_reason() if spend else "stopped"
            records.append(record)
    return records, None


def cost(records: list[dict[str, Any]], key: str = "cost_usd") -> Decimal:
    return sum((Decimal(r["usage"][key] or 0) for r in records), Decimal(0))


def estimate(probe: list[dict[str, Any]], total_calls: int, rag: RagConfig) -> dict[str, Any]:
    """Planning figure from measured probe cost, plus the token-ceiling worst case."""
    physical = [
        Decimal(r["usage"]["cost_usd"] or 0) + Decimal(r["usage"]["reused_cost_usd"]) for r in probe
    ]
    mean = sum(physical, Decimal(0)) / len(physical)
    assert rag.cache_write_usd_per_million and rag.output_usd_per_million
    worst_input = max(r["usage"]["prompt_tokens"] for r in probe)
    ceiling_per_call = (
        Decimal(worst_input) * rag.cache_write_usd_per_million
        + Decimal(rag.max_output_tokens) * rag.output_usd_per_million
    ) / Decimal(1_000_000)
    return {
        "probe_items": [r["id"] for r in probe],
        "probe_mean_cost_usd": str(mean),
        "probe_mean_latency_seconds": sum(r["wall_seconds"] for r in probe) / len(probe),
        "planned_calls": total_calls,
        "planning_estimate_usd": str(mean * total_calls),
        "token_ceiling_bound_usd": str(ceiling_per_call * total_calls),
        "note": (
            "The ceiling bound assumes every call spends its full output allowance; the ledger "
            "stops the run before the cap regardless."
        ),
    }


def summarize(
    records: list[dict[str, Any]], planned: dict[str, list[StanceExample]]
) -> dict[str, Any]:
    """Per-dataset metrics. Items never run stay in the denominator as NOT_RUN."""
    by_id = {r["id"]: r for r in records}
    out: dict[str, Any] = {}
    for dataset, examples in planned.items():
        rows = [
            (e.gold, by_id[e.id]["predicted"] if e.id in by_id else "NOT_RUN") for e in examples
        ]
        entry: dict[str, Any] = {
            "planned": len(examples),
            "run": sum(e.id in by_id for e in examples),
        }
        entry["three_way"] = stance_metrics(rows)
        entry["two_way_support_vs_contradict"] = stance_metrics(
            [(g, p) for g, p in rows if g != "NEUTRAL"]
        )
        scored = list(zip(examples, [p for _, p in rows], strict=True))
        if dataset == "vitaminc":
            entry["pairs"] = pair_metrics([(e.group or "", e.gold, p) for e, p in scored])
            grouped: dict[str, list[tuple[str, str]]] = {}
            for e, p in scored:
                grouped.setdefault(e.group or e.id, []).append((e.gold, p))
            resample_units = list(grouped.values())
        else:
            resample_units = [[(e.gold, p)] for e, p in scored]

        def statistic(name: str) -> Callable[[Sequence[list[tuple[str, str]]]], float | None]:
            def compute(units: Sequence[list[tuple[str, str]]]) -> float | None:
                value = stance_metrics([pair for unit in units for pair in unit])[name]
                return None if value is None else float(value)

            return compute

        entry["bootstrap_95"] = {
            name: bootstrap_ci(resample_units, statistic(name), resamples=2000)
            for name in ("accuracy", "macro_f1", "false_contradict_rate")
        }
        out[dataset] = entry
    return out


def verdict(summary: dict[str, Any]) -> dict[str, Any]:
    """The pre-registered stance rule; no discretion."""
    vit, sci = summary["vitaminc"], summary["scifact"]
    checks = {
        "vitaminc_macro_f1_at_least_0.70": vit["three_way"]["macro_f1"] >= 0.70,
        "vitaminc_false_contradict_at_most_0.10": (vit["three_way"]["false_contradict_rate"] or 0)
        <= 0.10,
        "scifact_false_contradict_at_most_0.10": (sci["three_way"]["false_contradict_rate"] or 0)
        <= 0.10,
    }
    complete = all(s["run"] == s["planned"] for s in summary.values())
    return {
        "checks": checks,
        "stance_works": all(checks.values()) and complete,
        "complete": complete,
    }


def sample_description(planned: dict[str, list[StanceExample]]) -> dict[str, Any]:
    return {d: {"n": len(es), "ids": [e.id for e in es]} for d, es in planned.items()} | {
        "sampling_seed": SAMPLING_SEED
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_sync(
    examples: list[StanceExample], rag: RagConfig
) -> tuple[list[dict[str, Any]], str | None]:
    return asyncio.run(run_examples(examples, rag))


def spend_report(rag: RagConfig) -> dict[str, object]:
    return ledger_report(rag)


RUN_ID = "rv2-a-stance-v1"
CAP_USD = "0.25"
OUT = Path("docs/results/rv2/rv2_a")


def planned_samples(data_root: Path) -> dict[str, list[StanceExample]]:
    from epistemic_search.rv2_adapters import (
        load_scifact_pairs,
        load_vitaminc,
        sample_stratified,
        sample_vitaminc,
    )

    vit = sample_vitaminc(
        load_vitaminc(data_root / "vitaminc/vitaminc/dev.jsonl"), 50, SAMPLING_SEED
    )
    sci = sample_stratified(
        load_scifact_pairs(data_root / "scifact", "dev"), 100, SAMPLING_SEED, "scifact-dev"
    )
    return {"vitaminc": vit, "scifact": sci}


def stage_estimate(root: Path) -> dict[str, Any]:
    from epistemic_search.rv2_run import rag_config, write_new_json

    rag = rag_config(RUN_ID, CAP_USD)
    planned = planned_samples(root / "data/external")
    probes = [min(es, key=lambda e: e.id) for es in planned.values()]
    records, halted = run_sync(probes, rag)
    if halted or len(records) != len(probes):
        raise RuntimeError(f"Probe stopped: {halted}")
    total = sum(len(es) for es in planned.values())
    report = estimate(records, total, rag) | {
        "run_id": RUN_ID,
        "hard_cap_usd": CAP_USD,
        "probe_records": records,
        "ledger_after_probe": spend_report(rag),
    }
    write_new_json(root / OUT / "estimate.json", report)
    return report


def stage_run(root: Path) -> dict[str, Any]:
    from epistemic_search.rv2_run import MODEL, rag_config, write_new_json

    estimate_path = root / OUT / "estimate.json"
    if not estimate_path.exists():
        raise RuntimeError("Run the estimate stage first; the full run needs a logged estimate")
    rag = rag_config(RUN_ID, CAP_USD)
    planned = planned_samples(root / "data/external")
    everything = [e for es in planned.values() for e in es]
    started = perf_counter()
    records, halted = run_sync(everything, rag)
    summary = summarize(records, planned)
    result = {
        "experiment": "RV2-A stance against gold labels",
        "code": "tag epistemic-search-v1.1",
        "run_id": RUN_ID,
        "model": MODEL,
        "reasoning_effort": rag.reasoning_effort,
        "seed": SEED,
        "sampling_seed": SAMPLING_SEED,
        "splits": {"vitaminc": "dev", "scifact": "dev"},
        "belief_threshold": BeliefConfig().threshold,
        "label_mapping": {
            "SUPPORTED": "SUPPORT",
            "CONTRADICTED": "CONTRADICT",
            "UNKNOWN": "NEUTRAL",
            "MIXED": "MIXED (kept, counted wrong)",
        },
        "samples": sample_description(planned),
        "stopped_by_cap": halted,
        "metrics": summary,
        "verdict": verdict(summary),
        "totals": {
            "records": len(records),
            "model_calls": sum(r["usage"]["model_calls"] for r in records),
            "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in records),
            "completion_tokens": sum(r["usage"]["completion_tokens"] for r in records),
            "new_api_cost_usd": str(cost(records)),
            "logical_cost_incl_cache_usd": str(cost(records) + cost(records, "reused_cost_usd")),
            "wall_seconds": perf_counter() - started,
        },
        "ledger": spend_report(rag),
        "predictions": records,
    }
    write_new_json(root / OUT / "results.json", result)
    return result
