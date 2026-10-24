import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from test_paper_artifacts import plan

from epistemic_search.reproduction import bundle_reproduction, verify_reproduction


def repository(tmp_path: Path) -> Path:
    path = plan(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=not-a-real-key\n")
    (tmp_path / ".gitignore").write_text(".env\n*.zip\n")
    (tmp_path / "README.md").write_text("Fixture repository\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md", ".gitignore"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    return path


def test_bundle_is_exact_repeatable_and_excludes_credentials(tmp_path: Path) -> None:
    path = repository(tmp_path)
    output = tmp_path / "one.zip"
    first = bundle_reproduction(tmp_path, path, output)
    assert first["runs"] == 2 and first["working_tree_dirty"]
    assert verify_reproduction(output)["verified"]
    with zipfile.ZipFile(output) as archive:
        assert ".env" not in archive.namelist()
        assert "run/traces/000000.json" in archive.namelist()
        manifest = json.loads(archive.read("reproduction-manifest.json"))
        assert all("seed" in run and "model" in run for run in manifest["runs"])
    second = bundle_reproduction(tmp_path, path, tmp_path / "two.zip")
    assert first == second
    with pytest.raises(FileExistsError):
        bundle_reproduction(tmp_path, path, output)


def test_verifier_rejects_modified_and_extra_members(tmp_path: Path) -> None:
    path = repository(tmp_path)
    bundle_reproduction(tmp_path, path, tmp_path / "good.zip")
    for mode in ("modified", "extra", "traversal"):
        output = tmp_path / (mode + ".zip")
        with zipfile.ZipFile(tmp_path / "good.zip") as source, zipfile.ZipFile(output, "w") as dest:
            for name in source.namelist():
                data = (
                    b"changed" if name == "README.md" and mode == "modified" else source.read(name)
                )
                dest.writestr(name, data)
            if mode != "modified":
                dest.writestr("../outside" if mode == "traversal" else "extra.txt", "bad")
        with pytest.raises(ValueError, match="checksum|inventory|Unsafe"):
            verify_reproduction(output)


def test_bundle_refuses_symlinks_and_external_runs(tmp_path: Path) -> None:
    path = repository(tmp_path)
    (tmp_path / "linked.md").symlink_to(tmp_path / "README.md")
    with pytest.raises(ValueError, match="symlinks"):
        bundle_reproduction(tmp_path, path, tmp_path / "bad.zip")
    assert not (tmp_path / "bad.zip").exists()
