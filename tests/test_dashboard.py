import asyncio
import base64
import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml
from test_engine import ScenarioModel, ScenarioSearch, config
from test_failures import setup_run
from typer.testing import CliRunner

from epistemic_search.cli import app
from epistemic_search.dashboard import build_dashboard, snapshots
from epistemic_search.engine import run_epistemic
from epistemic_search.models import QueryCase, Source


def test_playback_has_no_future_evidence_and_conserves_usage(
    tmp_path: Path, source: Source
) -> None:
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="question"),
            config(),
            ScenarioSearch("B", source),
            ScenarioModel(),
            tmp_path,
        )
    )
    views = snapshots(result)
    assert len(views) == len(result.trace)
    assert views[0]["graph"] is None and views[0]["evidence"] == []
    assert views[-1]["usage"] == result.usage.model_dump(mode="json")
    assert views[-1]["decision"]["action"] == "ANSWER"
    query_index = next(i for i, e in enumerate(result.trace) if e.type == "QUERY_GENERATED")
    assert views[query_index]["next_query"].startswith("Beta holds.")
    search_index = next(
        i for i in range(query_index + 1, len(result.trace)) if result.trace[i].type == "SEARCH"
    )
    assert views[search_index]["next_query"] is None
    assert len(views[query_index]["evidence"]) < len(views[-1]["evidence"])
    result.usage.model_calls += 1
    with pytest.raises(ValueError, match="usage differs"):
        snapshots(result)


def test_dashboard_cli_contains_all_cases_and_exact_csp_hash(tmp_path: Path) -> None:
    setup_run(tmp_path)
    path = tmp_path / "dashboard.yaml"
    path.write_text(yaml.safe_dump({"runs": {"fixture": "run"}, "output_dir": "dashboard"}))
    result = CliRunner().invoke(app, ["dashboard", str(path)])
    assert result.exit_code == 0, result.output
    page = (tmp_path / "dashboard/index.html").read_text()
    data_match = re.search(
        r'<script id="trace-data" type="application/json">(.*?)</script>', page, re.S
    )
    assert data_match
    data = json.loads(data_match[1])
    assert len(data["cases"]) == 2
    assert all("gold_answer" not in case for case in data["cases"])
    script = page.split("</script><script>")[1].split("</script>")[0]
    encoded = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    assert f"script-src 'sha256-{encoded}'" in page
    manifest = json.loads((tmp_path / "dashboard/manifest.json").read_text())
    assert manifest["additional_api_calls"] == 0
    assert manifest["html_sha256"] == hashlib.sha256(page.encode()).hexdigest()
    with pytest.raises(FileExistsError):
        build_dashboard(path)


def test_dashboard_escapes_script_terminators_in_saved_text(tmp_path: Path) -> None:
    setup_run(tmp_path)
    labels = tmp_path / "run/labels.jsonl"
    rows = [json.loads(line) for line in labels.read_text().splitlines()]
    rows[0]["question"] = "</script><script>globalThis.pwned=true</script>"
    labels.write_text("".join(json.dumps(row) + "\n" for row in rows))
    path = tmp_path / "dashboard.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "runs": {"fixture": "run"},
                "output_dir": "dashboard",
                "title": "<script>title</script>",
            }
        )
    )
    build_dashboard(path)
    page = (tmp_path / "dashboard/index.html").read_text()
    assert "<script>globalThis.pwned" not in page
    assert "\\u003c/script\\u003e" in page
    assert "<title>&lt;script&gt;title&lt;/script&gt;" in page


def test_dashboard_refuses_trace_path_escape(tmp_path: Path) -> None:
    setup_run(tmp_path)
    examples = tmp_path / "run/examples.jsonl"
    rows = [json.loads(line) for line in examples.read_text().splitlines()]
    rows[0]["trace_file"] = "../outside.json"
    examples.write_text("".join(json.dumps(row) + "\n" for row in rows))
    path = tmp_path / "dashboard.yaml"
    path.write_text(yaml.safe_dump({"runs": {"fixture": "run"}, "output_dir": "dashboard"}))
    with pytest.raises(ValueError, match="escapes"):
        build_dashboard(path)
    assert not (tmp_path / "dashboard").exists()
