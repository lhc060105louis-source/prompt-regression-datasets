"""Prepare StarCraft II replay APM targets from the UCI SkillCraft1 table."""
import csv
import hashlib
import io
import json
import math
import sys
from pathlib import Path
from zipfile import ZipFile


ARCHIVE = "skillcraft1-uci272.zip"
MEMBER = "SkillCraft1_Dataset.csv"
SHA256 = "d6f4f88c2d077a0938cf774ff242df511c9a5801dcc66e4461ffdf893ce23fc2"
SOURCE = "https://archive.ics.uci.edu/dataset/272/skillcraft1+master+table+dataset"
DOWNLOAD = "https://archive.ics.uci.edu/static/public/272/skillcraft1+master+table+dataset.zip"
TASK = "actions_per_minute"
PROFILE_COLUMNS = ("LeagueIndex", "Age", "HoursPerWeek", "TotalHours")


def build(work: Path, output: Path):
    archive = work / ARCHIVE
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError(f"Expected the pinned UCI SkillCraft1 archive at {archive}")
    output.mkdir(parents=True, exist_ok=True)
    missing = implausible = rows = 0
    with ZipFile(archive) as bundle, bundle.open(MEMBER) as member, \
            io.TextIOWrapper(member, encoding="utf-8-sig", newline="") as source, \
            (output / "starcraft.jsonl").open("w", encoding="utf-8") as dest:
        for rows, row in enumerate(csv.DictReader(source), 1):
            if any(row[key] in {"", "?"} for key in PROFILE_COLUMNS):
                missing += 1
                continue
            league, age, weekly, total = (int(row[key]) for key in PROFILE_COLUMNS)
            if not (1 <= league <= 8 and age > 0 and 0 <= weekly <= 168
                    and 0 <= total <= age * 365.25 * 24):
                implausible += 1
                continue
            apm = float(row["APM"])
            if not math.isfinite(apm) or apm < 0:
                raise ValueError(f"Invalid APM at {MEMBER} data row {rows}")
            example = {
                "task_key": TASK,
                "input": {"league_index": league, "age_years": age,
                          "hours_played_per_week": weekly, "total_hours_played": total},
                "label": apm,
                "group_key": f"{league},{age},{weekly},{total}",
                "split": "unassigned",
                "source_refs": [{"file": MEMBER, "column": "APM", "row": rows}],
            }
            dest.write(json.dumps(example, separators=(",", ":"), allow_nan=False) + "\n")
    if (rows, missing, implausible) != (3395, 57, 1):
        raise ValueError(f"Unexpected source, missing profile, or invalid profile counts: {rows}, {missing}, {implausible}")
    metadata = {
        "name": "SkillCraft1 StarCraft II replay actions per minute",
        "dataset_id": "uci_272",
        "dataset_family": "skillcraft1_starcraft_ii_replays",
        "candidate_id": "B6-SC2",
        "source_url": SOURCE,
        "version": "UCI dataset 272, donated 2013-10-21, pinned static ZIP",
        "source_citation": (
            "Blair, M., Thompson, J., Henrey, A., and Chen, B. (2013). "
            "SkillCraft1 Master Table Dataset. UCI Machine Learning Repository. "
            "https://doi.org/10.24432/C5161N. Study: https://doi.org/10.1371/journal.pone.0075129"
        ),
        "license": {"name": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
                    "url": "https://creativecommons.org/licenses/by/4.0/", "evidence": SOURCE},
        "source_files": [{"url": DOWNLOAD, "relativepath": ARCHIVE,
                          "bytes": archive.stat().st_size, "sha256": SHA256}],
        "raw_rows_selected": rows,
        "excluded_source_rows": missing + implausible,
        "target_transform": "none_applied",
        "preparation": (
            "Read the numeric APM from each eligible replay and retain four background fields. "
            "Drop 57 incomplete profiles and one record whose reported playtime exceeds the player's "
            "lifetime. No same-replay action counts, timing statistics or game identifiers enter the prompt."
        ),
        "split_guidance": (
            "Keep matching four-field profiles in one group. Sort released group IDs, then allocate "
            "70%, 15% and 15% of groups to train, validation and test by largest remainder. "
            "The study collected one replay per respondent. GameID identifies a replay in the public table."
        ),
        "quality_findings": [
            "All 55 Professional-league rows lack age and playtime information. The released cohort "
            "spans Bronze through GrandMaster.",
            "Playtime is self-reported. Different replays can have the same profile and different APM.",
        ],
        "tasks": {TASK: {
            "target_name": "mean in-game actions per minute",
            "unit": "actions per minute",
            "type": "continuous",
            "instruction": "Estimate the player's average number of actions per minute in this StarCraft II replay.",
            "field_description": (
                "league_index is the ranked league: 1 Bronze, 2 Silver, 3 Gold, 4 Platinum, "
                "5 Diamond, 6 Master, 7 GrandMaster, 8 Professional. age_years is the player's age "
                "in years. hours_played_per_week and total_hours_played are self-reported weekly and "
                "lifetime StarCraft II playtime, both in hours."
            ),
        }},
    }
    (output / "starcraft.meta.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
