"""Write suggested game-task partitions using only the prepared shards."""
import argparse
import csv
import gzip
import io
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from preprocessing.batch5.suggest_splits import PARTITIONS, grouped_assignments, records


def export(root, entries, output):
    if {item["dataset_id"] for item in entries} != {"dota2_pro", "smmnet", "uci_272"}:
        raise ValueError("Expected the three game datasets.")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["sample_id", "dataset_id", "split"])
    summary = {}
    seen = set()
    for entry in entries:
        dataset = entry["dataset_id"]
        groups = {}
        if dataset != "dota2_pro":
            group_ids = {row["group_id"] for row in records(root, entry)}
            groups = grouped_assignments(group_ids, (70, 15, 15))
        counts = Counter()
        input_splits = {}
        for row in records(root, entry):
            sample = row["sample_id"]
            group = row["group_id"]
            if row["dataset_id"] != dataset or row["split"] != "unassigned" or sample in seen:
                raise ValueError(f"Unexpected source, partition or duplicate sample: {sample}")
            if dataset == "dota2_pro":
                year = date.fromisoformat(row["time_key"]).year
                split = {2023: "train", 2024: "train", 2025: "validation", 2026: "test"}[year]
                if groups.setdefault(group, split) != split:
                    raise ValueError(f"Match group spans temporal partitions: {group}")
            else:
                split = groups[group]
            if input_splits.setdefault(row["input_hash"], split) != split:
                raise ValueError(f"Identical input in multiple partitions: {sample}")
            seen.add(sample)
            counts[split] += 1
            writer.writerow([sample, dataset, split])
        if sum(counts.values()) != entry["output_examples"] or set(counts) != set(PARTITIONS):
            raise ValueError(f"Partition totals disagree with the release for {dataset}")
        summary[dataset] = {key: counts[key] for key in PARTITIONS}
    output.mkdir(parents=True, exist_ok=True)
    with (output / "assignments.csv.gz").open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            compressed.write(stream.getvalue().encode("utf-8"))
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    manifest = json.loads((args.root / "manifest.json").read_text(encoding="utf-8"))
    export(args.root, [item for item in manifest["datasets"] if item.get("batch") == 6], args.output_dir)
