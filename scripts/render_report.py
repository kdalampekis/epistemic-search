"""Render the technical report from prose plus checked result inclusions."""

import argparse
import hashlib
import importlib
import json
import re
from pathlib import Path
from typing import Any

TOKEN = re.compile(r"\{\{(include|value):([^}]+)\}\}")


def render(template: Path) -> tuple[str, str, dict[str, str]]:
    base = template.parent
    repository = base.parents[1]
    sources = {
        str(template.relative_to(repository)): hashlib.sha256(template.read_bytes()).hexdigest()
    }

    def read(relative: str) -> str:
        path = (base / relative).resolve()
        if not path.is_relative_to(repository.resolve()) or any(
            p.startswith(".env") for p in path.parts
        ):
            raise ValueError(
                "Report source must stay within the repository and exclude environment files"
            )
        sources[str(path.relative_to(repository.resolve()))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        return path.read_text()

    def replace(match: re.Match[str]) -> str:
        kind, source = match.groups()
        if kind == "include":
            return read(source).rstrip()
        path, pointer = source.split("#", 1)
        value: Any = json.loads(read(path))
        for key in pointer.lstrip("/").split("/"):
            value = value[int(key)] if isinstance(value, list) else value[key]
        if isinstance(value, (dict, list)):
            raise ValueError("Inline report values must be scalars")
        return "NA" if value is None else str(value)

    markdown = TOKEN.sub(replace, template.read_text())
    if "{{" in markdown or "}}" in markdown:
        raise ValueError("Unresolved report template token")
    for target in re.findall(r"\]\(([^)]+)\)", markdown):
        if not target.startswith(("https://", "http://", "#")):
            read(target.split("#")[0]) if Path(target).suffix not in {".png", ".pdf"} else None
            path = (base / target).resolve()
            if not path.exists():
                raise ValueError(f"Missing report link: {target}")
            sources[str(path.relative_to(repository.resolve()))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    module = importlib.import_module("markdown_it")
    body = module.MarkdownIt("commonmark", {"html": False}).enable("table").render(markdown)
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "img-src 'self' data:; style-src 'unsafe-inline'\">"
        "<title>Epistemic Search — Technical Report</title><style>"
        "body{font:16px/1.5 Georgia,serif;max-width:1000px;"
        "margin:3rem auto;padding:0 1.5rem;color:#17212b}"
        "h1,h2,h3{font-family:system-ui;line-height:1.2}h1{font-size:2rem}h2{margin-top:2rem}"
        "table{border-collapse:collapse;font:12px/1.35 system-ui;width:100%;margin:1rem 0}"
        "th,td{padding:6px;border-bottom:1px solid #bbb;text-align:left;overflow-wrap:anywhere}"
        "img{max-width:100%;height:auto}code,pre{font-size:12px;overflow-wrap:anywhere;white-space:pre-wrap}"
        "a{color:#155d72}thead{display:table-header-group}tr,img{break-inside:avoid}"
        "@page{size:A4;margin:16mm}@media print{"
        "body{font-size:10pt;margin:0;padding:0;max-width:none}"
        "h1{font-size:20pt}h2{font-size:14pt;break-after:avoid}h3{font-size:11pt;break-after:avoid}"
        "table{font-size:8pt}a{color:inherit;text-decoration:none}}"
        "</style></head><body>" + body + "</body></html>\n"
    )
    return markdown, html, sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    base = root / "docs/paper"
    markdown, html, sources = render(base / "REPORT.template.md")
    outputs = {"REPORT.md": markdown, "REPORT.html": html}
    manifest = {
        "protocol": "result-bound-technical-report-v1",
        "sources": sources,
        "renderer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "outputs": {
            name: hashlib.sha256(text.encode()).hexdigest() for name, text in outputs.items()
        },
    }
    outputs["report-manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    for name, text in outputs.items():
        path = base / name
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f"Report is stale: {name}")
        else:
            path.write_text(text)
    print("Technical report verified" if args.check else "Technical report generated")


if __name__ == "__main__":
    main()
