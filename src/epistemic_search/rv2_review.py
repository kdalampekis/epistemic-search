"""RV2-0: blind human spot-check of the RV1 labels. No model is called, nothing is inferred.

The reviewer first labels stance items and case root causes WITHOUT seeing the system's or the
RV1 assessor's labels, then opens a separate reveal file. Item selection is a fixed, seeded,
stratified rule so the sample is not hand-picked.
"""

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field

from epistemic_search.models import Schema
from epistemic_search.pilot_audit import normalized
from epistemic_search.rv1_schema import (
    CaseFile,
    RootCauseLabel,
    load_case,
)

PROTOCOL = "rv2-0-blind-spot-check-v1"
Stance = Literal["SUPPORT", "CONTRADICT", "NEUTRAL", "UNSURE"]
Agree = Literal["YES", "NO", "UNSURE"]
CAUSES = [
    "DECOMPOSITION_ERROR",
    "RETRIEVAL_ERROR",
    "QUERY_GENERATION_ERROR",
    "EVIDENCE_EXTRACTION_ERROR",
    "STANCE_ERROR",
    "BELIEF_AGGREGATION_ERROR",
    "FORMALIZATION_ERROR",
    "CONTROLLER_ERROR",
    "ANSWER_GENERATION_ERROR",
    "APPROPRIATE_ABSTENTION",
    "MULTIPLE_FAILURES",
    "NO_IDENTIFIED_FAILURE",
    "UNCERTAIN",
]
REFERENCE_AGREEMENT = 0.85


class Stratum(Schema):
    system: Literal["SUPPORT", "CONTRADICT", "NEUTRAL"]
    gold: Literal["SUPPORT", "CONTRADICT", "NEUTRAL"]
    n: int | None = Field(default=None, ge=1)  # None = take every item in the stratum


class ReviewConfig(Schema):
    rv1_annotations: Path
    rv0_dir: Path
    output_dir: Path
    responses_path: Path
    cases: list[int] = Field(default_factory=lambda: [5, 6, 8, 12, 17])
    seed: int = 20261024
    strata: list[Stratum]


class ItemResponse(Schema):
    id: str
    human_stance: Stance | None = None
    notes: str | None = None


class CaseResponse(Schema):
    case: int
    human_primary_cause_epistemic_search: RootCauseLabel | None = None
    human_primary_cause_premise_only: RootCauseLabel | None = None
    agrees_with_rv1_epistemic_search: Agree | None = None
    agrees_with_rv1_premise_only: Agree | None = None
    notes: str | None = None


class Responses(Schema):
    reviewer: str | None = None
    date: str | None = None
    stance_items: list[ItemResponse]
    cases: list[CaseResponse]


def read_config(path: Path) -> ReviewConfig:
    cfg = ReviewConfig.model_validate(yaml.safe_load(path.read_text()))
    resolved = {
        k: (path.parent / v).resolve() for k, v in cfg.model_dump().items() if isinstance(v, Path)
    }
    return cfg.model_copy(update=resolved)


def load_documents(rv0_dir: Path) -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for line in (rv0_dir / "documents.jsonl").read_text().splitlines():
        row = json.loads(line)
        docs[row["key"][:12]] = row
    return docs


def excerpt(text: str, span: str, width: int = 450) -> str:
    flat = text.replace(" ", " ")
    probe = span.replace(" ", " ")
    at = flat.find(probe)
    if at < 0:
        at = flat.find(normalized(probe)[:60])
    if at < 0:
        return flat[: 2 * width].strip() + " ..."
    start, end = max(0, at - width), min(len(flat), at + len(probe) + width)
    return ("... " if start else "") + flat[start:end].strip() + (" ..." if end < len(flat) else "")


