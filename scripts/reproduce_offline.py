"""Run only offline fixtures or reanalyze bundled saved results in a fresh output directory."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["fixtures", "saved"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if (root / ".env").exists():
        raise SystemExit("Use an extracted reproduction package or clean checkout without .env")
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)

    def run(*arguments: str) -> None:
        subprocess.run(
            [sys.executable, "-c", "from epistemic_search.cli import app; app()", *arguments],
            cwd=root,
            env=env,
            check=True,
        )

    if args.mode == "fixtures":
        commands = [
            ["evaluate", "configs/evaluation_fixture.yaml"],
            ["evaluate", "configs/epistemic_fixture.yaml"],
            ["evaluate", "configs/voi_fixture.yaml"],
            ["compare", "configs/parity_fixture.yaml"],
            ["ablate", "configs/ablation_fixture.yaml"],
            ["compare-formal", "configs/formal_fixture.yaml"],
            ["calibrate", "configs/calibration_fixture.yaml"],
            ["transform", "configs/transform_fixture.yaml"],
            ["evaluate", "configs/controlled_fixture.yaml"],
            ["analyze-failures", "configs/failures_fixture.yaml"],
            ["dashboard", "configs/dashboard_fixture.yaml"],
            ["paper-artifacts", "configs/paper_fixture.yaml"],
        ]
        if (root / "artifacts").exists() and any((root / "artifacts").glob("*-fixture*")):
            raise SystemExit("Fixture outputs already exist; use a fresh checkout")
        for command in commands:
            run(*command)
    else:
        # Keep the original plan immutable. All source paths still resolve from configs/.
        path = root / "configs/reproduction_saved.yaml"
        if path.exists():
            raise SystemExit("Saved reproduction plan already exists")
        config = yaml.safe_load((root / "configs/paper_pilot.yaml").read_text())
        config["output_dir"] = "../artifacts/reproduced-paper"
        path.write_text(yaml.safe_dump(config, sort_keys=False))
        run("paper-artifacts", str(path))
        expected = root / "docs/paper/generated"
        actual = root / "artifacts/reproduced-paper"
        for group in config["groups"]:
            for name in ("results.csv", "ablations.csv", "resources.csv", "paired.csv"):
                before = expected / group / name
                if before.exists() and before.read_bytes() != (actual / group / name).read_bytes():
                    raise SystemExit(f"Saved result mismatch: {group}/{name}")
            before_stats = json.loads((expected / group / "statistics.json").read_text())
            after_stats = json.loads((actual / group / "statistics.json").read_text())
            for key in ("runs", "comparisons", "matched_protocol"):
                if before_stats[key] != after_stats[key]:
                    raise SystemExit(f"Saved statistical mismatch: {group}/{key}")
        print("Saved tables and statistics reproduced exactly; additional API cost $0")


if __name__ == "__main__":
    main()
