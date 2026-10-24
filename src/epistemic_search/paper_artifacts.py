"""Generate paper tables, figures and outcome-stratified traces from saved runs."""

import csv
import hashlib
import importlib
import importlib.metadata
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, Literal

import yaml
from pydantic import Field

from epistemic_search.baseline import RunResult
from epistemic_search.evaluation import file_hash
from epistemic_search.failures import RunName, classify, fenced
from epistemic_search.models import Count, Schema
from epistemic_search.statistics import StatisticsConfig, analyze_comparison, distribution, read_run


class PaperGroup(Schema):
    statistics_config: Path
    kind: Literal["comparison", "ablation"] = "comparison"


class PaperConfig(Schema):
    groups: Annotated[dict[RunName, PaperGroup], Field(min_length=1)]
    output_dir: Path
    selection_seed: Count = 42


def display(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def tex(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(c, c) for c in value)


def write_table(path: Path, rows: list[dict[str, Any]], caption: str) -> None:
    if not rows:
        return
    fields = list(rows[0])
    with path.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    values = [[display(row[key]) for key in fields] for row in rows]

    def md(cells: list[str]) -> str:
        return "| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |"

    path.with_suffix(".md").write_text(
        caption
        + "\n\n"
        + "\n".join([md(fields), md(["---"] * len(fields))] + [md(row) for row in values])
        + "\n"
    )
    lines = [r"\begin{tabular}{" + "l" * len(fields) + "}", r"\hline"]
    lines += [" & ".join(tex(c) for c in row) + r" \\" for row in [fields, *values]]
    lines += [r"\hline", r"\end{tabular}"]
    path.with_suffix(".tex").write_text(
        "% " + caption.replace("\n", " ") + "\n" + "\n".join(lines) + "\n"
    )


def plot_report(report: dict[str, Any], output: Path, title: str) -> None:
    mpl = importlib.import_module("matplotlib")
    mpl.use("Agg")
    plt = importlib.import_module("matplotlib.pyplot")
    with plt.rc_context({"svg.hashsalt": "epistemic-paper-v1", "svg.fonttype": "none"}):
        names = list(report["runs"])
        fig, axes = plt.subplots(
            1, 2, figsize=(10, max(3.4, len(names) * 0.42)), layout="constrained"
        )
        for ax, metric, label in zip(
            axes, ("coverage", "token_f1"), ("Answer coverage", "Token F1"), strict=True
        ):
            for y, name in enumerate(names):
                m = report["runs"][name]["metrics"][metric]
                if m["mean"] is None:
                    ax.text(0.02, y, "Unavailable: no answer labels", va="center", fontsize=8)
                    continue
                ax.plot(m["mean"], y, "o", color="#23736a")
                if m["lower"] is not None:
                    ax.hlines(y, m["lower"], m["upper"], color="#23736a", linewidth=2)
            ax.set(yticks=range(len(names)), yticklabels=names, xlim=(-0.02, 1.02), xlabel=label)
            ax.set_ylim(len(names) - 0.5, -0.5)
            ax.grid(axis="x", alpha=0.2)
        confidence = report["config"]["confidence"]
        fig.suptitle(
            title
            + f"\n{confidence:.0%} marginal cluster bootstrap intervals; small-sample exploratory"
            "\nIntervals unavailable with fewer than two question groups."
        )
        fig.savefig(output.with_suffix(".svg"), metadata={"Date": None})
        fig.savefig(output.with_suffix(".pdf"), metadata={"CreationDate": None, "ModDate": None})
        fig.savefig(output.with_suffix(".png"), dpi=180)
        plt.close(fig)


def generate_paper_artifacts(config_path: Path) -> dict[str, Any]:
    config = PaperConfig.model_validate(yaml.safe_load(config_path.read_text()))
    output = config_path.parent / config.output_dir
    if output.exists():
        raise FileExistsError(output)
    try:
        version = importlib.metadata.version("matplotlib")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ValueError("Paper figures require uv sync --extra paper") from exc
    sources: dict[str, Any] = {}
    inventory: list[dict[str, Any]] = []
    datasets: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="epistemic-paper-") as temporary:
        root = Path(temporary)
        for name, group in config.groups.items():
            stats_path = config_path.parent / group.statistics_config
            stats = StatisticsConfig.model_validate(yaml.safe_load(stats_path.read_text()))
            folder = root / name
            folder.mkdir()
            report = analyze_comparison(stats_path, output_path=folder / "statistics.json")
            title = name + (
                " — SCRIPTED FIXTURE (not model quality)"
                if report["fixture_only"]
                else " — saved model pilot"
            )
            rows: list[dict[str, Any]] = []
            resource_rows: list[dict[str, Any]] = []
            candidates: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
            sources[name] = {"statistics_config_sha256": file_hash(stats_path), "runs": {}}
            for method, relative in stats.runs.items():
                run_path = (stats_path.parent / relative).resolve()
                run = read_run(run_path)
                sources[name]["runs"][method] = dict(run.hashes)
                s = run.summary
                models = run.manifest["config"]["rag"]
                rows.append(
                    {
                        "method": method,
                        "n": s.examples,
                        "EM": s.exact_match,
                        "F1": s.token_f1,
                        "coverage": s.coverage,
                        "selective_EM_risk": (
                            sum(
                                1 - r.exact_match
                                for r in run.rows.values()
                                if r.answered and r.exact_match is not None
                            )
                            / sum(
                                r.answered and r.exact_match is not None for r in run.rows.values()
                            )
                            if any(
                                r.answered and r.exact_match is not None for r in run.rows.values()
                            )
                            else None
                        ),
                        "errors": s.errors,
                        "budget_stops": s.budget_exhausted,
                    }
                )
                resources = dict(report["runs"][method]["resources"])
                for field in (
                    "retrieved_tokens",
                    "context_tokens",
                    "cache_write_tokens",
                    "reused_cost_usd",
                    "latency_seconds",
                ):
                    resources[field] = distribution(
                        [
                            float(value) if (value := getattr(r.usage, field)) is not None else None
                            for r in run.rows.values()
                        ]
                    )
                resource_rows.extend(
                    {"method": method, "resource": key, **value} for key, value in resources.items()
                )
                if group.kind == "ablation" and "ablation_protocol" not in run.manifest:
                    raise ValueError("Ablation tables require recorded intervention provenance")
                if method == stats.reference:
                    datasets.append(
                        {
                            "group": name,
                            "kind": group.kind,
                            "fixture_only": report["fixture_only"],
                            "n": s.examples,
                            "labelled": s.labelled_examples,
                            "question_groups": report["runs"][method]["metrics"]["coverage"][
                                "groups"
                            ],
                            "known_answerability": sum(
                                c.answerable is not None for c in run.labels.values()
                            ),
                            "model": models["model"],
                            "effort": models.get("reasoning_effort"),
                            "grader": s.metric_version,
                            "split": run.manifest["config"]["evaluation"].get("split"),
                            "retrieval_scope": run.manifest["retrieval_scope"],
                        }
                    )
                for case_id, row in run.rows.items():
                    trace_path = (run_path / row.trace_file).resolve()
                    if not trace_path.is_relative_to(run_path):
                        raise ValueError("Paper trace path escapes its run")
                    result = RunResult.model_validate_json(trace_path.read_text())
                    if (
                        result.query_id != case_id
                        or result.status != row.status
                        or result.usage != row.usage
                        or result.usage_complete != row.usage_complete
                        or row.answered
                        != (
                            result.status == "completed"
                            and result.output is not None
                            and result.output.answer is not None
                        )
                    ):
                        raise ValueError("Paper trace identity/status/usage differs from scores")
                    trace_hash = file_hash(trace_path)
                    sources[name]["runs"][method][row.trace_file] = trace_hash
                    category = classify(method, result, row, trace_hash)
                    entry = {
                        "group": name,
                        "method": method,
                        "query_id": case_id,
                        "outcome": category.outcome,
                        "trace_file": row.trace_file,
                        "trace_sha256": trace_hash,
                        "selected": False,
                    }
                    inventory.append(entry)
                    key = hashlib.sha256(
                        json.dumps([config.selection_seed, name, method, case_id]).encode()
                    ).hexdigest()
                    excerpt = {
                        "question": run.labels[case_id].question,
                        "classification": category.model_dump(mode="json"),
                        "scores": row.model_dump(mode="json"),
                        "output": result.output.model_dump(mode="json") if result.output else None,
                        "error": result.error,
                        "events": [
                            e.model_dump(mode="json")
                            for e in result.trace
                            if e.type in {"DECISION", "QUERY_GENERATED", "SUFFICIENCY"}
                        ],
                    }
                    candidates.setdefault(category.outcome, []).append(
                        (key, fenced(json.dumps(excerpt, indent=2, ensure_ascii=False)), entry)
                    )
            if group.kind == "ablation":
                title += "; named switch disabled"
            caption = (
                title + ". NA means unavailable; errors and abstentions retained. "
                "No pooled dataset score."
            )
            write_table(
                folder / ("ablations" if group.kind == "ablation" else "results"), rows, caption
            )
            write_table(
                folder / "resources",
                resource_rows,
                title
                + ". Physical cost and latency reflect cache reuse; unknowns excluded and counted.",
            )
            pairs = [
                {
                    "method": c["method"],
                    "reference": c["reference"],
                    "metric": c["metric"],
                    "difference": c["difference"]["mean"],
                    "CI_lower": c["difference"]["lower"],
                    "CI_upper": c["difference"]["upper"],
                    "p": c["test"]["p_value"],
                    "p_Holm": c["test"]["p_holm"],
                }
                for c in report["comparisons"]
            ]
            write_table(
                folder / "paired",
                pairs,
                title + ". Holm correction within this dataset/report only; marginal CIs.",
            )
            if group.kind == "ablation":
                (folder / "interventions.json").write_text(
                    json.dumps(run.manifest["ablation_protocol"], indent=2) + "\n"
                )
            plot_report(report, folder / "quality", title)
            traces = [
                "# Automatically selected trace excerpts",
                caption,
                "One minimum seeded hash per observed outcome across methods. "
                "Illustrative, outcome-stratified, not representative. "
                "Full population is retained in inventory.json.",
            ]
            for outcome, options in sorted(candidates.items()):
                _, excerpt_text, entry = min(options, key=lambda item: item[0])
                entry["selected"] = True
                traces += ["## " + outcome, fenced(json.dumps(entry, indent=2)), excerpt_text]
            (folder / "selected_traces.md").write_text("\n\n".join(traces) + "\n")
        write_table(
            root / "datasets",
            datasets,
            "Saved evaluation populations; fixture and real-model rows remain separate. "
            "Not full release sizes.",
        )
        (root / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
        (root / "README.md").write_text(
            "# Generated paper artifacts\n\nDo not edit result values by hand. Regenerate "
            "from YAML.\n\n"
            "Each group has CSV/Markdown/LaTeX tables, SVG/PDF figures, full statistics "
            "and selected trace excerpts. "
            "CSV retains full precision; display tables use six significant digits. "
            "NA/null is never zero.\n\n"
            "No automatic quality, causal, calibration or superiority claim follows. "
            "Ablation fixtures only test plumbing. "
            "All failed cases remain in denominators and inventory. Cost is physical "
            "estimated spend; cache reuse couples runs.\n\n"
            "Groups: " + ", ".join(config.groups) + ".\n"
        )
        manifest = {
            "protocol": "paper-artifacts-v1",
            "config": config.model_dump(mode="json"),
            "config_sha256": file_hash(config_path),
            "implementation_sha256": file_hash(Path(__file__)),
            "matplotlib_version": version,
            "source_hashes": sources,
            "selection": "minimum seeded SHA256 per group/outcome, across methods",
            "method_cases": len(inventory),
            "selected_traces": sum(r["selected"] for r in inventory),
            "additional_api_calls": 0,
            "additional_api_cost_usd": "0",
            "files": {
                str(p.relative_to(root)): file_hash(p)
                for p in sorted(root.rglob("*"))
                if p.is_file()
            },
        }
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root, output)
    return manifest
