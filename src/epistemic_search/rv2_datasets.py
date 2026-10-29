"""RV2 external-dataset acquisition: pinned sources, safe extraction, reproducibility manifests.

Raw third-party data lives under ``data/external/`` (git-ignored). Only the small manifests under
``data/manifests/`` are committed. Nothing here calls a model, and tests never touch the network.
"""

import hashlib
import shutil
import subprocess
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
import yaml

from epistemic_search.models import Schema

MANIFEST_FIELDS = (
    "name",
    "canonical_source",
    "download_source",
    "license",
    "retrieved_at",
    "version_or_commit",
    "archive_sha256",
    "split_used",
    "sampling_seed",
    "transformations",
    "notes",
)


class Manifest(Schema):
    name: str
    canonical_source: str
    download_source: str
    license: str
    retrieved_at: str
    version_or_commit: str
    archive_sha256: str | None
    split_used: str
    sampling_seed: int | None
    transformations: list[str]
    notes: str
    status: Literal["downloaded", "not_used"] = "downloaded"
    files: dict[str, str]  # relative path -> sha256 of every file kept locally


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def download(url: str, target: Path, client: httpx.Client | None = None) -> str:
    """Stream to ``target`` (never overwriting) and return its SHA-256."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    own = client is None
    http = client or httpx.Client()
    try:
        with http.stream("GET", url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with partial.open("xb") as out:
                for chunk in response.iter_bytes():
                    out.write(chunk)
        digest = sha256_file(partial)
        partial.rename(target)
        return digest
    finally:
        partial.unlink(missing_ok=True)
        if own:
            http.close()


def _inside(root: Path, name: str) -> Path:
    resolved = (root / name).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Archive member escapes the extraction directory: {name}")
    return resolved


def junk(name: str) -> bool:
    """macOS resource forks and zip metadata carry no data."""
    parts = name.split("/")
    return "__MACOSX" in parts or parts[-1].startswith("._")


def safe_extract(archive: Path, destination: Path) -> list[str]:
    """Extract a zip or tar without following paths outside ``destination``; no code is run."""
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            names = [n for n in z.namelist() if not n.endswith("/") and not junk(n)]
            for n in names:
                _inside(destination, n)
            z.extractall(destination, members=names)
        return sorted(names)
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            _inside(destination, m.name)
            if m.issym() or m.islnk() or m.isdev():
                raise ValueError(f"Unsupported archive member type: {m.name}")
        members = [m for m in t.getmembers() if m.isfile() and not junk(m.name)]
        t.extractall(destination, members=members, filter="data")
    return sorted(m.name for m in members)


def clone_pinned(repo_url: str, destination: Path, keep: list[str]) -> str:
    """Shallow-clone, copy only ``keep`` paths, drop git metadata, return the exact commit SHA."""
    work = destination.with_name(destination.name + ".clone")
    if work.exists():
        raise FileExistsError(work)
    subprocess.run(["git", "clone", "--quiet", "--depth", "1", repo_url, str(work)], check=True)
    sha = subprocess.run(
        ["git", "-C", str(work), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    try:
        for rel in keep:
            source = _inside(work, rel)
            target = _inside(destination, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return sha


def hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): sha256_file(p) for p in sorted(root.rglob("*")) if p.is_file()
    }


def write_manifest(manifest: Manifest, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{manifest.name}.yaml"
    if path.exists():
        raise FileExistsError(f"{path} exists; manifests are never overwritten")
    path.write_text(yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False))
    return path


def verify_manifest(path: Path, data_root: Path) -> list[str]:
    """Offline check that the local files still match the manifest; returns problems."""
    manifest = Manifest.model_validate(yaml.safe_load(path.read_text()))
    if manifest.status == "not_used":
        return []
    root = data_root / manifest.name
    problems = []
    for rel, digest in manifest.files.items():
        file = root / rel
        if not file.is_file():
            problems.append(f"{manifest.name}: missing {rel}")
        elif sha256_file(file) != digest:
            problems.append(f"{manifest.name}: checksum differs for {rel}")
    return problems
