import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from epistemic_search.adapters import FixtureModelProvider
from epistemic_search.cli import app
from epistemic_search.config import load_config
from epistemic_search.decomposition import DecompositionDraft, ProofGraph, decompose
from epistemic_search.models import QueryCase


def draft() -> DecompositionDraft:
    return DecompositionDraft.model_validate_json(
        Path("tests/fixtures/decomposition_gold.json").read_text()
    )


def test_ids_stable_under_alias_and_order_changes() -> None:
    original = draft()
    changed = original.model_copy(deep=True)
    changed.claims.reverse()
    changed.nodes.reverse()
    for claim in changed.claims:
        claim.id = "alias-" + claim.id
    for node in changed.nodes:
        node.id = "alias-" + node.id
        node.children = ["alias-" + c for c in reversed(node.children)]
        if node.claim_id is not None:
            node.claim_id = "alias-" + node.claim_id
    changed.conclusion_id = "alias-" + changed.conclusion_id
    assert original.graph() == changed.graph()
    assert ProofGraph.model_validate_json(original.graph().model_dump_json()) == original.graph()


@pytest.mark.parametrize(
    "problem",
    ["cycle", "dangling", "disconnected", "arity", "duplicate", "claim_ref", "duplicate_text"],
)
def test_invalid_graphs_rejected(problem: str) -> None:
    value = draft()
    if problem == "cycle":
        value.nodes[2].children = ["root", "nb"]
    elif problem == "dangling":
        value.nodes[2].children = ["missing", "nb"]
    elif problem == "disconnected":
        value.nodes[-1].children = ["na"]
    elif problem == "arity":
        value.nodes[2].kind = "NOT"
    elif problem == "duplicate":
        value.nodes.append(value.nodes[0])
    elif problem == "claim_ref":
        value.nodes[0].claim_id = "missing"
    else:
        value.claims[1].text = value.claims[0].text
    with pytest.raises((ValueError, ValidationError)):
        value.graph()


def test_cache_retains_origin_but_charges_zero_and_invalidates_request(tmp_path: Path) -> None:
    config = load_config(Path("configs/decomposition_fixture.yaml"))
    case = QueryCase(id="q", question="Capital and continent?", gold_answer="SECRET")
    model = FixtureModelProvider([draft().model_dump_json()])
    first = asyncio.run(decompose(case, config, model, tmp_path))
    assert first.graph is not None and first.usage.model_calls == 1
    assert "SECRET" not in first.request.prompt
    second = asyncio.run(decompose(case, config, model, tmp_path))
    assert second.cache_hit and second.usage.model_calls == 0
    assert second.response is not None and second.response.usage.model_calls == 1
    assert first.graph == second.graph
    config.seed += 1
    third = asyncio.run(decompose(case, config, model, tmp_path))
    assert not third.cache_hit and third.error is not None  # Empty fixture script is called again.


def test_invalid_output_preserves_usage_without_caching(tmp_path: Path) -> None:
    result = asyncio.run(
        decompose(
            QueryCase(id="q", question="question"),
            load_config(Path("configs/decomposition_fixture.yaml")),
            FixtureModelProvider(["bad JSON"]),
            tmp_path,
        )
    )
    assert result.error is not None and result.usage.model_calls == 1
    assert list(tmp_path.iterdir()) == []


def test_decomposition_cli(tmp_path: Path) -> None:
    import yaml

    cfg = yaml.safe_load(Path("configs/decomposition_fixture.yaml").read_text())
    cfg["rag"]["responses_path"] = str(
        Path("tests/fixtures/decomposition_responses.json").resolve()
    )
    cfg["decomposition"]["cache_dir"] = str(tmp_path / "cache")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(cfg))
    output = tmp_path / "result.json"
    result = CliRunner().invoke(
        app, ["decompose", str(config_path), "tests/fixtures/decomposition_query.json", str(output)]
    )
    assert result.exit_code == 0, result.output
    saved = json.loads(output.read_text())
    assert saved["request"]["prompt_version"] == "premise-decomposition-v1"
    assert len(saved["graph"]["claims"]) == 2
