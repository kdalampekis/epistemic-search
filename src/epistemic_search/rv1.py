"""RV1 tooling: generate blank annotation files from frozen RV0 output, validate, aggregate.

No model is ever called and no judgment is inferred. Human fields stay null until a person
fills them; failure distributions are withheld until every case is complete.
"""

import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import Field

from epistemic_search.decomposition import ProofGraph
from epistemic_search.evaluation import file_hash
from epistemic_search.models import Schema
from epistemic_search.pilot_audit import normalized, surface_form
from epistemic_search.rv1_schema import (
    PROTOCOL,
    BatchUnit,
    BeliefUnit,
    CaseFile,
    DecisionUnit,
    DecompositionUnit,
    ItemUnit,
    MethodSection,
    OutcomeUnit,
    PremiseUnit,
    RootCauseJudgment,
    RoundUnit,
    check,
    context_hash,
    dump_case,
    judgments,
    load_case,
    oracle_graph,
)

METHODS = ("epistemic_search", "premise_only")
SEARCH_ACTIONS = {"SEARCH_MORE", "RESOLVE_CONFLICT"}
RV0_FILES = ("diagnostics.jsonl", "documents.jsonl", "manual_review_priority.jsonl")
AssessorId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
FREE_TEXT = {"notes", "rationale", "missing_blockers_description", "description"}
HEADER = """RV1 human annotation file ({case_id}). Edit ONLY the `assessor`, `date`, `status` fields
and the blank `judgment` / `oracle` / `root_cause` fields. `context` blocks are generated, hashed
and read-only: do not edit them.

Fill order, to limit hindsight: (1) oracle (written from the question and gold only, BEFORE
reading the generated decomposition below); (2) decomposition + premises; (3) per method:
retrieval rounds, extraction batches/items, belief states, controller decisions, outcome;
(4) root_cause last. Answers: YES / NO / UNSURE (NOT_APPLICABLE where offered). null means
not yet answered, never NO. Set status to IN_PROGRESS while working and COMPLETE only when
every field is answered; `rv1-validate` rejects a COMPLETE file with blanks.
Full retrieved-document text is in the matching sheet under the sheets directory.
See docs/experiments/RV1_ANNOTATION_PROTOCOL.md."""


class Rv1Config(Schema):
    rv0_dir: Path
    frozen_rv0_summary: Path
    annotations_dir: Path
    sheets_dir: Path
    results_dir: Path
    assessors: list[AssessorId] = Field(default_factory=lambda: ["primary"], min_length=1)


def read_config(path: Path) -> Rv1Config:
    cfg = Rv1Config.model_validate(yaml.safe_load(path.read_text()))
    resolved = {
        k: (path.parent / v).resolve() for k, v in cfg.model_dump().items() if isinstance(v, Path)
    }
    return cfg.model_copy(update=resolved)


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_rv0(cfg: Rv1Config) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    frozen = json.loads(cfg.frozen_rv0_summary.read_text())["output_hashes"]
    for name in RV0_FILES:
        if file_hash(cfg.rv0_dir / name) != frozen[name]:
            raise ValueError(f"RV0 output {name} differs from the frozen RV0 summary")
    documents = {d["key"]: d for d in jsonl(cfg.rv0_dir / "documents.jsonl")}
    return (
        jsonl(cfg.rv0_dir / "diagnostics.jsonl"),
        documents,
        jsonl(cfg.rv0_dir / "manual_review_priority.jsonl"),
    )


def dataset_short(dataset: str) -> str:
    return re.split(r"[-_]", dataset)[0]


def formula(graph: ProofGraph, labels: dict[str, str]) -> str:
    nodes = {n.id: n for n in graph.nodes}

    def render(node_id: str) -> str:
        node = nodes[node_id]
        if node.kind == "CLAIM":
            return labels[str(node.claim_id)]
        inner = ", ".join(render(c) for c in node.children)
        return inner if node.kind == "CONCLUSION" else f"{node.kind}({inner})"

    return render(graph.conclusion_id)


