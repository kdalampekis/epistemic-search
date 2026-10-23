"""Checksum-locked benchmark acquisition; no execution of downloaded code."""

import hashlib
import importlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from pydantic import Field, StringConstraints

from epistemic_search.models import Schema

Filename = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class ReleaseFile(Schema):
    name: Filename
    url: str
    sha256: Digest
    license_note: str
    archive_members: dict[Filename, Digest] = Field(default_factory=dict)
    convert: Literal["hotpot-parquet"] | None = None


class DatasetLock(Schema):
    version: Literal[1] = 1
    files: list[ReleaseFile]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def hotpot_from_parquet(path: Path, output: Path) -> None:
    try:
        pq = importlib.import_module("pyarrow.parquet")
    except ImportError as exc:
        raise ValueError("Hotpot mirror conversion requires uv sync --extra benchmarks") from exc
    rows: list[dict[str, Any]] = pq.read_table(path).to_pylist()
    for row in rows:
        row["_id"] = row.pop("id")
        context = row["context"]
        row["context"] = list(zip(context["title"], context["sentences"], strict=True))
        facts = row["supporting_facts"]
        row["supporting_facts"] = list(zip(facts["title"], facts["sent_id"], strict=True))
    with output.open("x", encoding="utf-8") as stream:
        json.dump(rows, stream, ensure_ascii=False, sort_keys=True)
        stream.write("\n")


def prepare_datasets(lock_path: Path, output_dir: Path, client: httpx.Client) -> dict[str, str]:
    lock = DatasetLock.model_validate_json(lock_path.read_bytes())
    names = [f.name for f in lock.files]
    names += [name for f in lock.files for name in f.archive_members]
    names += [f.name + ".json" for f in lock.files if f.convert]
    if len(set(names)) != len(names) or not names:
        raise ValueError("Release output filenames must be unique and nonempty")
    if "setup-manifest.json" in names or any(name + ".part" in names for name in names):
        raise ValueError("Release filenames collide with setup bookkeeping files")
    output_dir.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}
    for release in lock.files:
        path = output_dir / release.name
        partial = path.with_name(path.name + ".part")
        try:
            with client.stream("GET", release.url, follow_redirects=True, timeout=60) as response:
                response.raise_for_status()
                with partial.open("xb") as stream:
                    for chunk in response.iter_bytes():
                        stream.write(chunk)
            if sha256(partial) != release.sha256:
                raise ValueError(f"Checksum mismatch: {release.name}")
            partial.rename(path)
        finally:
            partial.unlink(missing_ok=True)
        hashes[path.name] = release.sha256
        if release.archive_members:
            with zipfile.ZipFile(path) as archive:
                for name, expected in release.archive_members.items():
                    target = output_dir / name
                    with archive.open(name) as source, target.open("xb") as stream:
                        shutil.copyfileobj(source, stream)
                    if sha256(target) != expected:
                        target.unlink()
                        raise ValueError(f"Archive member checksum mismatch: {name}")
                    hashes[name] = expected
        if release.convert:
            target = path.with_name(path.name + ".json")
            hotpot_from_parquet(path, target)
            hashes[target.name] = sha256(target)
    (output_dir / "setup-manifest.json").write_text(
        json.dumps(
            {
                "lock": lock.model_dump(mode="json"),
                "lock_sha256": sha256(lock_path),
                "output_sha256": hashes,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return hashes
