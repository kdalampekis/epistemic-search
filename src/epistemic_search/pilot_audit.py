"""RV0: read-only observations from saved runs; no semantic judging or providers."""

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from epistemic_search.baseline import RunResult
from epistemic_search.belief import aggregate_beliefs
from epistemic_search.config import RunConfig
from epistemic_search.decomposition import ProofGraph
from epistemic_search.evaluation import ScoredCase, file_hash
from epistemic_search.evidence import PROMPT_VERSION, EvidenceLedger, Extraction
from epistemic_search.failures import FailureConfig, classify
from epistemic_search.models import ClaimBelief, EvidenceItem, QueryCase
from epistemic_search.providers import ModelRequest, ModelResponse, SearchResponse
from epistemic_search.reasoning import SufficiencyResult, reason
from epistemic_search.statistics import matched_protocol, read_run

PROTOCOL = "rv0-mechanical-audit-v1"
REVIEW = "REQUIRES_MANUAL_REVIEW"
NA = "NOT_IMPLEMENTED_BY_METHOD"
TARGETS = {"epistemic_search", "premise_only"}
CATEGORIES = [
    "DECOMPOSITION_ERROR",
    "RETRIEVAL_ERROR",
    "EVIDENCE_EXTRACTION_ERROR",
    "STANCE_ERROR",
    "BELIEF_AGGREGATION_ERROR",
    "FORMALIZATION_ERROR",
    "CONTROLLER_ERROR",
    "ANSWER_GENERATION_ERROR",
    "APPROPRIATE_ABSTENTION",
    "UNKNOWN_REQUIRES_HUMAN_REVIEW",
]
# Fixed lexical list; a surface-form flag is not a semantic verdict on claim quality.
TASK_VERBS = frozenset(
    "identify determine establish resolve find verify check confirm locate compare decide".split()
)


class AuditConfig(FailureConfig):
    annotation_groups: int = Field(default=18, strict=True, ge=1)


def normalized(text: str) -> str:
    return " ".join(text.split())


def gold_title_retrieval(case: QueryCase, retrieval: list[dict[str, Any]]) -> dict[str, Any]:
    """Benchmark-annotated supporting titles vs retrieved titles; a proxy, not decisiveness."""
    annotations = case.metadata.get("annotations")
    facts = annotations.get("supporting_facts") if isinstance(annotations, dict) else None
    if not retrieval:
        return {"available": False, "reason": "no_retrieval_events"}
    if not isinstance(facts, list) or not facts:
        return {"available": False, "reason": "no_supporting_fact_annotation"}
    titles = [fact[0] for fact in facts if isinstance(fact, list) and fact]
    gold = sorted({normalized(str(title)).casefold(): str(title) for title in titles}.items())
    retrieved = {
        normalized(source["title"]).casefold() for r in retrieval for source in r["sources"]
    }
    found = [title for key, title in gold if key in retrieved]
    return {
        "available": True,
        "basis": "benchmark_supporting_facts_exact_title_match",
        "gold_titles": [title for _, title in gold],
        "gold_titles_retrieved": found,
        "gold_titles_missing": [title for key, title in gold if key not in retrieved],
        "recall": len(found) / len(gold),
        "decisive_evidence_present": REVIEW,
    }


def surface_form(text: str) -> str:
    """Lexical form of a claim's text only: tasks and questions are not checkable assertions."""
    words = text.split()
    first = words[0].lower().strip(",.;:") if words else ""
    if text.rstrip().endswith("?"):
        return "QUESTION_MARK"
    if first in TASK_VERBS:
        return "TASK_VERB_PREFIX"
    if first == "whether":
        return "WHETHER_CLAUSE"
    return "OTHER"


def mean_recall(rows: list[dict[str, Any]]) -> float | None:
    values = [
        r["gold_title_retrieval"]["recall"] for r in rows if r["gold_title_retrieval"]["available"]
    ]
    return round(sum(values) / len(values), 4) if values else None