def method_section(
    rec: dict[str, Any], labels: dict[str, str], gold: set[str] | None, docs_seen: dict[str, Any]
) -> MethodSection:
    obs = rec["observations"]
    rounds, queries = obs["retrieval"], obs["targeted_queries"]

    def label(cid: str | None) -> str | None:
        return labels.get(cid, cid) if cid else None

    by_text: dict[str, dict[str, Any]] = {}
    round_units = []
    for j, r in enumerate(rounds):
        target = None
        if j:
            if j > len(queries) or queries[j - 1]["query"] != r["query"]:
                raise ValueError(f"{rec['query_id']}: search round {j + 1} has no matching query")
            target = label(queries[j - 1]["target_claim_id"])
        titles = [normalized(s["title"]).casefold() for s in r["sources"]]
        docs = []
        for s in r["sources"]:
            key = s["document_key"]
            if docs_seen.setdefault(key[:12], key) != key:
                raise ValueError("Document key prefix collision")
            docs.append({"doc": key[:12], "title": s["title"], "rank": s["rank"]})
            entry = by_text.setdefault(
                s["text_sha256"], {"doc": key[:12], "title": s["title"], "rounds": []}
            )
            entry["rounds"].append(j + 1)
        round_units.append(
            RoundUnit(
                id=r["event_id"],
                context={
                    "round": j + 1,
                    "kind": "ORIGINAL_QUESTION" if j == 0 else "TARGETED",
                    "query": r["query"],
                    "target_premise": target,
                    "query_exactly_repeats_earlier_round": r["query"]
                    in [x["query"] for x in rounds[:j]],
                    "document_set_repeats_earlier_round": r["repeated_document_set"],
                    "documents": docs,
                    "benchmark_gold_titles_in_this_round": None
                    if gold is None
                    else sorted(t for t in gold if t in titles),
                },
            )
        )
    decisions, n_search = [], 0
    for i, a in enumerate(obs["controller_actions"]):
        ctx: dict[str, Any] = {
            "decision": i + 1,
            "action": a["action"],
            "target_premise": label(a.get("target_claim_id")),
            "blocking_premises": [label(c) for c in a.get("blocking_claims", [])],
            "rationale": a.get("rationale"),
            "next_query": None,
            "next_query_exact_repeat_of_earlier": None,
        }
        if a["action"] in SEARCH_ACTIONS:
            if n_search < len(queries):
                q = queries[n_search]
                if q["target_claim_id"] != a.get("target_claim_id"):
                    raise ValueError(f"{rec['query_id']}: decision/query target mismatch")
                ctx["next_query"] = q["query"]
                ctx["next_query_exact_repeat_of_earlier"] = q["query"] in [
                    x["query"] for x in rounds[: n_search + 1]
                ]
            n_search += 1
        decisions.append(DecisionUnit(id=a["event_id"], context=ctx))
    transitions, reasoner = obs["belief_transitions"], obs["structured_reasoner"]
    if len(transitions) != len(reasoner):
        raise ValueError(f"{rec['query_id']}: belief/reasoner events do not pair")
    beliefs = []
    for k, (t, d) in enumerate(zip(transitions, reasoner, strict=True)):
        r_ = d["recorded"]
        beliefs.append(
            BeliefUnit(
                id=t["event_id"],
                context={
                    "update": k + 1,
                    "reasoner_event": d["event_id"],
                    "claims_after_update": [
                        {
                            "premise": label(b["claim_id"]),
                            "status": b["status"],
                            "support_score": b["support_score"],
                            "contradiction_score": b["contradiction_score"],
                            "uncertainty": b["uncertainty"],
                            "evidence_items": len(b["evidence_ids"]),
                        }
                        for b in t["after"]
                    ],
                    "beliefs_unchanged_by_this_update": t["unchanged"],
                    "reasoner_status": r_["status"],
                    "reasoner_sufficient": r_["sufficient"],
                    "reasoner_blockers": [label(c) for c in r_["blockers"]],
                    "reasoner_minimal_frontier": [label(c) for c in r_["minimal_frontier"]],
                    "reasoner_conflicts": [label(c) for c in r_["conflicts"]],
                    "scores_are_uncalibrated_heuristics": True,
                },
            )
        )
    accepted = obs["accepted_evidence"]
    batches = []
    for e in obs["extractions"]:
        sha = e["document_text_sha256"]
        claim_id = e["claim_ids"][0] if e["claim_ids"] else None
        items = []
        for i, it in enumerate(e["items"]):
            span_class = (
                "EXACT"
                if it["exact_in_document"]
                else "NORMALIZATION_EQUIVALENT"
                if it["present_after_nbsp_replacement"]
                or it["present_after_whitespace_normalization"]
                else "NON_VERBATIM"
            )
            items.append(
                ItemUnit(
                    id=f"{e['event_id']}#{i}",
                    context={
                        "span": it["span"],
                        "system_stance": it["stance"],
                        "system_stance_score": it["stance_score"],
                        "mechanical_span_class": span_class,
                        "accepted_into_ledger": any(
                            x["claim_id"] in e["claim_ids"]
                            and x["span"] == it["span"]
                            and x["stance"] == it["stance"]
                            for x in accepted
                        ),
                    },
                )
            )
        batches.append(
            BatchUnit(
                id=e["event_id"],
                context={
                    "premise": label(claim_id),
                    "premise_text": e["claim_text"],
                    "document": by_text.get(sha, {"doc": None, "title": None, "rounds": []}),
                    "schema_valid": e["schema_valid"],
                    "items_returned": len(items),
                },
                items=items,
            )
        )
    answer = (obs["final_output"] or {}).get("answer")
    decision = obs["final_decision"] or {}
    return MethodSection(
        run=rec["run"],
        trace_sha256=rec["trace_sha256"],
        outcome=OutcomeUnit(
            context={
                "status": obs["status"],
                "rv0_outcome": obs["outcome"],
                "answered": obs["answered"],
                "final_answer": answer,
                "reference_answer": obs["recorded_reference"],
                "exact_match": obs["exact_match"],
                "token_f1": obs["token_f1"],
                "final_decision_rationale": decision.get("rationale"),
                "error": obs["error"],
            }
        ),
        retrieval_rounds=round_units,
        extraction_batches=batches,
        belief_states=beliefs,
        controller_decisions=decisions,
        root_cause=RootCauseJudgment(),
    )


