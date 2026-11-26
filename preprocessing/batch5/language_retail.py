"""Prepare pinned Lancaster word ratings and UCI retail next-week candidates.

Usage: python language_retail.py WORK/raw WORK/candidates
Place the files named in SOURCES under WORK/raw. Source inventory paths are
relative to WORK, matching the batch-3 standardizer. No split is assigned here.
"""
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import unicodedata
from zipfile import ZipFile


SOURCES = {
    "lancaster_sensorimotor.csv": (
        "https://osf.io/download/48wsc/",
        "445d363fb1f9f3e50b86d88e2f46cdc9a22b5dd8a713ce4e7be2a773d57f43c5",
    ),
    "retail_weekly.zip": (
        "https://archive.ics.uci.edu/static/public/396/sales+transactions+dataset+weekly.zip",
        "dededa20f199af8f2bb96184bb1696befda902849a700bde283fe763afc90ba9",
    ),
}
CC_BY = "https://creativecommons.org/licenses/by/4.0/"
LANCASTER_PAGE = "https://osf.io/7emr6/"
LANCASTER_NODE = "https://api.osf.io/v2/nodes/rwhs6/"
LANCASTER_LICENSE = "https://api.osf.io/v2/licenses/563c1cf88c5e4a3877f9e96a/"
RETAIL_PAGE = "https://archive.ics.uci.edu/dataset/396/sales+transactions+dataset+weekly"
RETAIL_MEMBER = "Sales_Transactions_Dataset_Weekly.csv"
RETAIL_CSV_SHA = "6f939a928c04820bc291a6184f4f1d0be694b8de58d949e808852804f25969c3"
DIMENSIONS = {
    "auditory_strength": ("Auditory", "hearing"),
    "visual_strength": ("Visual", "vision"),
    "haptic_strength": ("Haptic", "touch"),
}
HISTORY = 8


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def emit(stream, value):
    stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")


def source_file(raw, name):
    path = raw / name
    payload = path.read_bytes()
    url, expected = SOURCES[name]
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError(f"Unexpected source version or corrupted file: {path}")
    return payload, {"relativepath": "raw/" + name, "url": url,
                     "sha256": expected, "bytes": len(payload)}


def read_csv(payload):
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames
    if not fields or len(fields) != len(set(fields)):
        raise ValueError("Missing or repeated CSV headers")
    records = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in records):
        raise ValueError("Malformed CSV row")
    return fields, records


def number(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"Nonfinite source number: {text}")
    return int(value) if value.is_integer() else value


def word_key(word):
    return unicodedata.normalize("NFKC", word).strip().casefold()


