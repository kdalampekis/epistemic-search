import io
import tarfile
import zipfile
from pathlib import Path

import httpx
import pytest
import yaml

from epistemic_search.rv2_datasets import (
    Manifest,
    download,
    hash_tree,
    safe_extract,
    sha256_file,
    verify_manifest,
    write_manifest,
)


def make_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)


def test_extraction_skips_mac_junk_and_rejects_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    make_zip(archive, {"data/x.jsonl": b"1", "__MACOSX/data/._x.jsonl": b"j", "data/._y": b"j"})
    names = safe_extract(archive, tmp_path / "out")
    assert names == ["data/x.jsonl"] and not list((tmp_path / "out").rglob("._*"))
    assert not (tmp_path / "out/__MACOSX").exists()

    bad = tmp_path / "bad.zip"
    make_zip(bad, {"../escape.txt": b"x"})
    with pytest.raises(ValueError, match="escapes"):
        safe_extract(bad, tmp_path / "out2")
    assert not (tmp_path / "escape.txt").exists()


def test_tar_extraction_rejects_links_and_keeps_regular_files(tmp_path: Path) -> None:
    good = tmp_path / "g.tar"
    with tarfile.open(good, "w") as t:
        info = tarfile.TarInfo("data/claims.jsonl")
        info.size = 2
        t.addfile(info, io.BytesIO(b"{}"))
    assert safe_extract(good, tmp_path / "o1") == ["data/claims.jsonl"]

    link = tmp_path / "l.tar"
    with tarfile.open(link, "w") as t:
        info = tarfile.TarInfo("data/evil")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        t.addfile(info)
    with pytest.raises(ValueError, match="member type"):
        safe_extract(link, tmp_path / "o2")


def test_download_streams_hashes_and_never_overwrites(tmp_path: Path) -> None:
    payload = b"dataset-bytes"
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=payload))
    )
    target = tmp_path / "d" / "file.bin"
    digest = download("https://example.invalid/file.bin", target, client)
    assert target.read_bytes() == payload and digest == sha256_file(target)
    with pytest.raises(FileExistsError):
        # an existing file blocks the rename; the partial is cleaned up either way
        target.with_name("file.bin.part").write_bytes(b"stale")
        download("https://example.invalid/file.bin", target, client)
    failing = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(httpx.HTTPStatusError):
        download("https://example.invalid/x", tmp_path / "x.bin", failing)
    assert not (tmp_path / "x.bin").exists() and not (tmp_path / "x.bin.part").exists()


def manifest(root: Path) -> Manifest:
    return Manifest(
        name="toy",
        canonical_source="c",
        download_source="d",
        license="l",
        retrieved_at="2026-10-29T00:00:00Z",
        version_or_commit="v",
        archive_sha256=None,
        split_used="dev",
        sampling_seed=None,
        transformations=[],
        notes="n",
        files=hash_tree(root / "toy"),
    )


def test_manifest_round_trip_detects_drift_and_never_overwrites(tmp_path: Path) -> None:
    data = tmp_path / "ext"
    (data / "toy").mkdir(parents=True)
    (data / "toy" / "a.txt").write_text("alpha")
    path = write_manifest(manifest(data), tmp_path / "manifests")
    assert yaml.safe_load(path.read_text())["name"] == "toy"
    assert verify_manifest(path, data) == []
    with pytest.raises(FileExistsError):
        write_manifest(manifest(data), tmp_path / "manifests")
    (data / "toy" / "a.txt").write_text("changed")
    assert verify_manifest(path, data) == ["toy: checksum differs for a.txt"]
    (data / "toy" / "a.txt").unlink()
    assert verify_manifest(path, data) == ["toy: missing a.txt"]


def test_committed_manifests_are_complete() -> None:
    paths = sorted(Path("data/manifests").glob("*.yaml"))
    names = {p.stem for p in paths}
    assert {
        "scifact",
        "vitaminc",
        "strategyqa",
        "entailmentbank",
        "hotpotqa",
        "2wikimultihop",
    } <= names
    for path in paths:
        m = Manifest.model_validate(yaml.safe_load(path.read_text()))
        assert m.name == path.stem and m.canonical_source and m.license and m.notes
        if m.status == "downloaded":
            assert (
                m.version_or_commit
                and m.files
                and (m.archive_sha256 or len(m.version_or_commit) >= 40)
            )
