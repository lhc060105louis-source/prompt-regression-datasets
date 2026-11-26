"""Prepare adult IPF-affiliate raw three-lift competition results from a pinned export."""
import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from zipfile import ZipFile


SNAPSHOT = "openipf-2026-11-21.zip"
MEMBER = "openipf-2026-11-21/openipf-2026-11-21-fb43e52f.csv"
SHA256 = "9633dfd0930c131ccdbaffc197320c2e3e9276fedbc1ecb7228d5d4ac20aae79"
SOURCE = "https://openpowerlifting.gitlab.io/opl-csv/"
TASK = "best_deadlift"


def build(work, output):
    archive = work / SNAPSHOT
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError("Expected the OpenIPF snapshot dated 2026-11-21, revision fb43e52f.")
    output.mkdir(parents=True, exist_ok=True)
    eligible = 0
    with ZipFile(archive) as bundle, bundle.open(MEMBER) as member, \
            io.TextIOWrapper(member, encoding="utf-8-sig", newline="") as source, \
            (output / "openipf.jsonl").open("w", encoding="utf-8") as dest:
        for row_number, row in enumerate(csv.DictReader(source), 1):
            if not ("2015-01-01" <= row["Date"] <= "2024-12-31"
                    and row["Event"] == "SBD" and row["Equipment"] == "Raw"):
                continue
            age = float(row["Age"] or 0)
            bodyweight = float(row["BodyweightKg"] or 0)
            deadlift = float(row["Best3DeadliftKg"] or 0)
            if age < 18 or bodyweight <= 0 or deadlift <= 0:
                continue
            if not row["Name"]:
                raise ValueError(f"Missing athlete grouping key at row {row_number}.")
            inputs = {"age_years": age, "bodyweight_kg": bodyweight,
                      "competition_sex": row["Sex"], "meet_date": row["Date"],
                      "federation": row["Federation"], "meet_country": row["MeetCountry"],
                      "meet_state": row["MeetState"] or None, "meet_town": row["MeetTown"] or None}
            example = {"task_key": TASK, "input": inputs, "label": deadlift,
                       "group_key": hashlib.sha256(row["Name"].encode()).hexdigest(),
                       "time_key": row["Date"], "split": "unassigned",
                       "source_refs": [{"file": MEMBER, "column": "Best3DeadliftKg", "row": row_number}]}
            dest.write(json.dumps(example, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
            eligible += 1
    if (row_number, eligible) != (1540272, 326853):
        raise ValueError(f"Unexpected cohort counts: {row_number}, {eligible}")
    metadata = {
        "name": "OpenIPF adult raw three-lift deadlift results", "dataset_id": "openipf",
        "dataset_family": "openpowerlifting_competition_results", "candidate_id": "B5-IPF",
        "source_url": SOURCE + "bulk-csv.html", "version": "OpenIPF 2026-11-21, revision fb43e52f",
        "source_citation": "OpenPowerlifting project and contributors. OpenIPF IPF-affiliate results, 2026-11-21. https://www.openpowerlifting.org/",
        "license": {"name": "Competition data dedicated to the Public Domain", "url": SOURCE,
                    "archive_evidence": "openipf-2026-11-21/LICENSE.txt"},
        "source_files": [{"url": SOURCE + "files/openipf-latest.zip", "relativepath": SNAPSHOT,
                          "bytes": archive.stat().st_size, "sha256": SHA256}],
        "raw_rows_selected": row_number, "excluded_source_rows": row_number - eligible,
        "target_transform": "reported_best_successful_deadlift_from_first_three_attempts_in_kg",
        "preparation": "Selected adult Raw SBD entries in 2015–2024 with known positive bodyweight and best deadlift. Used pre-lift attributes only. Omitted division because multiple divisions can register the same performance. Matching task/input/label occurrences are merged with their row references.",
        "split_guidance": "Use whole group_id holdouts to evaluate unfamiliar athletes. Groups join repeated source-disambiguated athlete names and identical inputs. Homonyms or aliases in the source may affect identity resolution. For forecasting later meets, split on meet_date and state how repeated athletes are treated.",
        "quality_findings": ["The source may give approximate fractional ages. Age is the reported value.",
                             "Results describe competitors with a successful recorded deadlift. They do not cover all entrants.",
                             "Different recorded outcomes for the same visible inputs are retained. The original athlete names, divisions, placing, attempted lifts, totals and derived scores are absent from the prompt."],
        "tasks": {TASK: {"target_name": "best successful deadlift", "unit": "kg", "type": "continuous",
                         "instruction": "Estimate this adult competitor's best successful deadlift in the first three attempts at a raw three-lift powerlifting meet.",
                         "field_description": "age_years is the reported age. bodyweight_kg is the weigh-in mass. competition_sex is the source competition category. meet_date is the competition date. federation and the meet country, state and town describe the competition setting."}}
    }
    (output / "openipf.meta.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