def lancaster(raw, out):
    payload, source = source_file(raw, "lancaster_sensorimotor.csv")
    fields, records = read_csv(payload)
    assert len(fields) == 45 and len(records) == 39707
    assert len({word_key(r["Word"]) for r in records}) == len(records)
    assert all(r["Word"].strip() for r in records)
    tasks = {}
    for task, (column, sense) in DIMENSIONS.items():
        tasks[task] = {
            "target_name": task, "unit": "mean human rating (0-5)", "type": "continuous",
            "instruction": f"Estimate the mean human rating of how strongly the meaning of this English word is experienced through {sense}. The scale ranges from 0 (not experienced at all) to 5 (experienced greatly).",
            "field_description": "word is the original English word or expression, without sentence context. Ratings summarize people's experience of its meaning across possible senses; they are not a measurement of a physical property.",
        }
    count = 0
    with (out / "lancaster.jsonl").open("w", encoding="utf-8") as target:
        for rownum, row in enumerate(records, 1):
            for task, (column, _) in DIMENSIONS.items():
                label = number(row[column + ".mean"])
                sd = number(row[column + ".SD"])
                n = number(row["N_known.perceptual"])
                assert 0 <= label <= 5 and sd >= 0 and isinstance(n, int) and n >= 10
                emit(target, {
                    "task_key": task, "input": {"word": row["Word"]}, "label": label,
                    "group_key": word_key(row["Word"]), "entity_id": word_key(row["Word"]),
                    "split": "unassigned", "quality_flags": ["human_aggregate_rating"],
                    "rating_sd": sd, "rating_n": n,
                    "source_refs": [{"file": "raw/lancaster_sensorimotor.csv", "row": rownum,
                                     "column": column + ".mean"}],
                })
                count += 1
    assert count == 119121
    write_json(out / "lancaster.meta.json", {
        "dataset_id": "lancaster_sensorimotor", "dataset_family": "lancaster_sensorimotor_norms",
        "name": "Lancaster Sensorimotor Norms: auditory, visual and haptic strength",
        "candidate_id": "B5-LANCASTER", "source_url": LANCASTER_PAGE,
        "creators": ["Dermot Lynott", "Louise Connell", "Marc Brysbaert", "James Brand", "James Carney"],
        "source_citation": "Lynott, D., Connell, L., Brysbaert, M., Brand, J., and Carney, J. (2020). The Lancaster Sensorimotor Norms: multidimensional measures of perceptual and action strength for 40,000 English words. Behavior Research Methods 52, 1271-1291. https://doi.org/10.3758/s13428-019-01316-z",
        "version": "OSF aggregate file 48wsc, SHA256-pinned, accessed 2026-11-26",
        "source_files": [source],
        "license": {"name": "CC BY 4.0", "url": CC_BY,
                    "evidence": {"data_node": LANCASTER_NODE, "license_relationship": LANCASTER_LICENSE},
                    "scope": "Original aggregate CSV words and ratings. Preserve author attribution, licence and adaptation notice. No third-party sentence or audio material is included."},
        "raw_rows_selected": len(records), "candidate_task_examples": count,
        "excluded_source_rows": 0, "invalid_label_examples": 0,
        "source_profile": {"source_columns": fields, "unique_normalized_words": len(records),
                           "selected_mean_columns": [v[0] + ".mean" for v in DIMENSIONS.values()],
                           "unselected_mean_columns": [x for x in fields if x.endswith(".mean") and x not in {v[0] + ".mean" for v in DIMENSIONS.values()}]},
        "excluded_input_columns": [f for f in fields if f != "Word"],
        "target_transform": "original_source_mean_no_transformation",
        "grouping_rule": "NFKC-normalized, stripped and casefolded original Word. All three target dimensions of a word share a group; the original input spelling is unchanged.",
        "split_policy": "Unassigned. Assign word groups jointly across all dimensions, for example 80/10/10. Audit morphological relatives and cross-source overlapping words before claiming unseen-word evaluation.",
        "quality_findings": [
            "Only auditory, visual and haptic aggregate mean scores are selected. Other rating means, SDs, sample sizes and score-derived summary variables are excluded from input.",
            "rating_sd and rating_n preserve source rater disagreement and sample size outside the prompt. They are not model prediction variance labels.",
            "The OSF data node says the historical participant-ID correction affected trial-level data, not this aggregate file. Trial-level participant data are not included.",
            "These are decontextualized human ratings across meanings of a word, not objective sensory measurements. References use 1-based data rows excluding the header.",
        ], "tasks": tasks,
    })