def build_cases(cfg: Rv1Config) -> tuple[list[CaseFile], dict[str, dict[str, Any]], dict[str, Any]]:
    records, documents, priority = load_rv0(cfg)
    by_case: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in records:
        if r["method"] in METHODS:
            by_case[(r["dataset"], r["query_id"])][r["method"]] = r
    cases, sheet_docs = [], {}
    for p in sorted(priority, key=lambda x: x["rank"]):
        group = by_case.get((p["dataset"], p["query_id"]))
        if not group:
            raise ValueError(f"No audited records for {p['dataset']}/{p['query_id']}")
        decompositions = {
            json.dumps(r["observations"]["decomposition"], sort_keys=True) for r in group.values()
        }
        if len(decompositions) != 1:
            raise ValueError(f"{p['query_id']}: audited methods differ in decomposition")
        first = next(iter(group.values()))
        obs = first["observations"]
        graph = ProofGraph.model_validate(obs["decomposition"])
        labels = {c.id: f"P{i + 1}" for i, c in enumerate(graph.claims)}
        annotations = obs["dataset_annotations"].get("annotations")
        facts = annotations.get("supporting_facts") if isinstance(annotations, dict) else None
        gold = (
            {normalized(str(f[0])).casefold() for f in facts if isinstance(f, list) and f}
            if facts
            else None
        )
        docs_seen: dict[str, Any] = {}
        methods = {
            m: method_section(group[m], labels, gold, docs_seen) for m in METHODS if m in group
        }
        short = dataset_short(p["dataset"])
        case = CaseFile(
            case_id=f"{short}:{p['query_id']}",
            order=p["rank"],
            dataset=p["dataset"],
            query_id=p["query_id"],
            context_sha256="",
            question=first["question"],
            gold={
                "reference_answer": obs["recorded_reference"],
                "answerable": obs["recorded_answerable"],
                **obs["dataset_annotations"],
            },
            decomposition=DecompositionUnit(
                context={
                    "formula": formula(graph, labels),
                    "premises": len(graph.claims),
                    "shared_by_methods": sorted(group),
                }
            ),
            premises=[
                PremiseUnit(
                    id=c.id,
                    context={
                        "label": labels[c.id],
                        "text": c.text,
                        "polarity": c.polarity,
                        "lexical_surface_form_flag": surface_form(c.text),
                    },
                )
                for c in graph.claims
            ],
            methods=methods,
        )
        case.context_sha256 = context_hash(case)
        cases.append(case)
        sheet_docs[case.case_id] = {prefix: documents[k] for prefix, k in docs_seen.items()}
    return cases, sheet_docs, {n: file_hash(cfg.rv0_dir / n) for n in RV0_FILES}


