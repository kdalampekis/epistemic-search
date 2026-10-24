"""Offline trace inspection and provisional failure-stage classification."""

import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import Field, model_validator

from epistemic_search.baseline import RunResult
from epistemic_search.evaluation import JsonlDataset, ScoredCase, Summary, file_hash
from epistemic_search.models import QueryCase, Schema, Text

Category = Literal[
    "DECOMPOSITION_ERROR",
    "RETRIEVAL_ERROR",
    "EVIDENCE_EXTRACTION_ERROR",
    "STANCE_ERROR",
    "BELIEF_AGGREGATION_ERROR",
    "FORMALIZATION_ERROR",
    "CONTROLLER_ERROR",
    "ANSWER_GENERATION_ERROR",
    "CALIBRATION_ERROR",
    "BENCHMARK_AMBIGUITY",
]
RunName = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class FailureJudgment(Schema):
    run: RunName
    query_id: Text
    trace_sha256: Hash
    primary: Category
    secondary: list[Category] = Field(default_factory=list)
    rationale: Text

    @model_validator(mode="after")
    def distinct_categories(self) -> Self:
        if self.primary in self.secondary or len(set(self.secondary)) != len(self.secondary):
            raise ValueError("Primary and secondary failure categories must be distinct")
        return self


class FailureJudgments(Schema):
    assessor: Text
    protocol: Text
    cases: list[FailureJudgment]

    @model_validator(mode="after")
    def unique_cases(self) -> Self:
        if len({(c.run, c.query_id) for c in self.cases}) != len(self.cases):
            raise ValueError("Failure judgments must have unique run/case keys")
        return self


class FailureConfig(Schema):
    runs: Annotated[dict[RunName, Path], Field(min_length=1)]
    output_dir: Path
    judgments_path: Path | None = None


class Classification(Schema):
    run: RunName
    query_id: Text
    trace_sha256: Hash
    outcome: Literal[
        "execution_error",
        "answer_mismatch",
        "reference_match",
        "ungraded_answer",
        "abstention",
        "budget_stop",
    ]
    primary: Category | None
    secondary: list[Category] = Field(default_factory=list)
    basis: Literal["observed_stage", "output_symptom", "manual", "not_classified"]
    rationale: Text
    needs_review: bool
    assessor: Text | None = None
    protocol: Text | None = None


def classify(run: str, result: RunResult, row: ScoredCase, trace_hash: str) -> Classification:
    outcome: Literal[
        "execution_error",
        "answer_mismatch",
        "reference_match",
        "ungraded_answer",
        "abstention",
        "budget_stop",
    ]
    if result.status == "error":
        outcome = "execution_error"
    elif result.status == "budget_exhausted":
        outcome = "budget_stop"
    elif not row.answered:
        outcome = "abstention"
    elif row.exact_match is None:
        outcome = "ungraded_answer"
    else:
        outcome = "reference_match" if row.exact_match == 1 else "answer_mismatch"
    primary: Category | None = None
    basis: Literal["observed_stage", "output_symptom", "manual", "not_classified"] = (
        "not_classified"
    )
    explanation = (
        "No failure inferred: abstention, budget stop or ungraded output "
        "is not automatically an error."
    )
    if outcome == "reference_match":
        explanation = (
            "Matches the recorded reference; does not establish reasoning or real-world truth."
        )
    if outcome in {"execution_error", "answer_mismatch"}:
        primary = "ANSWER_GENERATION_ERROR"
        basis = "output_symptom"
        explanation = (
            "Failed final output or reference mismatch; upstream root cause "
            "and benchmark ambiguity need review."
        )
    if outcome == "execution_error":
        stages: dict[str, Category] = {
            "decomposition": "DECOMPOSITION_ERROR",
            "retrieval": "RETRIEVAL_ERROR",
            "search": "RETRIEVAL_ERROR",
            "evidence": "EVIDENCE_EXTRACTION_ERROR",
            "control": "CONTROLLER_ERROR",
            "answering": "ANSWER_GENERATION_ERROR",
        }
        for event in result.trace:
            category: Category | None = None
            if event.type == "SEARCH_ERROR":
                category = "RETRIEVAL_ERROR"
            elif event.type == "MODEL_ERROR":
                category = stages.get(event.component)
            elif event.type == "EVIDENCE_ADDED" and event.payload.get("errors"):
                category = "EVIDENCE_EXTRACTION_ERROR"
            elif event.type == "DECOMPOSE" and event.payload.get("error"):
                category = "DECOMPOSITION_ERROR"
            if category:
                primary, basis = category, "observed_stage"
                explanation = (
                    f"Trace event {event.id} records failure in {category}; "
                    "semantic root cause is not established."
                )
        if result.error and result.error.startswith("Decomposition artifact failed"):
            primary, basis = "DECOMPOSITION_ERROR", "observed_stage"
            explanation = (
                "Decomposition artifact failed to load or validate; inspect the retained error."
            )
        if result.error and result.error.startswith("Reasoner could not produce an exact result"):
            primary, basis = "FORMALIZATION_ERROR", "observed_stage"
            explanation = (
                "Structured reasoner rejected the model or hit its exact-frontier limit; "
                "not proof of semantic invalidity."
            )
    return Classification(
        run=run,
        query_id=row.query_id,
        trace_sha256=trace_hash,
        outcome=outcome,
        primary=primary,
        basis=basis,
        rationale=explanation,
        needs_review=primary is not None,
    )


