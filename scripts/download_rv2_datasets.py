"""Download the external RV2 datasets and write reproducibility manifests.

    uv run --locked python scripts/download_rv2_datasets.py            # all datasets
    uv run --locked python scripts/download_rv2_datasets.py scifact    # one dataset

Raw data goes to data/external/<name>/ (git-ignored); manifests go to data/manifests/<name>.yaml.
Existing data and manifests are never overwritten. No model is called.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

from epistemic_search.rv2_datasets import (
    Manifest,
    clone_pinned,
    download,
    hash_tree,
    now_iso,
    safe_extract,
    sha256_file,
    write_manifest,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "external"
MANIFESTS = ROOT / "data" / "manifests"
LEGACY = ROOT / "artifacts" / "benchmarks"
LOCK = json.loads((ROOT / "configs" / "datasets.lock.json").read_text())
LOCKED = {f["name"]: f for f in LOCK["files"]}
NOT_VERIFIED = "dataset content license not independently verified in this audit"


def archive(
    name: str,
    url: str,
    canonical: str,
    license_: str,
    split: str,
    notes: str,
    transformations: list[str],
) -> Manifest:
    target = DATA / name
    with tempfile.TemporaryDirectory() as tmp:
        file = Path(tmp) / url.rsplit("/", 1)[-1]
        digest = download(url, file)
        safe_extract(file, target)
    return Manifest(
        name=name,
        canonical_source=canonical,
        download_source=url,
        license=license_,
        retrieved_at=now_iso(),
        version_or_commit=f"archive sha256 {digest}",
        archive_sha256=digest,
        split_used=split,
        sampling_seed=None,
        transformations=transformations,
        notes=notes,
        files=hash_tree(target),
    )


def scifact() -> Manifest:
    return archive(
        "scifact",
        "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz",
        "https://github.com/allenai/scifact",
        f"repository license per GitHub API: NOASSERTION; {NOT_VERIFIED}",
        "dev (claims_dev.jsonl); train may be used for deterministic diagnostics; "
        "claims_test.jsonl is unlabeled and is never used",
        "Official release archive named by script/download-data.sh (a 'latest' alias that was last "
        "modified 2021-01-26). Wrapped as 'latest', so the archive hash is the version identity.",
        ["extracted unchanged"],
    )


def vitaminc() -> Manifest:
    return archive(
        "vitaminc",
        "https://github.com/TalSchuster/talschuster.github.io/raw/master/static/vitaminc.zip",
        "https://github.com/TalSchuster/VitaminC",
        f"repository: MIT per GitHub API; {NOT_VERIFIED}",
        "dev (a deterministic subset, never test)",
        "Fact-verification data linked from the VitaminC README ('vitaminc.zip'). Label "
        "vocabulary is inspected, not assumed; see RV2_DATASET_AUDIT.md.",
        ["extracted unchanged"],
    )


def strategyqa() -> Manifest:
    return archive(
        "strategyqa",
        "https://storage.googleapis.com/ai2i/strategyqa/data/strategyqa_dataset.zip",
        "https://allenai.org/data/strategyqa (code: https://github.com/eladsegal/strategyqa)",
        f"code repository: MIT per GitHub API; {NOT_VERIFIED}",
        "train only carries decompositions/evidence; an internal deterministic split is used",
        "Official dataset ZIP linked from the AI2 dataset page. Which splits carry which fields is "
        "audited in RV2_DATASET_AUDIT.md.",
        ["extracted unchanged"],
    )


def entailmentbank() -> Manifest:
    target = DATA / "entailmentbank"
    sha = clone_pinned(
        "https://github.com/allenai/entailment_bank", target, ["data/public_dataset", "LICENSE"]
    )
    return Manifest(
        name="entailmentbank",
        canonical_source="https://github.com/allenai/entailment_bank",
        download_source="https://github.com/allenai/entailment_bank (shallow git clone)",
        license=f"repository: Apache-2.0 per GitHub API; {NOT_VERIFIED}",
        retrieved_at=now_iso(),
        version_or_commit=sha,
        archive_sha256=None,
        split_used="dev (task_1 complete leaves, task_2 with distractors); test untouched",
        sampling_seed=None,
        transformations=["only data/public_dataset and LICENSE kept; git metadata removed"],
        notes="The repository ships the public dataset as entailment_trees_emnlp2021_data_v2.",
        files=hash_tree(target),
    )


def legacy(name: str, entries: dict[str, str], **fields: object) -> Manifest:
    """HotpotQA / 2Wiki: reuse the pilot's checksum-locked files rather than re-download."""
    target = DATA / name
    target.mkdir(parents=True)
    for source, dest in entries.items():
        shutil.copy2(LEGACY / source, target / dest)
    return Manifest(
        name=name,
        retrieved_at="2026-10-23T00:00:00Z (pilot setup; copied locally on retrieval)",
        files=hash_tree(target),
        sampling_seed=None,
        **fields,  # type: ignore[arg-type]
    )