def file_name(case: CaseFile) -> str:
    ident = re.sub(r"[^A-Za-z0-9]", "", case.query_id)[:12]
    return f"{case.order:02d}_{dataset_short(case.dataset)}_{ident}.yaml"


def sheet(case: CaseFile, docs: dict[str, Any]) -> str:
    out = [
        f"# {case.case_id} (annotation order {case.order})",
        "",
        f"**Question:** {case.question}",
    ]
    out += ["", f"**Reference answer:** {case.gold.get('reference_answer')}", ""]
    annotations = case.gold.get("annotations")
    if isinstance(annotations, dict) and annotations.get("supporting_facts"):
        out += [f"**Benchmark supporting facts:** {annotations['supporting_facts']}", ""]
    out += [
        "## Generated decomposition",
        "",
        f"Formula: `{case.decomposition.context['formula']}`",
        "",
    ]
    out += [f"- **{p.context['label']}** `{p.id}`: {p.context['text']}" for p in case.premises]
    for name, m in sorted(case.methods.items()):
        out += ["", f"## {name}: {m.outcome.context['rv0_outcome']}", ""]
        for r in m.retrieval_rounds:
            shown: Any = r.context["documents"]
            out.append(
                f"- round {r.context['round']} ({r.context['kind']}, target "
                f"{r.context['target_premise']}): `{r.context['query']}` -> "
                + ", ".join(f"{d['doc']} {d['title']}" for d in shown)
            )
        out += [
            f"- decision {d.context['decision']}: {d.context['action']} "
            f"target {d.context['target_premise']} - {d.context['rationale']}"
            for d in m.controller_decisions
        ]
    out += ["", "## Retrieved documents (full text)", ""]
    for key, doc in sorted(docs.items()):
        source = doc["source"]
        out += [f"### {key} — {source['title']}", f"<{source['uri']}>", "", doc["text"], ""]
    return "\n".join(out) + "\n"


def write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)


def init_rv1(config_path: Path) -> dict[str, Any]:
    cfg = read_config(config_path)
    manifest_path = cfg.results_dir / "context_manifest.json"
    if manifest_path.exists() or any((cfg.annotations_dir / a).exists() for a in cfg.assessors):
        raise FileExistsError("RV1 files already exist; annotations are never overwritten")
    cases, docs, hashes = build_cases(cfg)
    manifest = {
        "protocol": PROTOCOL,
        "rv0_output_hashes": hashes,
        "cases": [
            {
                "case_id": c.case_id,
                "order": c.order,
                "file": file_name(c),
                "context_sha256": c.context_sha256,
            }
            for c in cases
        ],
    }
    for case in cases:
        write_new(
            cfg.sheets_dir / file_name(case).replace(".yaml", ".md"),
            sheet(case, docs[case.case_id]),
        )
        for assessor in cfg.assessors:
            write_new(
                cfg.annotations_dir / assessor / file_name(case),
                dump_case(case, HEADER.format(case_id=case.case_id)),
            )
    write_new(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"cases": len(cases), "assessors": cfg.assessors, "api_calls": 0}


def add_assessor(config_path: Path, assessor: str) -> dict[str, Any]:
    cfg = read_config(config_path)
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", assessor):
        raise ValueError("Assessor ids are lowercase letters, digits and underscores")
    manifest = json.loads((cfg.results_dir / "context_manifest.json").read_text())
    target = cfg.annotations_dir / assessor
    if target.exists():
        raise FileExistsError(f"{target} exists; annotations are never overwritten")
    cases, _, _ = build_cases(cfg)
    expected = {c["case_id"]: c["context_sha256"] for c in manifest["cases"]}
    if {c.case_id: c.context_sha256 for c in cases} != expected:
        raise ValueError("Regenerated context differs from the committed manifest")
    for case in cases:
        write_new(target / file_name(case), dump_case(case, HEADER.format(case_id=case.case_id)))
    return {"cases": len(cases), "assessor": assessor}


