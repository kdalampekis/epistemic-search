"""Allowlisted, checksummed offline reproduction archives; never include credentials."""

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from epistemic_search.evaluation import file_hash
from epistemic_search.paper_artifacts import PaperConfig
from epistemic_search.statistics import StatisticsConfig, read_run

SOURCE_DIRS = {"src", "tests", "configs", "scripts", "docs", ".github"}
SOURCE_SUFFIXES = {
    ".py",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".md",
    ".toml",
    ".lock",
    ".css",
    ".js",
    ".csv",
    ".tex",
    ".svg",
    ".pdf",
    ".png",
}
ROOT_FILES = {"pyproject.toml", "uv.lock", ".python-version", ".gitignore", "LICENSE"}


def source_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
    )
    selected = []
    for name in sorted(set(result.stdout.decode().split("\0")) - {""}):
        relative = Path(name)
        allowed = (
            len(relative.parts) == 1
            and (relative.suffix == ".md" or name in ROOT_FILES)
            or relative.parts[0] in SOURCE_DIRS
            and relative.suffix in SOURCE_SUFFIXES
        )
        if allowed:
            selected.append(root / relative)
    return selected


def bundle_reproduction(root: Path, paper_config: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    config_path = (root / paper_config).resolve()
    if not config_path.is_relative_to(root):
        raise ValueError("Reproduction plan must be inside the repository")
    config = PaperConfig.model_validate(yaml.safe_load(config_path.read_text()))
    files = set(source_files(root))
    files.add(config_path)
    metadata = []
    for group, plan in config.groups.items():
        stats_path = (config_path.parent / plan.statistics_config).resolve()
        files.add(stats_path)
        stats = StatisticsConfig.model_validate(yaml.safe_load(stats_path.read_text()))
        for method, relative in stats.runs.items():
            run_path = (stats_path.parent / relative).resolve()
            if not run_path.is_relative_to(root):
                raise ValueError("Saved runs must be inside the repository")
            run = read_run(run_path)
            files.update(run_path / name for name in run.hashes)
            for row in run.rows.values():
                trace = (run_path / row.trace_file).resolve()
                if not trace.is_relative_to(run_path):
                    raise ValueError("Reproduction trace path escapes its run")
                files.add(trace)
            cfg = run.manifest["config"]
            metadata.append(
                {
                    "group": group,
                    "method": method,
                    "path": str(run_path.relative_to(root)),
                    "fixture_only": run.manifest.get("fixture_only", True),
                    "model": cfg["rag"]["model"],
                    "reasoning_effort": cfg["rag"].get("reasoning_effort"),
                    "seed": cfg["seed"],
                    "config_hash": run.manifest["config_hash"],
                    "metric_version": run.summary.metric_version,
                    "examples": run.summary.examples,
                    "input_hashes": run.manifest["input_hashes"],
                }
            )
    contents = {}
    for path in sorted(files):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Reproduction inputs cannot be symlinks or escape the repository")
        archive_name = str(path.relative_to(root))
        if any(part.startswith(".env") for part in path.relative_to(root).parts):
            raise ValueError("Environment files cannot enter a reproduction archive")
        contents[archive_name] = path.read_bytes()
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    manifest = {
        "protocol": "offline-reproduction-v1",
        "source_commit": revision,
        "working_tree_dirty": dirty,
        "paper_config": str(config_path.relative_to(root)),
        "runs": metadata,
        "files": {n: hashlib.sha256(b).hexdigest() for n, b in contents.items()},
        "excluded": [
            "credentials/environment files",
            "model caches",
            "spending databases",
            "full benchmark downloads",
            "Git metadata",
        ],
        "scope": "Saved-output reanalysis and offline fixture execution; no paid model rerun.",
        "additional_api_calls": 0,
    }
    contents["reproduction-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(contents.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return {
        "archive_sha256": file_hash(output),
        "files": len(contents),
        "runs": len(metadata),
        "source_commit": revision,
        "working_tree_dirty": dirty,
    }


def verify_reproduction(archive_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive members")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("Unsafe archive member path")
        manifest = json.loads(archive.read("reproduction-manifest.json"))
        if manifest.get("protocol") != "offline-reproduction-v1":
            raise ValueError("Unknown reproduction protocol")
        if set(names) != {*manifest["files"], "reproduction-manifest.json"}:
            raise ValueError("Archive inventory differs from manifest")
        for name, expected in manifest["files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError(f"Archive checksum mismatch: {name}")
    return {
        "archive_sha256": file_hash(archive_path),
        "files": len(names),
        "source_commit": manifest["source_commit"],
        "verified": True,
    }