def diagnostic(
    name: str,
    dataset: str,
    case: QueryCase,
    row: ScoredCase,
    result: RunResult,
    trace_hash: str,
    config: RunConfig,
    documents: dict[str, Any],
) -> dict[str, Any]:
    """Facts are tied to event IDs. Null semantic labels are never filled by heuristics."""
    outcome = classify(name, result, row, trace_hash).outcome
    graph: ProofGraph | None = None
    ledger = EvidenceLedger()
    beliefs: list[ClaimBelief] = []
    retrieval, extractions, transitions, derivations, actions, queries = [], [], [], [], [], []
    seen_documents: set[str] = set()
    previous_sets: list[set[str]] = []
    for event in result.trace:
        payload: dict[str, Any] = event.payload
        if event.type == "DECOMPOSE" and payload.get("graph"):
            graph = ProofGraph.model_validate(payload["graph"])
            beliefs = aggregate_beliefs(graph.claims, [], config.belief)
        elif event.type == "SEARCH":
            response = SearchResponse.model_validate(payload["response"])
            sources = []
            current = set()
            for doc in response.results:
                # Content keys distinguish sources and bind the complete original text.
                key = hashlib.sha256(doc.model_dump_json().encode()).hexdigest()
                documents[key] = doc.model_dump(mode="json")
                content = hashlib.sha256(doc.text.encode()).hexdigest()
                current.add(content)
                sources.append(
                    {
                        "document_key": key,
                        "source_id": doc.source.id,
                        "title": doc.source.title,
                        "text_sha256": content,
                        "rank": doc.rank,
                    }
                )
            retrieval.append(
                {
                    "event_id": event.id,
                    "query": payload["query"],
                    "sources": sources,
                    "returned_documents": len(sources),
                    "new_document_texts": len(current - seen_documents),
                    "repeated_document_set": bool(current) and current in previous_sets,
                }
            )
            previous_sets.append(current)
            seen_documents.update(current)
        elif event.type == "MODEL" and payload["request"]["prompt_version"] == PROMPT_VERSION:
            request = ModelRequest.model_validate(payload["request"])
            response_model = ModelResponse.model_validate(payload["response"])
            data = json.loads(request.prompt[request.prompt.index("{") :])
            raw: dict[str, Any] = {
                "event_id": event.id,
                "claim_text": data["claim"],
                "claim_ids": [c.id for c in graph.claims if c.text == data["claim"]]
                if graph
                else [],
                "schema_valid": True,
                "items": [],
            }
            raw["document_text_sha256"] = hashlib.sha256(data["document"].encode()).hexdigest()
            try:
                extracted = response_model.parse(Extraction)
            except ValueError:
                raw["schema_valid"] = False
            else:
                for item in extracted.items:
                    raw["items"].append(
                        {
                            **item.model_dump(mode="json"),
                            "exact_in_document": bool(item.span.strip())
                            and item.span in data["document"],
                            "present_after_nbsp_replacement": item.span.replace("\u00a0", " ")
                            in data["document"].replace("\u00a0", " "),
                            "present_after_whitespace_normalization": normalized(item.span)
                            in normalized(data["document"]),
                            "semantic_stance_review": REVIEW,
                        }
                    )
            extractions.append(raw)
        elif event.type == "EVIDENCE_ADDED":
            for item in payload["items"]:
                ledger.add(EvidenceItem.model_validate(item))
        elif event.type == "BELIEF_UPDATE" and graph:
            observed = [ClaimBelief.model_validate(b) for b in payload["beliefs"]]
            replayed = aggregate_beliefs(graph.claims, ledger.items, config.belief)
            transitions.append(
                {
                    "event_id": event.id,
                    "before": [b.model_dump(mode="json") for b in beliefs],
                    "after": [b.model_dump(mode="json") for b in observed],
                    "unchanged": observed == beliefs,
                    "matches_current_replay": observed == replayed,
                    "replayed": [b.model_dump(mode="json") for b in replayed],
                }
            )
            beliefs = observed
        elif event.type == "SUFFICIENCY" and graph:
            observed_reason = SufficiencyResult.model_validate(payload)
            replayed_reason = reason(graph, beliefs)
            derivations.append(
                {
                    "event_id": event.id,
                    "recorded": payload,
                    "matches_current_replay": observed_reason == replayed_reason,
                    "replayed": replayed_reason.model_dump(mode="json"),
                }
            )
        elif event.type == "DECISION":
            actions.append({"event_id": event.id, **payload})
        elif event.type == "QUERY_GENERATED":
            queries.append({"event_id": event.id, **payload, "semantic_quality": REVIEW})

    target = result.method in TARGETS
    review = REVIEW if target else "OUTSIDE_SEMANTIC_AUDIT_SCOPE"
    evidence = [e.model_dump(mode="json") for e in ledger.items]
    invalid = [
        item for batch in extractions for item in batch["items"] if not item["exact_in_document"]
    ]
    candidates = []
    if invalid or any(not e["schema_valid"] for e in extractions):
        candidates.append(
            {
                "category": "EVIDENCE_EXTRACTION_ERROR",
                "basis": "literal_or_schema_contract_violation",
            }
        )
    if any(not t["matches_current_replay"] for t in transitions):
        candidates.append(
            {
                "category": "BELIEF_AGGREGATION_ERROR",
                "basis": "current_replay_mismatch_not_semantic_verdict",
            }
        )
    if any(not t["matches_current_replay"] for t in derivations):
        candidates.append(
            {
                "category": "FORMALIZATION_ERROR",
                "basis": "current_replay_mismatch_not_semantic_verdict",
            }
        )
    return {
        "protocol": PROTOCOL,
        "run": name,
        "dataset": dataset,
        "query_id": case.id,
        "method": result.method,
        "trace_file": row.trace_file,
        "trace_sha256": trace_hash,
        "question": case.question,
        "semantic_audit_scope": target,
        "observations": {
            "status": result.status,
            "outcome": outcome,
            "error": result.error,
            "answered": row.answered,
            "exact_match": row.exact_match,
            "token_f1": row.token_f1,
            "recorded_reference": case.gold_answer,
            "recorded_answerable": case.answerable,
            "dataset_annotations": case.metadata,
            "model": config.rag.model if config.rag else None,
            "reasoning_effort": config.rag.reasoning_effort if config.rag else None,
            "usage": result.usage.model_dump(mode="json"),
            "usage_complete": result.usage_complete,
            "wall_seconds": result.wall_seconds,
            "decomposition": graph.model_dump(mode="json") if graph else None,
            "retrieval": retrieval,
            "gold_title_retrieval": gold_title_retrieval(case, retrieval),
            "claim_surface_forms": {c.id: surface_form(c.text) for c in graph.claims}
            if graph
            else None,
            "extractions": extractions,
            "accepted_evidence": evidence,
            "belief_transitions": transitions,
            "structured_reasoner": derivations,
            "blocking_obligations": result.state.blockers if result.state else None,
            "controller_actions": actions,
            "targeted_queries": queries,
            "final_decision": result.decision.model_dump(mode="json") if result.decision else None,
            "last_recorded_action": actions[-1]["action"] if actions else None,
            "final_output": result.output.model_dump(mode="json") if result.output else None,
            "invalid_span_count": len(invalid),
            "invalid_spans_matching_after_nbsp_replacement": sum(
                item["present_after_nbsp_replacement"] for item in invalid
            ),
            "accepted_stance_counts": dict(Counter(e["stance"] for e in evidence)),
            "empty_extraction_batches": sum(
                e["schema_valid"] and not e["items"] for e in extractions
            ),
            "repeated_document_sets": sum(r["repeated_document_set"] for r in retrieval),
            "belief_updates_unchanged": sum(t["unchanged"] for t in transitions),
            "exact_repeated_queries": len(retrieval) - len({r["query"] for r in retrieval}),
            "final_state": result.state.model_dump(mode="json", exclude={"trace"})
            if result.state
            else None,
            "extraction_events": [
                {"event_id": e.id, **e.payload} for e in result.trace if e.type == "EVIDENCE_ADDED"
            ],
        },
        "human_judgments": {
            "status": review,
            "assessor": None,
            "decomposition_quality": None,
            "premises": [
                {
                    "claim_id": c.id,
                    "necessary": None,
                    "correct": None,
                    "atomic": None,
                    "complete": None,
                    "dependency_correct": None,
                }
                for c in graph.claims
            ]
            if graph
            else [],
            "missing_required_premises": None,
            "retrieval_success": None,
            "decisive_evidence_present": None,
            "evidence_assignment_and_stance": REVIEW if result.method == "epistemic_search" else NA,
            "belief_semantics": REVIEW if result.method == "epistemic_search" else NA,
            "formalization_semantics": REVIEW if result.method == "epistemic_search" else NA,
            "controller_action_appropriate": None,
            "targeted_query_quality": None,
            "abstention_appropriate": None,
            "answer_correct": None,
            "primary_attribution": "UNKNOWN_REQUIRES_HUMAN_REVIEW",
        },
        "candidate_observed_defects": candidates,
    }