def distinct_items(cases: list[CaseFile], docs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for case in cases:
        method = case.methods["epistemic_search"]
        premises = {p.context["label"]: p for p in case.premises}
        for batch in method.extraction_batches:
            premise = premises[str(batch.context["premise"])]
            doc_ref: Any = batch.context["document"]
            doc = docs.get(str(doc_ref["doc"])) if doc_ref.get("doc") else None
            for item in batch.items:
                key = (
                    case.order,
                    premise.context["label"],
                    item.context["span"],
                    item.context["system_stance"],
                )
                if key in seen:
                    continue
                seen[key] = {
                    "case": case.order,
                    "case_id": case.case_id,
                    "question": case.question,
                    "reference": case.gold.get("reference_answer"),
                    "premise_label": premise.context["label"],
                    "premise_text": premise.context["text"],
                    "premise_flag": premise.context["lexical_surface_form_flag"],
                    "rv1_premise_is_assertion": premise.judgment.is_assertion,
                    "document_title": doc["source"]["title"] if doc else doc_ref.get("title"),
                    "document_lead": (doc["text"][:300] if doc else ""),
                    "context": excerpt(doc["text"], str(item.context["span"])) if doc else "",
                    "span": item.context["span"],
                    "system_stance": item.context["system_stance"],
                    "rv1_stance": item.judgment.gold_stance,
                    "rv1_addresses_premise": item.judgment.addresses_assigned_premise,
                    "rv1_notes": item.judgment.notes,
                }
    return list(seen.values())


def select(items: list[dict[str, Any]], cfg: ReviewConfig) -> list[dict[str, Any]]:
    rng = random.Random(cfg.seed)
    chosen: list[dict[str, Any]] = []
    for stratum in cfg.strata:
        pool = sorted(
            (
                i
                for i in items
                if (i["system_stance"], i["rv1_stance"]) == (stratum.system, stratum.gold)
            ),
            key=lambda i: (i["case"], i["premise_label"], i["span"]),
        )
        take = pool if stratum.n is None or stratum.n >= len(pool) else rng.sample(pool, stratum.n)
        chosen += [{**i, "stratum": f"{stratum.system}->{stratum.gold}"} for i in take]
    rng.shuffle(chosen)
    for n, item in enumerate(chosen, 1):
        item["id"] = f"S{n:02d}"
    return chosen


def ctx(unit: Any) -> dict[str, Any]:
    return dict(unit.context)


def case_packet(case: CaseFile, docs: dict[str, dict[str, Any]]) -> list[str]:
    """System-side facts only; RV1 judgments are never shown here."""
    out = [f"### Case {case.order} — {case.case_id}", "", f"**Question:** {case.question}", ""]
    out += [f"**Reference answer:** {case.gold.get('reference_answer')}", ""]
    annotations: Any = case.gold.get("annotations")
    wanted: set[str] = set()
    if isinstance(annotations, dict) and annotations.get("supporting_facts"):
        titles = sorted({str(f[0]) for f in annotations["supporting_facts"]})
        wanted = {normalized(t).casefold() for t in titles}
        out += [f"**Benchmark supporting-document titles:** {titles}", ""]
    out += [f"**Generated decomposition:** `{ctx(case.decomposition)['formula']}`", ""]
    out += [f"- **{ctx(p)['label']}**: {ctx(p)['text']}" for p in case.premises] + [""]
    premises = {str(ctx(p)["label"]): ctx(p) for p in case.premises}
    gold_docs: dict[str, dict[str, Any]] = {}
    for name, m in sorted(case.methods.items()):
        c = ctx(m.outcome)
        out += [f"#### {name}: {c['rv0_outcome']}; final answer: {c['final_answer']!r}", ""]
        for r in m.retrieval_rounds:
            rc = ctx(r)
            shown = ", ".join(str(d["title"]) for d in rc["documents"])
            out.append(
                f"- round {rc['round']} ({rc['kind']}, target {rc['target_premise']}): "
                f"`{rc['query']}` -> {shown}"
            )
            for d in rc["documents"]:
                doc = docs.get(str(d["doc"]))
                if doc and normalized(doc["source"]["title"]).casefold() in wanted:
                    gold_docs[doc["key"]] = doc
        for d in m.controller_decisions:
            dc = ctx(d)
            out.append(
                f"- decision {dc['decision']}: {dc['action']} (target {dc['target_premise']}); "
                f"{dc['rationale']}"
            )
        if name == "epistemic_search":
            seen: set[tuple[Any, ...]] = set()
            for b in m.extraction_batches:
                bc = ctx(b)
                for i in b.items:
                    ic = ctx(i)
                    key = (bc["premise"], ic["span"], ic["system_stance"])
                    if key in seen:
                        continue
                    seen.add(key)
                    title = (bc["document"] or {}).get("title")
                    out.append(
                        f"- evidence for {bc['premise']} "
                        f"({premises[str(bc['premise'])]['text'][:60]}) from *{title}*: "
                        f"“{str(ic['span'])[:140]}” [system {ic['system_stance']}]"
                    )
        out.append("")
    if gold_docs:
        out += ["#### Retrieved documents whose title is a benchmark supporting title", ""]
        for doc in gold_docs.values():
            out += [f"- *{doc['source']['title']}*: {doc['text'][:500].strip()} ...", ""]
    return out


def reveal_for_case(case: CaseFile) -> list[str]:
    out = [f"### Case {case.order} — RV1 conclusions", ""]
    for name, m in sorted(case.methods.items()):
        rc = m.root_cause
        out += [
            f"- **{name}**: primary `{rc.primary}`, secondary {rc.secondary or 'none'}",
            f"  - rationale: {rc.rationale}",
        ]
    out += [
        "",
        f"- decomposition judged semantically correct: "
        f"{case.decomposition.judgment.semantically_correct}; "
        f"unnecessary premises: {case.decomposition.judgment.has_unnecessary_premises}",
        "",
    ]
    return out


def build_review(config_path: Path) -> dict[str, Any]:
    cfg = read_config(config_path)
    paths = [
        cfg.output_dir / "RV2_0_REVIEW.md",
        cfg.output_dir / "RV2_0_CASES.md",
        cfg.output_dir / "RV2_0_REVEAL.md",
        cfg.output_dir / "rv2_0_selection.json",
        cfg.responses_path,
    ]
    if any(p.exists() for p in paths):
        raise FileExistsError("RV2-0 review files already exist; never overwritten")
    cases = [load_case(p) for p in sorted(cfg.rv1_annotations.glob("*.yaml"))]
    docs = load_documents(cfg.rv0_dir)
    by_order = {c.order: c for c in cases}
    missing = [n for n in cfg.cases if n not in by_order]
    if missing:
        raise ValueError(f"Unknown case numbers: {missing}")
    items = select(distinct_items(cases, docs), cfg)
    blind = [
        "# RV2-0 — blind spot-check of the RV1 labels",
        "",
        "Reading order: this file (Part 1), then `RV2_0_CASES.md` (Part 2), then",
        "`RV2_0_REVEAL.md`. Record your answers in",
        f"`{cfg.responses_path.name}` as you go. This file shows neither the system's nor the",
        "RV1 assessor's stance, on purpose: otherwise your agreement would only measure anchoring.",
        "The RV1 labels came from GPT-5.6 Sol (model-assisted, not human ground truth); this",
        "check is how we find out whether they can be trusted.",
        "",
        "## Part 1 — stance items",
        "",
        "For each item decide the stance of the **span** toward the **premise**, judging the",
        "premise about the *specific entity/event it names*:",
        "`SUPPORT` (the span establishes it), `CONTRADICT` (the span shows it is false),",
        "`NEUTRAL` (the span says nothing decisive about *this* premise, including when it is",
        "about a different person, game, office, place or time), `UNSURE` (the premise is not",
        "truth-apt or you cannot tell). The context shows where the span sits in the document.",
        "",
    ]
    for it in items:
        blind += [
            f"### {it['id']} — case {it['case']}",
            "",
            f"- **Question:** {it['question']}",
            f"- **Reference answer:** {it['reference']}",
            f"- **Premise {it['premise_label']}:** {it['premise_text']}",
            f"- **Document:** *{it['document_title']}*",
            f"- **Span:** “{it['span']}”",
            "",
            f"> {it['context']}",
            "",
        ]
    cases_md = [
        "# RV2-0 Part 2 — case root causes",
        "",
        "Open this only after finishing Part 1 in `RV2_0_REVIEW.md`: it shows what the system",
        "concluded (but not what the RV1 assessor concluded).",
        "",
        "For each case write your own primary cause for each method in "
        f"`{cfg.responses_path.name}` (`human_primary_cause_*`), choosing one of:",
        "",
        ", ".join(f"`{c}`" for c in CAUSES),
        "",
        "Choose the earliest stage whose failure by itself explains the outcome. Then open",
        "`RV2_0_REVEAL.md` and record whether you agree with the RV1 conclusion.",
        "",
    ]
    for n in cfg.cases:
        cases_md += case_packet(by_order[n], docs)
    reveal = [
        "# RV2-0 — reveal (open only after answering Parts 1 and 2)",
        "",
        "## Part 1 — stance items",
        "",
        "| id | case | premise | span | system | RV1 | RV1 notes |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for it in items:
        note = (it["rv1_notes"] or "").replace("|", "/")
        span = it["span"][:70].replace("|", "/")
        premise = it["premise_text"][:60].replace("|", "/")
        reveal.append(
            f"| {it['id']} | {it['case']} | {premise} | {span} | {it['system_stance']} "
            f"| {it['rv1_stance']} | {note} |"
        )
    reveal += [
        "",
        "Items from the agreeing strata (SUPPORT→SUPPORT, NEUTRAL→NEUTRAL) are controls:",
        "they test whether you disagree where the system and the RV1 assessor agree.",
        "",
        "## Part 2 — RV1 root-cause conclusions",
        "",
    ]
    for n in cfg.cases:
        reveal += reveal_for_case(by_order[n])
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    cfg.responses_path.parent.mkdir(parents=True, exist_ok=True)
    (cfg.output_dir / "RV2_0_REVIEW.md").write_text("\n".join(blind) + "\n")
    (cfg.output_dir / "RV2_0_CASES.md").write_text("\n".join(cases_md) + "\n")
    (cfg.output_dir / "RV2_0_REVEAL.md").write_text("\n".join(reveal) + "\n")
    selection = {
        "protocol": PROTOCOL,
        "seed": cfg.seed,
        "strata_requested": [s.model_dump() for s in cfg.strata],
        "items": [
            {
                k: it[k]
                for k in (
                    "id",
                    "case",
                    "premise_label",
                    "span",
                    "system_stance",
                    "rv1_stance",
                    "stratum",
                    "rv1_premise_is_assertion",
                )
            }
            for it in items
        ],
        "cases": cfg.cases,
    }
    (cfg.output_dir / "rv2_0_selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    template = Responses(
        stance_items=[ItemResponse(id=it["id"]) for it in items],
        cases=[CaseResponse(case=n) for n in cfg.cases],
    )
    cfg.responses_path.write_text(
        "# RV2-0 responses. Fill human_stance with SUPPORT | CONTRADICT | NEUTRAL | UNSURE.\n"
        "# Cases: human_primary_cause_* (blind, before reveal) and agrees_with_rv1_* (after).\n"
        + yaml.safe_dump(template.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
    )
    return {
        "items": len(items),
        "cases": len(cfg.cases),
        "strata": dict(Counter(i["stratum"] for i in items)),
        "api_calls": 0,
    }


def agreement(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    determinate = [(a, b) for a, b in pairs if "UNSURE" not in (a, b)]
    return {
        "n": len(pairs),
        "unsure_excluded": len(pairs) - len(determinate),
        "agree": sum(a == b for a, b in determinate),
        "compared": len(determinate),
        "rate": round(sum(a == b for a, b in determinate) / len(determinate), 4)
        if determinate
        else None,
    }


def score_review(config_path: Path) -> dict[str, Any]:
    cfg = read_config(config_path)
    responses = Responses.model_validate(yaml.safe_load(cfg.responses_path.read_text()))
    selection = json.loads((cfg.output_dir / "rv2_0_selection.json").read_text())
    expected = {i["id"]: i for i in selection["items"]}
    given = {r.id: r for r in responses.stance_items}
    if set(given) != set(expected):
        raise ValueError("Responses do not match the committed selection")
    answered = {k: r for k, r in given.items() if r.human_stance is not None}
    disagree_strata = {
        "CONTRADICT->NEUTRAL",
        "CONTRADICT->SUPPORT",
        "SUPPORT->NEUTRAL",
        "NEUTRAL->SUPPORT",
    }
    groups: dict[str, list[tuple[str, str]]] = {
        "all": [],
        "rv1_disagreed_with_system": [],
        "rv1_agreed_with_system": [],
        "premise_is_assertion": [],
        "premise_is_not_assertion": [],
    }
    vs_system: list[tuple[str, str]] = []
    for k, r in answered.items():
        item = expected[k]
        human = str(r.human_stance)
        groups["all"].append((human, item["rv1_stance"]))
        key = (
            "rv1_disagreed_with_system"
            if item["stratum"] in disagree_strata
            else "rv1_agreed_with_system"
        )
        groups[key].append((human, item["rv1_stance"]))
        kind = (
            "premise_is_assertion"
            if item["rv1_premise_is_assertion"] == "YES"
            else "premise_is_not_assertion"
        )
        groups[kind].append((human, item["rv1_stance"]))
        vs_system.append((human, item["system_stance"]))
    case_rows = {c.case: c for c in responses.cases}
    cause_pairs = []
    for n in selection["cases"]:
        row = case_rows[n]
        for field, attr in (
            ("epistemic_search", row.human_primary_cause_epistemic_search),
            ("premise_only", row.human_primary_cause_premise_only),
        ):
            if attr is not None:
                cause_pairs.append((n, field, attr))
    report = {
        "protocol": PROTOCOL,
        "reviewer": responses.reviewer,
        "items_answered": f"{len(answered)}/{len(expected)}",
        "human_vs_rv1": {k: agreement(v) for k, v in groups.items()},
        "human_vs_system": agreement(vs_system),
        "reference_rate_for_straightforward_labels": REFERENCE_AGREEMENT,
        "note": (
            "Informational only: whether the RV1 labels are trusted enough to proceed is a "
            "human decision, not computed here."
        ),
        "cases_with_human_cause": len(cause_pairs),
        "cases_agree_with_rv1": dict(
            Counter(
                str(v)
                for row in responses.cases
                for v in (row.agrees_with_rv1_epistemic_search, row.agrees_with_rv1_premise_only)
                if v is not None
            )
        ),
        "api_calls": 0,
    }
    (cfg.output_dir / "rv2_0_score.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report
