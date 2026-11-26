"""Recreate the seven prepared datasets in a scratch directory and verify their hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "batch4"))
from package import package


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(work, spec):
    path = work / spec["relativepath"]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_suffix(path.suffix + ".partial")
        subprocess.run(["curl", "--fail", "--location", "--retry", "3", "--silent", "--show-error",
                        "--output", str(pending), spec["url"]], check=True)
        if sha256(pending) != spec["sha256"]:
            raise ValueError(f"Source version mismatch at {spec['url']}. Supply the recorded snapshot at {path}.")
        pending.replace(path)
    elif sha256(path) != spec["sha256"]:
        raise ValueError(f"Local source has a different SHA-256: {path}")


def main(work):
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    sources = [item for item in manifest["datasets"] if item.get("batch") == 5]
    if len(sources) != 7:
        raise ValueError("Expected the seven batch 5 sources in the manifest.")
    candidates = work / "candidates"
    candidates.mkdir(parents=True, exist_ok=True)
    for entry in sources:
        inventory = ROOT / "sources" / entry["dataset_id"] / "source_manifest.json"
        for item in json.loads(inventory.read_text(encoding="utf-8"))["files"]:
            fetch(work, item)
    for builder, raw in [("engineering.py", work), ("language_retail.py", work / "raw"),
                         ("powerlifting.py", work), ("physiology.py", work)]:
        subprocess.run([sys.executable, str(HERE / builder), str(raw), str(candidates)], check=True)
    for entry in sources:
        folder = Path(entry["files"][0]["path"]).parent.name
        prefix = entry["dataset_id"] + "_"
        if not folder.startswith(prefix):
            raise ValueError(f"Unexpected folder name: {folder}")
        slug = folder[len(prefix):]
        package(work, slug, batch=5, version="2.4.0")
        stats = json.loads((work / "stats" / f"{slug}.json").read_text(encoding="utf-8"))
        if stats["uncompressed_sha256"] != entry["uncompressed_sha256"]:
            raise ValueError(f"Rebuilt records differ for {slug}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="Scratch directory for source files and rebuilt shards.")
    main(parser.parse_args().work.resolve())