def annotation(record: dict[str, Any]) -> dict[str, Any]:
    obs = record["observations"]
    return {
        "run": record["run"],
        "query_id": record["query_id"],
        "trace_sha256": record["trace_sha256"],
        "status": "NOT_ANNOTATED",
        "assessor": None,
        "annotated_at": None,
        "protocol": "rv1-proposed-v1",
        "judgments": record["human_judgments"],
        "evidence": [
            {
                "event_id": batch["event_id"],
                "item_index": i,
                "gold_stance": None,
                "assignment_correct": None,
                "decisive": None,
                "rationale": None,
            }
            for batch in obs["extractions"]
            for i, _ in enumerate(batch["items"])
        ],
        "decisive_document_keys": None,
        "missing_premise_descriptions": None,
        "primary_category": None,
        "secondary_categories": [],
        "rationale": None,
    }


def audit_pilot(config_path: Path) -> dict[str, Any]:
    cfg = AuditConfig.model_validate(yaml.safe_load(config_path.read_text()))
    if cfg.judgments_path:
        raise ValueError("RV0 does not import judgments or adjudicate semantics")
    output = (config_path.parent / cfg.output_dir).resolve()
    roots = {name: (config_path.parent / path).resolve() for name, path in cfg.runs.items()}
    if output.exists() or any(
        output.is_relative_to(p) or p.is_relative_to(output) for p in roots.values()
    ):
        raise ValueError("Audit output must be new and separate from all source runs")
    records: list[dict[str, Any]] = []
    documents: dict[str, Any] = {}
    source_hashes: dict[str, dict[str, str]] = {}
    protocols: dict[str, dict[str, Any]] = {}
    checked: dict[Path, str] = {}
    for name, root in sorted(roots.items()):
        saved = read_run(root)
        config = RunConfig.model_validate(saved.manifest["config"])
        assert config.evaluation is not None
        dataset = config.evaluation.dataset_name
        protocol = matched_protocol(saved)
        if dataset in protocols and protocols[dataset] != protocol:
            raise ValueError("Methods do not share a matched experimental protocol")
        protocols[dataset] = protocol
        hashes = dict(saved.hashes)
        for row in saved.rows.values():
            path = (root / row.trace_file).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Trace path escapes source run")
            result = RunResult.model_validate_json(path.read_text())
            if (
                result.query_id,
                result.status,
                result.usage,
                result.usage_complete,
                result.method,
            ) != (row.query_id, row.status, row.usage, row.usage_complete, config.method):
                raise ValueError("Trace identity/status/usage differs from saved scores")
            answered = (
                result.status == "completed"
                and result.output is not None
                and result.output.answer is not None
            )
            if answered != row.answered:
                raise ValueError("Saved answer-presence flag differs from trace")
            hashes[row.trace_file] = file_hash(path)
            records.append(
                diagnostic(
                    name,
                    dataset,
                    saved.labels[row.query_id],
                    row,
                    result,
                    hashes[row.trace_file],
                    config,
                    documents,
                )
            )
        checked.update({root / p: h for p, h in hashes.items()})
        source_hashes[name] = hashes
    # Keep the actual matched naive result, never an imagined counterfactual RAG answer.
    naive = {(r["dataset"], r["query_id"]): r for r in records if r["method"] == "naive_rag"}
    for record in records:
        other = naive.get((record["dataset"], record["query_id"]))
        record["matched_naive_rag"] = {
            "available": other is not None,
            "run": other["run"] if other else None,
            "trace_sha256": other["trace_sha256"] if other else None,
            "recorded_scores": {
                k: other["observations"][k] for k in ("answered", "exact_match", "token_f1")
            }
            if other
            else None,
            "semantic_correctness": REVIEW,
        }
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["semantic_audit_scope"]:
            groups[(record["dataset"], record["query_id"])].append(record)

    def priority(key: tuple[str, str]) -> tuple[int, int, int, int, str, str]:
        rs = groups[key]
        return (
            -sum(r["observations"]["status"] == "error" for r in rs),
            -sum(bool(r["candidate_observed_defects"]) for r in rs),
            -sum(
                any(b["recorded"]["conflicts"] for b in r["observations"]["structured_reasoner"])
                for r in rs
            ),
            -sum(r["observations"]["repeated_document_sets"] for r in rs),
            *key,
        )

    ranked = sorted(groups, key=priority)
    selected = ranked[: cfg.annotation_groups]
    templates = [annotation(r) for key in selected for r in groups[key]]
    priorities = [
        {
            "rank": i + 1,
            "dataset": key[0],
            "query_id": key[1],
            "selected_for_proposed_rv1": key in selected,
            "priority_tuple": list(priority(key)[:4]),
            "records": [{"run": r["run"], "trace_sha256": r["trace_sha256"]} for r in groups[key]],
        }
        for i, key in enumerate(ranked)
    ]
    methods = {}
    for method in sorted({r["method"] for r in records}):
        rows = [r["observations"] for r in records if r["method"] == method]
        methods[method] = {
            "cases": len(rows),
            "outcomes": dict(Counter(r["outcome"] for r in rows)),
            "invalid_span_cases": sum(r["invalid_span_count"] > 0 for r in rows),
            "invalid_spans": sum(r["invalid_span_count"] for r in rows),
            "invalid_spans_matching_after_nbsp_replacement": sum(
                r["invalid_spans_matching_after_nbsp_replacement"] for r in rows
            ),
            "repeated_document_set_cases": sum(r["repeated_document_sets"] > 0 for r in rows),
            "exact_repeated_query_cases": sum(r["exact_repeated_queries"] > 0 for r in rows),
            "extraction_batches": sum(len(r["extractions"]) for r in rows),
            "empty_extraction_batches": sum(r["empty_extraction_batches"] for r in rows),
            "belief_updates_checked": sum(len(r["belief_transitions"]) for r in rows),
            "belief_updates_unchanged": sum(r["belief_updates_unchanged"] for r in rows),
            "cases_with_unchanged_belief_update": sum(
                r["belief_updates_unchanged"] > 0 for r in rows
            ),
            "belief_replay_mismatches": sum(
                not t["matches_current_replay"] for r in rows for t in r["belief_transitions"]
            ),
            "gold_title_cases": sum(r["gold_title_retrieval"]["available"] for r in rows),
            "claims": sum(len(r["claim_surface_forms"] or {}) for r in rows),
            "claims_by_surface_form": dict(
                Counter(f for r in rows for f in (r["claim_surface_forms"] or {}).values())
            ),
            "cases_with_non_assertion_surface_form": sum(
                any(f != "OTHER" for f in (r["claim_surface_forms"] or {}).values()) for r in rows
            ),
            "gold_title_mean_recall": mean_recall(rows),
            "gold_title_all_retrieved_cases": sum(
                r["gold_title_retrieval"].get("recall") == 1 for r in rows
            ),
            "gold_title_none_retrieved_cases": sum(
                r["gold_title_retrieval"].get("recall") == 0 for r in rows
            ),
            "final_decision_rationales": dict(
                Counter(r["final_decision"]["rationale"] for r in rows if r["final_decision"])
            ),
            "reasoner_results_checked": sum(len(r["structured_reasoner"]) for r in rows),
            "reasoner_replay_mismatches": sum(
                not t["matches_current_replay"] for r in rows for t in r["structured_reasoner"]
            ),
        }
    summary = {
        "protocol": PROTOCOL,
        "cases": len(records),
        "question_groups": len(groups),
        "detailed_method_cases": sum(r["semantic_audit_scope"] for r in records),
        "outcomes": dict(Counter(r["observations"]["outcome"] for r in records)),
        "methods": methods,
        "human_annotations_completed": 0,
        "semantic_failure_distribution": None,
        "attribution_status": REVIEW,
        "proposed_annotation_method_cases": len(templates),
        "proposed_annotation_groups": len(selected),
        "additional_api_calls": 0,
        "additional_api_cost_usd": "0",
        "source_hashes": source_hashes,
        "config_sha256": file_hash(config_path),
        "implementation_sha256": file_hash(Path(__file__)),
        "allowed_rv1_categories": CATEGORIES,
        "limitations": [
            "Mechanical agreement is not independent semantic validation.",
            "No causal failure percentages can be inferred without human annotation.",
            "Abstention is not an error; reference match is not proof of correctness.",
            "Normalizing spans is a diagnostic only; no evidence is repaired.",
            "Claim surface forms are lexical flags, not claim-quality judgments.",
            "Gold-title recall uses benchmark supporting-fact titles; it is a proxy only.",
            "Premise-only has no stance/belief/formal components; absence is intentional.",
        ],
    }
    if any(file_hash(p) != h for p, h in checked.items()):
        raise ValueError("Source changed while auditing")
    output.mkdir(parents=True, exist_ok=False)
    for filename, values in (
        ("diagnostics.jsonl", records),
        ("documents.jsonl", [{"key": k, **v} for k, v in sorted(documents.items())]),
        ("rv1_annotation_template.jsonl", templates),
        ("manual_review_priority.jsonl", priorities),
    ):
        (output / filename).write_text(
            "".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in values)
        )
    table = io.StringIO()
    writer = csv.DictWriter(
        table,
        fieldnames=[
            "run",
            "query_id",
            "method",
            "trace_sha256",
            "outcome",
            "answered",
            "exact_match",
            "token_f1",
            "invalid_span_count",
            "repeated_document_sets",
            "semantic_review",
        ],
    )
    writer.writeheader()
    for r in records:
        writer.writerow(
            {
                **{k: r[k] for k in ("run", "query_id", "method", "trace_sha256")},
                **{
                    k: r["observations"][k]
                    for k in (
                        "outcome",
                        "answered",
                        "exact_match",
                        "token_f1",
                        "invalid_span_count",
                        "repeated_document_sets",
                    )
                },
                "semantic_review": r["human_judgments"]["status"],
            }
        )
    (output / "diagnostics.csv").write_text(table.getvalue())
    summary["output_hashes"] = {p.name: file_hash(p) for p in sorted(output.iterdir())}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary
