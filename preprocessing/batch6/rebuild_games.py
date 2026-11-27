"""Rebuild all three game datasets and compare them with the published release."""
import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from preprocessing.batch4.package import package
from preprocessing.batch5.rebuild import fetch
from preprocessing.batch6 import dota, mario, starcraft
from preprocessing.batch6.split_games import export


BUILDERS = {"dota2_pro": ("dota", dota.build), "smmnet": ("mario", mario.build),
            "uci_272": ("starcraft", starcraft.build)}


def rebuild(work):
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    entries = [item for item in manifest["datasets"] if item.get("batch") == 6]
    if {item["dataset_id"] for item in entries} != BUILDERS.keys():
        raise ValueError("Missing game datasets in the release manifest.")
    candidates = work / "candidates"
    candidates.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        dataset = entry["dataset_id"]
        inventory = ROOT / "sources" / dataset / "source_manifest.json"
        for item in json.loads(inventory.read_text(encoding="utf-8"))["files"]:
            fetch(work, item)
        slug, build = BUILDERS[dataset]
        build(work, candidates)
        package(work, slug, batch=6, version="2.5.0")
        stats = json.loads((work / "stats" / f"{slug}.json").read_text(encoding="utf-8"))
        if stats["uncompressed_sha256"] != entry["uncompressed_sha256"]:
            raise ValueError(f"Rebuilt records differ for {dataset}.")

    output = work / "splits" / "batch6"
    export(work / "publish", entries, output)
    official = ROOT / "splits" / "batch6"
    with gzip.open(output / "assignments.csv.gz", "rb") as rebuilt, \
            gzip.open(official / "assignments.csv.gz", "rb") as published:
        if rebuilt.read() != published.read():
            raise ValueError("Rebuilt split assignments differ from the published CSV.")
    if json.loads((output / "summary.json").read_text()) != json.loads((official / "summary.json").read_text()):
        raise ValueError("Rebuilt partition counts differ from the release.")
    print("Verified all three datasets and their suggested partitions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="Scratch directory for raw files and reconstructed records.")
    rebuild(parser.parse_args().work.resolve())
