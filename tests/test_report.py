import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("render_report", Path("scripts/render_report.py"))
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
render = module.render


def test_report_values_and_tables_bind_to_sources(tmp_path: Path) -> None:
    base = tmp_path / "docs/paper"
    base.mkdir(parents=True)
    (base / "scores.json").write_text(json.dumps({"n": 3, "missing": None}))
    (base / "table.md").write_text("| score |\n| --- |\n| NA |\n")
    template = base / "REPORT.template.md"
    template.write_text(
        "# Fixture\n\nN={{value:scores.json#/n}}; "
        "missing={{value:scores.json#/missing}}\n\n{{include:table.md}}\n\n<script>bad()</script>"
    )
    markdown, html, sources = render(template)
    assert "N=3; missing=NA" in markdown
    assert "<table>" in html and "<script>bad()" not in html
    assert set(sources) == {
        "docs/paper/REPORT.template.md",
        "docs/paper/scores.json",
        "docs/paper/table.md",
    }
    assert render(template) == (markdown, html, sources)
    (base / "scores.json").write_text(json.dumps({"n": 4, "missing": None}))
    assert "N=4" in render(template)[0]


def test_report_rejects_unresolved_tokens_and_external_sources(tmp_path: Path) -> None:
    base = tmp_path / "docs/paper"
    base.mkdir(parents=True)
    template = base / "REPORT.template.md"
    for text, error in [
        ("{{unknown:x}}", "Unresolved"),
        ("{{include:../../../outside.md}}", "within"),
        ("{{include:../../.env}}", "environment"),
    ]:
        template.write_text(text)
        with pytest.raises(ValueError, match=error):
            render(template)