def hotpotqa() -> Manifest:
    pinned = LOCKED["hotpot_dev.parquet"]
    if sha256_file(LEGACY / "hotpot_dev.parquet") != pinned["sha256"]:
        raise ValueError("Pilot HotpotQA parquet no longer matches the checksum lock")
    return legacy(
        "hotpotqa",
        {
            "hotpot_dev.parquet": "hotpot_dev.parquet",
            "hotpot_dev.parquet.json": "hotpot_dev_distractor.json",
        },
        canonical_source="https://github.com/hotpotqa/hotpot",
        download_source=pinned["url"],
        license="HotpotQA: CC BY-SA 4.0 per the dataset card; code Apache-2.0",
        version_or_commit="huggingface hotpotqa/hotpot_qa revision "
        "1908d6afbbead072334abe2965f91bd2709910ab",
        archive_sha256=pinned["sha256"],
        split_used="dev distractor; official test untouched",
        transformations=[
            "parquet converted to the official JSON schema by "
            "epistemic_search.dataset_setup.hotpot_from_parquet (pilot setup)"
        ],
        notes="The canonical host curtis.ml.cmu.edu does not resolve (checked 2026-10-29), so the "
        "pinned Hugging Face mirror of the official distractor dev set is used, as in the pilot.",
    )


def twowiki() -> Manifest:
    pinned = LOCKED["2wiki.zip"]
    if sha256_file(LEGACY / "2wiki.zip") != pinned["sha256"]:
        raise ValueError("Pilot 2Wiki archive no longer matches the checksum lock")
    return legacy(
        "2wikimultihop",
        {"dev.json": "dev.json", "id_aliases.json": "id_aliases.json"},
        canonical_source="https://github.com/Alab-NII/2wikimultihop",
        download_source=pinned["url"],
        license="repository Apache-2.0; Wikipedia-derived content has its own terms",
        version_or_commit="data_ids_april7.zip (official April 7 2021 release with ids)",
        archive_sha256=pinned["sha256"],
        split_used="dev; official test untouched",
        transformations=["dev.json and id_aliases.json extracted from the archive unchanged"],
        notes="Same locked archive as the pilot.",
    )


def hover() -> Manifest:
    return Manifest(
        name="hover",
        canonical_source="https://github.com/hover-nlp/hover",
        download_source="not downloaded",
        license="repository: MIT per GitHub API",
        retrieved_at=now_iso(),
        version_or_commit="n/a",
        archive_sha256=None,
        split_used="none",
        sampling_seed=None,
        transformations=[],
        status="not_used",
        files={},
        notes="Optional in the RV2 plan and skipped: the official download script also fetches "
        "wiki_wo_links.db and retrieval caches. RV2 does not depend on it.",
    )


BUILDERS = {
    "scifact": scifact,
    "vitaminc": vitaminc,
    "strategyqa": strategyqa,
    "entailmentbank": entailmentbank,
    "hotpotqa": hotpotqa,
    "2wikimultihop": twowiki,
    "hover": hover,
}


def main(names: list[str]) -> int:
    chosen = names or list(BUILDERS)
    unknown = [n for n in chosen if n not in BUILDERS]
    if unknown:
        print(f"Unknown datasets: {unknown}; choose from {sorted(BUILDERS)}", file=sys.stderr)
        return 2
    for name in chosen:
        if (MANIFESTS / f"{name}.yaml").exists():
            print(f"{name}: manifest exists, skipped")
            continue
        if (DATA / name).exists():
            print(
                f"{name}: data directory exists without a manifest; refusing to overwrite",
                file=sys.stderr,
            )
            return 1
        manifest = BUILDERS[name]()
        path = write_manifest(manifest, MANIFESTS)
        print(f"{name}: {len(manifest.files)} files, manifest {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