def retail(raw, out):
    payload, source = source_file(raw, "retail_weekly.zip")
    with ZipFile(io.BytesIO(payload)) as archive:
        assert archive.namelist() == [RETAIL_MEMBER]
        csv_bytes = archive.read(RETAIL_MEMBER)
    assert hashlib.sha256(csv_bytes).hexdigest() == RETAIL_CSV_SHA
    fields, records = read_csv(csv_bytes)
    assert len(records) == 811 and len(fields) == 107
    assert len({r["Product_Code"] for r in records}) == 811
    counts = Counter()
    with (out / "retail.jsonl").open("w", encoding="utf-8") as target:
        for rownum, row in enumerate(records, 1):
            values = [number(row[f"W{i}"]) for i in range(52)]
            assert all(isinstance(v, int) and v >= 0 for v in values)
            product = row["Product_Code"]
            for week in range(HISTORY, 52):
                inputs = {"product_code": product, "target_week_index": week,
                          "prior_weekly_purchased_quantities": values[week-HISTORY:week]}
                emit(target, {
                    "task_key": "next_week_purchased_quantity", "input": inputs, "label": values[week],
                    "group_key": product, "entity_id": product, "split": "unassigned",
                    "time_key": f"W{week:02d}", "target_week_index": week,
                    "history_end": f"W{week-1:02d}", "quality_flags": ["integer_count_target"],
                    "source_refs": [{"file": RETAIL_MEMBER, "archive": "raw/retail_weekly.zip",
                                     "row": rownum, "column": f"W{week}",
                                     "history_columns": [f"W{i}" for i in range(week-HISTORY, week)]}],
                })
                counts[str(week)] += 1
    assert sum(counts.values()) == 35684 and set(counts.values()) == {811}
    write_json(out / "retail.meta.json", {
        "dataset_id": "uci_396", "dataset_family": "uci_sales_transactions_weekly",
        "name": "Sales Transactions Weekly: next-week purchased quantity",
        "candidate_id": "B5-RETAIL", "source_url": RETAIL_PAGE, "creators": ["James Tan"],
        "source_citation": "Tan, J. (2014). Sales Transactions Weekly [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5XS4Q.",
        "version": "UCI 396 ZIP, SHA256-pinned, accessed 2026-11-26", "source_files": [source],
        "license": {"name": "CC BY 4.0", "url": CC_BY, "evidence": {"url": RETAIL_PAGE},
                    "scope": "Published anonymous product codes and weekly quantities. Preserve citation, licence and adaptation notice."},
        "raw_rows_selected": len(records), "candidate_task_examples": sum(counts.values()),
        "excluded_source_rows": 0, "invalid_label_examples": 0,
        "source_profile": {"source_columns": fields, "raw_product_rows": 811, "raw_weekly_observations": 42172,
                           "history_weeks": HISTORY, "target_week_range": [8, 51],
                           "windows_by_target_week": dict(counts), "csv_sha256": RETAIL_CSV_SHA},
        "excluded_input_columns": ["MIN", "MAX"] + [f"Normalized {i}" for i in range(52)],
        "target_transform": "next_observed_week_integer_quantity_no_transformation",
        "grouping_rule": "Product_Code identifies each complete 52-week product series. time_key uses zero-padded source week indices, not invented calendar dates.",
        "split_policy": "Unassigned. Rolling one-step proposal: target W08-W35 train (22708), W36-W43 validation (6488), W44-W51 test (6488). Previously observed quantities may supply later histories. For unseen-product evaluation, hold out entire product groups separately.",
        "quality_findings": [
            "The source is labelled as a clustering dataset. This release constructs a lag-8 one-step numerical prediction task from its raw observations.",
            "All whole-series MIN, MAX and Normalized columns are removed to prevent future-statistic leakage. The input never includes the target week quantity or a later observation.",
            "Counts are nonnegative integers; they are not physical continuous measurements, prices or revenue. Observed purchases need not equal unconstrained demand.",
            "There are only 52 source weeks and no stated calendar dates, store identifiers or product descriptions. Products are retained as anonymous IDs; no semantics are invented.",
            "References use 1-based CSV data rows excluding the header. Windows overlap by design, so do not randomly split windows when evaluating future-time prediction.",
        ],
        "tasks": {"next_week_purchased_quantity": {
            "target_name": "next_week_purchased_quantity", "unit": "purchased units per week", "type": "continuous",
            "instruction": "Predict the purchased quantity for this anonymous product in the next source week using its eight preceding weekly observations.",
            "field_description": "product_code is an anonymous source product identifier, without a product description. target_week_index is the requested zero-based source week (0-51), not a calendar date. prior_weekly_purchased_quantities contains eight nonnegative integer quantities, oldest to newest, for the eight immediately preceding weeks.",
        }},
    })


def audit(raw, out):
    """Read candidate files back and compare every value/window to source rows."""
    _, words = read_csv((raw / "lancaster_sensorimotor.csv").read_bytes())
    seen = set()
    groups = {}
    with (out / "lancaster.jsonl").open(encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            ref, = record["source_refs"]
            original = words[ref["row"] - 1]
            key = (ref["row"], record["task_key"])
            assert key not in seen
            seen.add(key)
            assert record["input"] == {"word": original["Word"]}
            assert record["label"] == float(original[ref["column"]])
            assert record["split"] == "unassigned"
            groups.setdefault(original["Word"], set()).add(record["group_key"])
    assert len(seen) == 119121 and len(groups) == 39707 and all(len(g) == 1 for g in groups.values())
    with ZipFile(raw / "retail_weekly.zip") as archive:
        _, products = read_csv(archive.read(RETAIL_MEMBER))
    retail_seen = set()
    with (out / "retail.jsonl").open(encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            ref, = record["source_refs"]
            original = products[ref["row"] - 1]
            week = record["target_week_index"]
            key = (ref["row"], week)
            assert key not in retail_seen
            retail_seen.add(key)
            assert record["label"] == int(original[f"W{week}"])
            assert record["input"] == {"product_code": original["Product_Code"], "target_week_index": week,
                "prior_weekly_purchased_quantities": [int(original[f"W{i}"]) for i in range(week-8, week)]}
            assert record["group_key"] == original["Product_Code"] and record["split"] == "unassigned"
            assert record["time_key"] == f"W{week:02d}" and record["history_end"] == f"W{week-1:02d}"
    assert len(retail_seen) == 35684
    report = {"status": "passed", "lancaster_candidates": len(seen), "lancaster_word_groups": len(groups),
              "retail_candidates": len(retail_seen), "retail_product_groups": len(products),
              "checks": ["Pinned raw SHA256", "All source rows accounted for", "All labels finite and in declared range",
                         "Full candidate-to-source label and input equality", "Three dimensions share word groups",
                         "Retail history ends before target", "All split values unassigned"], "training_executed": False}
    write_json(out / "language_retail.audit.json", report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    raw, out = map(Path, sys.argv[1:])
    out.mkdir(parents=True, exist_ok=True)
    lancaster(raw, out)
    retail(raw, out)
    audit(raw, out)