def fenced(value: str) -> str:
    longest = max((len(m.group()) for m in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{value}\n{fence}"


def render_example(
    case: QueryCase, row: ScoredCase, result: RunResult, classification: Classification
) -> tuple[str, str]:
    sections = {
        "Question (evaluator view)": case.question,
        "Recorded gold / answerability": json.dumps(
            {"gold_answer": case.gold_answer, "answerable": case.answerable},
            ensure_ascii=False,
            indent=2,
        ),
        "Outcome and provisional classification": classification.model_dump_json(indent=2),
        "Final answer / stop": json.dumps(
            {
                "status": result.status,
                "output": result.output.model_dump(mode="json") if result.output else None,
                "decision": result.decision.model_dump(mode="json") if result.decision else None,
                "error": result.error,
            },
            ensure_ascii=False,
            indent=2,
        ),
        "Recorded scores and resources": row.model_dump_json(indent=2),
        "Final evidence state": result.state.model_dump_json(indent=2, exclude={"trace"})
        if result.state
        else "No explicit evidence state recorded by this method.",
    }
    title = f"{classification.run}: {case.id}"
    intro = (
        "Offline saved trace. Automatic categories identify observable failure stages or output "
        "symptoms, not verified root causes. Gold labels are shown only in this evaluator view."
    )
    markdown = ["# Trace inspection", fenced(title), intro]
    body = [f"<h1>{html.escape(title)}</h1><p>{html.escape(intro)}</p>"]
    for name, text in sections.items():
        markdown.extend(["## " + name, fenced(text)])
        body.append(
            f"<section><h2>{html.escape(name)}</h2><pre>{html.escape(text)}</pre></section>"
        )
    markdown.append("## Event timeline")
    body.append("<h2>Event timeline</h2>")
    for index, event in enumerate(result.trace):
        label = f"{index + 1}. {event.type} / {event.component} / {event.timestamp.isoformat()}"
        text = event.model_dump_json(indent=2)
        markdown.extend([fenced(label), fenced(text)])
        body.append(
            f"<details><summary>{html.escape(label)}</summary>"
            f"<pre>{html.escape(text)}</pre></details>"
        )
    return "\n\n".join(markdown) + "\n", html_document(title, "".join(body))


def html_document(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        f"<title>{html.escape(title)}</title><style>"
        "body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#17212b}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f7;padding:1rem}"
        "summary{cursor:pointer;padding:.6rem;border-bottom:1px solid #ccd4dd}"
        "table{border-collapse:collapse}th,td{padding:.5rem;"
        "text-align:left;border:1px solid #ccd4dd}"
        "a{color:#174ea6}</style></head><body>" + body + "</body></html>\n"
    )


def analyze_failures(config_path: Path) -> dict[str, object]:
    config = FailureConfig.model_validate(yaml.safe_load(config_path.read_text()))
    judgments = (
        FailureJudgments.model_validate_json(
            (config_path.parent / config.judgments_path).read_text()
        )
        if config.judgments_path
        else None
    )
    annotations = {(a.run, a.query_id): a for a in judgments.cases} if judgments else {}
    loaded: list[tuple[QueryCase, ScoredCase, RunResult, Classification]] = []
    source_hashes: dict[str, dict[str, str]] = {}
    partial: dict[str, str | None] = {}
    inventories: dict[str, dict[str, int]] = {}
    for name, relative in config.runs.items():
        root = (config_path.parent / relative).resolve()
        labels = {case.id: case for case in JsonlDataset(root / "labels.jsonl").load()}
        rows = [
            ScoredCase.model_validate_json(line)
            for line in (root / "examples.jsonl").read_text().split("\n")
            if line.strip()
        ]
        summary = Summary.model_validate_json((root / "summary.json").read_text())
        if len({r.query_id for r in rows}) != len(rows) or summary.examples != len(rows):
            raise ValueError("Saved scores need unique IDs and matching summary counts")
        if set(r.query_id for r in rows) - labels.keys():
            raise ValueError("Saved scores are missing labels")
        if len(rows) != len(labels) and not summary.stop_reason:
            raise ValueError("Missing cases require an explicit partial-run stop reason")
        partial[name] = summary.stop_reason
        inventories[name] = {"planned": len(labels), "executed": len(rows)}
        source_hashes[name] = {
            p: file_hash(root / p)
            for p in ("manifest.json", "labels.jsonl", "examples.jsonl", "summary.json")
        }
        for row in rows:
            trace_path = (root / row.trace_file).resolve()
            if not trace_path.is_relative_to(root):
                raise ValueError("Trace path escapes its run directory")
            result = RunResult.model_validate_json(trace_path.read_text())
            if (
                result.query_id != row.query_id
                or result.status != row.status
                or result.usage != row.usage
                or result.usage_complete != row.usage_complete
            ):
                raise ValueError("Trace identity/status/usage differs from scored row")
            answered = (
                result.status == "completed"
                and result.output is not None
                and result.output.answer is not None
            )
            if answered != row.answered:
                raise ValueError("Trace answer presence differs from scored row")
            trace_hash = file_hash(trace_path)
            source_hashes[name][row.trace_file] = trace_hash
            classification = classify(name, result, row, trace_hash)
            annotation = annotations.pop((name, row.query_id), None)
            if annotation:
                assert judgments
                if annotation.trace_sha256 != trace_hash:
                    raise ValueError("Manual judgment references a different trace hash")
                classification.primary = annotation.primary
                classification.secondary = annotation.secondary
                classification.rationale = annotation.rationale
                classification.basis = "manual"
                classification.needs_review = False
                classification.assessor = judgments.assessor
                classification.protocol = judgments.protocol
            loaded.append((labels[row.query_id], row, result, classification))
    if annotations:
        raise ValueError("Manual judgments reference absent run/case keys")
    output = config_path.parent / config.output_dir
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    links, md_links = [], []
    for index, (case, row, result, classification) in enumerate(loaded):
        markdown, page = render_example(case, row, result, classification)
        stem = f"cases/{index:06}"
        (output / (stem + ".md")).write_text(markdown, encoding="utf-8")
        (output / (stem + ".html")).write_text(page, encoding="utf-8")
        label = (
            f"{classification.run}: {case.id} — {classification.outcome} / "
            f"{classification.primary or 'unclassified'}"
        )
        links.append(f'<li><a href="{stem}.html">{html.escape(label)}</a></li>')
        md_links.append(f"- [{index + 1}]({stem}.md)\n\n" + fenced(label))
    (output / "index.html").write_text(
        html_document(
            "Saved trace inspection",
            "<h1>Saved trace inspection</h1><p>All executed cases, including abstentions "
            "and errors. Automatic categories need review.</p><ul>" + "".join(links) + "</ul>",
        )
    )
    (output / "index.md").write_text("# Saved trace inspection\n\n" + "\n".join(md_links) + "\n")
    classifications = [item[3] for item in loaded]
    (output / "classifications.jsonl").write_text(
        "".join(c.model_dump_json() + "\n" for c in classifications)
    )
    report: dict[str, object] = {
        "protocol": "provisional-failure-stage-v1",
        "examples": len(loaded),
        "outcomes": dict(Counter(c.outcome for c in classifications)),
        "primary_categories": dict(Counter(c.primary for c in classifications if c.primary)),
        "automatic_needs_review": sum(c.needs_review for c in classifications),
        "manual_judgments": sum(c.basis == "manual" for c in classifications),
        "partial_runs": partial,
        "inventories": inventories,
        "source_hashes": source_hashes,
        "config_sha256": file_hash(config_path),
        "implementation_sha256": file_hash(Path(__file__)),
        "judgments_sha256": file_hash(config_path.parent / config.judgments_path)
        if config.judgments_path
        else None,
        "additional_api_calls": 0,
        "additional_api_cost_usd": "0",
        "limitations": [
            "Automatic classification locates symptoms/stages, not verified semantic root causes.",
            "Wrong answers get a provisional output category; upstream cause remains unresolved.",
            "Abstention/budget stop is not an error; independent answerability review is needed.",
            "Manual labels bind to exact trace hashes and preserve assessor/protocol provenance.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