def validate_rv1(config_path: Path) -> dict[str, Any]:
    cfg = read_config(config_path)
    manifest = json.loads((cfg.results_dir / "context_manifest.json").read_text())
    expected = {c["file"]: c for c in manifest["cases"]}
    report: dict[str, Any] = {"assessors": {}, "issues": [], "_cases": {}}
    for directory in sorted(p for p in cfg.annotations_dir.iterdir() if p.is_dir()):
        found = {p.name for p in directory.glob("*.yaml")}
        for name in sorted(found ^ set(expected)):
            report["issues"].append(f"{directory.name}: unexpected or missing file {name}")
        statuses: Counter[str] = Counter()
        blank = 0
        loaded: dict[str, CaseFile] = {}
        for name in sorted(found & set(expected)):
            try:
                case = load_case(directory / name)
            except ValueError as exc:
                report["issues"].append(str(exc))
                continue
            entry = expected[name]
            if (case.case_id, case.order, case.context_sha256) != (
                entry["case_id"],
                entry["order"],
                entry["context_sha256"],
            ):
                report["issues"].append(f"{directory.name}/{name}: differs from committed manifest")
                continue
            result = check(case)
            report["issues"] += [f"{directory.name}/{name}: {i}" for i in result["issues"]]
            statuses[case.status] += 1
            blank += result["blank"]
            loaded[case.case_id] = case
        report["assessors"][directory.name] = {
            "cases_expected": len(expected),
            "complete": statuses["COMPLETE"],
            "in_progress": statuses["IN_PROGRESS"],
            "not_started": statuses["NOT_STARTED"],
            "blank_fields_total": blank,
        }
        report["_cases"][directory.name] = loaded
    return report


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 4)


def flat(case: CaseFile) -> dict[tuple[str, str, str], str]:
    values: dict[tuple[str, str, str], str] = {}
    for path, section, j in judgments(case):
        if section == "oracle":
            values[(path, section, "required_claims_count")] = str(len(case.oracle.required_claims))
            values[(path, section, "logic_type")] = str(case.oracle.logic.type)
            values[(path, section, "authored_before_viewing_generated")] = str(
                case.oracle.authored_before_viewing_generated
            )
            continue
        for name in type(j).model_fields:
            if name not in FREE_TEXT:
                value = getattr(j, name)
                values[(path, section, name)] = json.dumps(
                    sorted(value) if isinstance(value, list) else value
                )
    return values


