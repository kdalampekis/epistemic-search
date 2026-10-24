"""Build a standalone local playback UI from validated saved experiments."""

import base64
import hashlib
import html
import json
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import Field

from epistemic_search.accounting import UsageLedger
from epistemic_search.baseline import RunResult
from epistemic_search.evaluation import file_hash
from epistemic_search.models import Schema, Text
from epistemic_search.statistics import read_run


class DashboardConfig(Schema):
    runs: Annotated[dict[Text, Path], Field(min_length=1)]
    output_dir: Path
    title: Text = "Epistemic Search"


def snapshots(result: RunResult) -> list[dict[str, Any]]:
    ledger = UsageLedger()
    graph: dict[str, Any] | None = None
    beliefs: list[Any] = []
    node_states: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    documents: dict[str, Any] = {}
    blockers: list[Any] = []
    decision: dict[str, Any] | None = None
    next_query: str | None = None
    views = []
    for event in result.trace:
        ledger.record(event)
        payload: Any = event.payload
        if event.type == "DECOMPOSE" and payload.get("graph"):
            graph = payload["graph"]
        elif event.type == "BELIEF_UPDATE":
            beliefs = payload["beliefs"]
        elif event.type == "EVIDENCE_ADDED":
            for item in payload.get("items", []):
                evidence[item["id"]] = item
        elif event.type == "SUFFICIENCY":
            blockers = payload.get("blockers", [])
            node_states = {node["node_id"]: node["status"] for node in payload.get("trace", [])}
        elif event.type == "DECISION":
            decision = payload.get("step", payload)
            blockers = decision.get("blocking_claims", blockers)
            if "query" in decision:
                next_query = decision["query"]
        elif event.type == "GENERATIVE_SUFFICIENCY":
            decision = payload
            blockers = [payload["target_claim_id"]] if payload.get("target_claim_id") else []
        elif event.type == "QUERY_GENERATED":
            next_query = payload.get("query")
        elif event.type == "SEARCH":
            next_query = None
            response = payload.get("response", payload)
            for document in response.get("results", []):
                documents[document["source"]["id"]] = document
        views.append(
            {
                "event": {"id": event.id, "type": event.type, "component": event.component},
                "graph": graph,
                "beliefs": beliefs,
                "evidence": list(evidence.values()),
                "node_states": node_states,
                "documents": list(documents.values()),
                "blockers": blockers,
                "decision": decision,
                "next_query": next_query,
                "usage": ledger.total().model_dump(mode="json"),
            }
        )
    if ledger.total() != result.usage:
        raise ValueError("Dashboard cannot replay a trace whose usage differs from its total")
    return views


def build_dashboard(config_path: Path) -> dict[str, object]:
    config = DashboardConfig.model_validate(yaml.safe_load(config_path.read_text()))
    cases = []
    sources = {}
    for name, relative in config.runs.items():
        root = (config_path.parent / relative).resolve()
        run = read_run(root)
        sources[name] = dict(run.hashes)
        for case_id, row in run.rows.items():
            path = (root / row.trace_file).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Dashboard trace path escapes its run directory")
            result = RunResult.model_validate_json(path.read_text())
            if (
                result.query_id != case_id
                or result.usage != row.usage
                or result.status != row.status
            ):
                raise ValueError("Dashboard trace differs from its scored case")
            sources[name][row.trace_file] = file_hash(path)
            cases.append(
                {
                    "id": case_id,
                    "run": name,
                    "question": run.labels[case_id].question,
                    "method": run.manifest.get("method"),
                    "fixture_only": run.manifest.get("fixture_only", True),
                    "model": run.manifest["config"]["rag"]["model"],
                    "reasoning_effort": run.manifest["config"]["rag"].get("reasoning_effort"),
                    "budget": run.manifest["config"]["budget"],
                    "status": result.status,
                    "output": result.output.model_dump(mode="json") if result.output else None,
                    "error": result.error,
                    "usage_complete": result.usage_complete,
                    "wall_seconds": result.wall_seconds,
                    "snapshots": snapshots(result),
                    "events": [event.model_dump(mode="json") for event in result.trace],
                }
            )
    if not cases or any(not case["snapshots"] for case in cases):
        raise ValueError("Dashboard needs nonempty saved traces")
    static = Path(__file__).with_name("static")
    script = (static / "dashboard.js").read_text()
    css = (static / "dashboard.css").read_text()
    encoded = json.dumps({"title": config.title, "cases": cases}, ensure_ascii=True)
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        f"script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'\">"
        f"<title>{html.escape(config.title)} — Run inspector</title>"
        f"<style>{css}</style></head><body>"
        '<header><div><span class="eyebrow">RESEARCH WORKSPACE</span><h1 id="title"></h1></div>'
        '<span class="offline">● Local trace playback · no API calls</span></header>'
        '<aside aria-label="Case selection"><label for="filter">Find a question or run</label>'
        '<input id="filter" type="search" placeholder="Search saved cases…">'
        '<p id="case-count" class="muted"></p>'
        '<nav id="case-list" aria-label="Saved cases"></nav></aside>'
        '<main><section class="question"><div id="case-meta" class="eyebrow"></div>'
        '<h2 id="question"></h2><p id="model" class="muted"></p></section>'
        '<section class="playback panel" aria-label="Trace playback"><div class="row">'
        '<h3>Follow the evidence</h3><span id="step-label"></span></div>'
        '<div class="controls"><button id="previous" aria-label="Previous event">←</button>'
        '<input id="step" type="range" min="0" value="0" aria-label="Trace event">'
        '<button id="next" aria-label="Next event">→</button></div>'
        '<p id="event-label"></p></section>'
        '<section id="usage" class="metrics" aria-label="Cumulative resource use"></section>'
        '<div class="columns"><section class="panel"><h3>Premise graph</h3>'
        '<p class="muted">Derivability from an extracted model. Belief scores are uncalibrated.</p>'
        '<div class="legend"><span class="supported">Supported</span>'
        '<span class="contradicted">Contradicted</span>'
        '<span class="mixed">Mixed</span><span class="unknown">Unknown / unrecorded</span></div>'
        '<div id="graph" class="graph"></div><div id="beliefs"></div></section>'
        '<section class="panel"><h3>Decision at this step</h3><div id="decision"></div>'
        '<h4>Blocking claims</h4><div id="blockers"></div><h4>Planned query</h4>'
        '<p id="query"></p><hr><h3>Recorded final outcome</h3>'
        '<div id="answer"></div></section></div>'
        '<section class="panel"><h3>Evidence and provenance</h3><div id="evidence"></div></section>'
        '<details class="panel"><summary>Inspect the selected event</summary>'
        '<pre id="raw-event"></pre></details>'
        '<p class="footnote">Replay of saved outputs. The interface is not evidence '
        "of scientific validity.</p></main>"
        f'<script id="trace-data" type="application/json">{encoded}</script>'
        f"<script>{script}</script>"
        "</body></html>\n"
    )
    report: dict[str, object] = {
        "protocol": "local-saved-trace-dashboard-v1",
        "cases": len(cases),
        "runs": len(config.runs),
        "source_hashes": sources,
        "config_sha256": file_hash(config_path),
        "implementation_sha256": file_hash(Path(__file__)),
        "script_sha256": file_hash(static / "dashboard.js"),
        "style_sha256": file_hash(static / "dashboard.css"),
        "html_sha256": hashlib.sha256(page.encode()).hexdigest(),
        "additional_api_calls": 0,
        "additional_api_cost_usd": "0",
    }
    output = config_path.parent / config.output_dir
    output.mkdir(parents=True, exist_ok=False)
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
