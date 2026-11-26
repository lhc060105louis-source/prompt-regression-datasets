"""Build and validate shards in a staging directory using the release 2.2 standardizer."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "preprocessing/batch3"))
import standardize
import validate_extension


def package(work, slug, *, batch=4, version="2.3.0"):
    standardize.ROOT = validate_extension.ROOT = work
    standardize.OUT = validate_extension.PUB = work / "publish"
    candidate = work / "candidates" / f"{slug}.meta.json"
    meta = json.loads(candidate.read_text(encoding="utf-8"))
    for item in meta["source_files"]:
        source = work / item["relativepath"]
        if item["sha256"] != standardize.sha(source):
            raise ValueError(f"Source checksum mismatch: {source}")
    standardize.build(slug)
    stats_path = work / "stats" / f"{slug}.json"
    stats = json.loads(stats_path.read_text())
    stats["batch"] = batch
    standardize.save(stats_path, stats)
    folder = standardize.OUT / Path(stats["files"][0]["path"]).parent
    prepared = json.loads((folder / "metadata.json").read_text())
    prepared.update(version=version, stats=stats)
    standardize.save(folder / "metadata.json", prepared)
    validate_extension.validate(slug)
    validation = json.loads((work / "stats" / f"{slug}.validation.json").read_text())
    standardize.save(folder / "record_validation.json", validation)
    standardize.save(standardize.OUT / "sources" / stats["dataset_id"] / "source_manifest.json", {
        "source_url": meta["source_url"], "version": meta["version"], "license": meta["license"],
        "citation": meta["source_citation"], "files": prepared["source_files"],
        "preparation": f"See preprocessing/batch{batch} and per-dataset metadata.", "raw_archives_included": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="Contains source files and the candidates directory.")
    parser.add_argument("slugs", nargs="+", choices="paddy faostat uji gas fred sdss".split())
    args = parser.parse_args()
    for slug in args.slugs:
        package(args.work.resolve(), slug)