def aggregate_rv1(config_path: Path) -> dict[str, Any]:
    cfg = read_config(config_path)
    report = validate_rv1(config_path)
    if report["issues"]:
        raise ValueError("RV1 files are inconsistent: " + "; ".join(report["issues"][:5]))
    all_cases: dict[str, dict[str, CaseFile]] = report.pop("_cases")
    summary: dict[str, Any] = {
        "protocol": PROTOCOL,
        "context_manifest_sha256": file_hash(cfg.results_dir / "context_manifest.json"),
        "api_calls": 0,
        "assessors": {},
        "agreement": None,
        "note": "Distributions appear only when an assessor has completed every case.",
    }
    oracle_rows, disagreements = [], []
    for assessor, cases in sorted(all_cases.items()):
        done = [c for c in cases.values() if c.status == "COMPLETE"]
        entry: dict[str, Any] = {
            **report["assessors"][assessor],
            "all_complete": False,
            "failure_distribution": None,
            "sections": None,
        }
        for case in sorted(cases.values(), key=lambda c: c.order):
            o = case.oracle
            if (
                o.authored_before_viewing_generated
                and o.required_claims
                and o.logic.type
                and all((c.assertion or "").strip() for c in o.required_claims)
            ):
                graph = oracle_graph(o)
                oracle_rows.append(
                    {
                        "assessor": assessor,
                        "case_id": case.case_id,
                        "dataset": case.dataset,
                        "query_id": case.query_id,
                        "case_status": case.status,
                        "authored_before_viewing_generated": o.authored_before_viewing_generated,
                        "required_claims": [c.model_dump() for c in o.required_claims],
                        "logic": o.logic.model_dump(),
                        "proof_graph": graph.model_dump(mode="json") if graph else None,
                        "context_sha256": case.context_sha256,
                    }
                )
        if done and len(done) == entry["cases_expected"]:
            entry["all_complete"] = True
            entry["failure_distribution"] = distribution(done)
            entry["sections"] = sections(done)
        summary["assessors"][assessor] = entry
    pairs = {}
    for a, b in combinations(sorted(all_cases), 2):
        common = sorted(
            cid
            for cid, c in all_cases[a].items()
            if c.status == "COMPLETE"
            and all_cases[b].get(cid)
            and all_cases[b][cid].status == "COMPLETE"
        )
        if not common:
            continue
        per_section: dict[str, tuple[list[str], list[str]]] = defaultdict(lambda: ([], []))
        for cid in common:
            fa, fb = flat(all_cases[a][cid]), flat(all_cases[b][cid])
            for key in sorted(fa):
                per_section[key[1]][0].append(fa[key])
                per_section[key[1]][1].append(fb[key])
                if fa[key] != fb[key]:
                    disagreements.append(
                        {
                            "assessors": [a, b],
                            "case_id": cid,
                            "unit": key[0],
                            "field": key[2],
                            "values": [fa[key], fb[key]],
                        }
                    )
        pairs[f"{a}|{b}"] = {
            "cases": len(common),
            "sections": {
                s: {
                    "fields_compared": len(x),
                    "raw_agreement": round(
                        sum(p == q for p, q in zip(x, y, strict=True)) / len(x), 4
                    ),
                    "cohens_kappa": kappa(x, y),
                }
                for s, (x, y) in sorted(per_section.items())
            },
        }
    summary["agreement"] = pairs or None
    cfg.results_dir.mkdir(parents=True, exist_ok=True)
    rows = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in oracle_rows)
    (cfg.results_dir / "oracle_decompositions.jsonl").write_text(rows)
    drows = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in disagreements)
    (cfg.results_dir / "disagreements.jsonl").write_text(drows)
    summary["oracle_decompositions_exported"] = len(oracle_rows)
    summary["disagreements"] = len(disagreements)
    (cfg.results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary


def distribution(done: list[CaseFile]) -> dict[str, Any]:
    out: dict[str, Any] = {"cases": len(done)}
    for method in METHODS:
        rows = [(c.dataset, c.methods[method].root_cause) for c in done if method in c.methods]
        if not rows:
            continue
        out[method] = {
            "n": len(rows),
            "primary": dict(sorted(Counter(rc.primary for _, rc in rows).items())),
            "secondary": dict(sorted(Counter(s for _, rc in rows for s in rc.secondary).items())),
            "primary_by_dataset": {
                d: dict(sorted(Counter(rc.primary for ds, rc in rows if ds == d).items()))
                for d in sorted({ds for ds, _ in rows})
            },
        }
    return out


def sections(done: list[CaseFile]) -> dict[str, Any]:
    counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    stance: dict[str, Counter[str]] = defaultdict(Counter)
    crosstab: dict[str, Counter[str]] = defaultdict(Counter)
    for case in done:
        flags = {p.id: p.context["lexical_surface_form_flag"] for p in case.premises}
        for _, section, j in judgments(case):
            if section == "oracle":
                continue
            for name in type(j).model_fields:
                if name not in FREE_TEXT:
                    value = getattr(j, name)
                    for v in value if isinstance(value, list) else [value]:
                        counts[section][name][str(v)] += 1
        for p in case.premises:
            crosstab[str(flags[p.id])][str(p.judgment.is_assertion)] += 1
        for m in case.methods.values():
            for b in m.extraction_batches:
                for i in b.items:
                    stance[str(i.context["system_stance"])][str(i.judgment.gold_stance)] += 1
    logic = Counter(str(c.oracle.logic.type) for c in done)
    return {
        "field_counts": {
            s: {f: dict(sorted(c.items())) for f, c in sorted(fs.items())}
            for s, fs in sorted(counts.items())
        },
        "is_assertion_by_lexical_flag": {
            k: dict(sorted(v.items())) for k, v in sorted(crosstab.items())
        },
        "system_stance_vs_gold_stance": {
            k: dict(sorted(v.items())) for k, v in sorted(stance.items())
        },
        "oracle": {
            "logic_types": dict(sorted(logic.items())),
            "generated_vs_oracle_premise_counts": [
                [c.case_id, len(c.premises), len(c.oracle.required_claims)]
                for c in sorted(done, key=lambda c: c.order)
            ],
            "graph_convertible": sum(oracle_graph(c.oracle) is not None for c in done),
        },
    }
