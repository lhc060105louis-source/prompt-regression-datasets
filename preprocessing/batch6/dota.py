"""Turn a timestamp-aligned minute-ten snapshot into one remaining-time example per game."""
import csv
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile


RECORD = "https://zenodo.org/records/23166182"
SNAPSHOTS = "DB_03_Live_Features_ANALYSIS_v3.csv"
ARCHIVE = "Reproducibility_Experiment_211_Zenodo_v3.zip"
RESULTS = "Reproducibility_Experiment_211_v3/results/"
TIMES = RESULTS + "r1_time_axis_audit.csv"
DATES = RESULTS + "temporal_folds.csv"
CONSTANTS = "https://raw.githubusercontent.com/odota/dotaconstants/54d1b83415ab32d25cd55ac6f3f1c81d6170f8b5/"
HEROES = "opendota-heroes-54d1b83.json"
NOTICE = "opendota-54d1b83-LICENSE.txt"
TASK = "remaining_match_seconds"
PINNED_FILES = [
    (SNAPSHOTS, f"{RECORD}/files/{SNAPSHOTS}?download=1",
     "61b3852b5eedbf0f6f0688564dbd178238c22001741089eb64e736ad1102d044"),
    (ARCHIVE, f"{RECORD}/files/{ARCHIVE}?download=1",
     "8191d3ba57289ba79518ac66714766373525e898963e7ecac0971dd5d944b715"),
    (HEROES, CONSTANTS + "build/heroes.json",
     "d08b94dbaa70e0fe3e848f387a2380805418d77082ab58de181a7046c6f6bca3"),
    (NOTICE, CONSTANTS + "LICENSE",
     "13d8ee5053b6b9da5448fa298ff1af56cc3994b945e9739a5a38821ea7463abf"),
]


def source_inventory(work):
    inventory = []
    for filename, url, expected in PINNED_FILES:
        path = work / filename
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError(f"Source checksum mismatch for {filename}")
        inventory.append({"relativepath": filename, "url": url, "bytes": path.stat().st_size, "sha256": expected})
    return inventory


def match_index(bundle, filename, column):
    index = {}
    with bundle.open(filename) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as source:
        for number, row in enumerate(csv.DictReader(source), 1):
            match = row["match_id"]
            if match in index:
                raise ValueError(f"Multiple rows for match {match} in {filename}")
            index[match] = (number, int(row[column]))
    return index


def build(work, output):
    inventory = source_inventory(work)
    heroes = json.loads((work / HEROES).read_text(encoding="utf-8"))
    with ZipFile(work / ARCHIVE) as bundle:
        durations = match_index(bundle, TIMES, "duration")
        starts = match_index(bundle, DATES, "start_time")

    output.mkdir(parents=True, exist_ok=True)
    seen = set()
    with (work / SNAPSHOTS).open(encoding="utf-8-sig", newline="") as source, \
            (output / "dota.jsonl").open("w", encoding="utf-8") as dest:
        for number, row in enumerate(csv.DictReader(source), 1):
            if row["minute"] != "10":
                continue
            match = row["match_id"]
            duration_row, duration = durations[match]
            date_row, start = starts[match]
            if match in seen or duration <= 600:
                raise ValueError(f"Unexpected match or duration at snapshot row {number}")
            seen.add(match)
            # The source's slot order is unnecessary. Sort each team's draft by categorical ID.
            radiant = sorted(int(row[f"rad_h{i}"]) for i in range(1, 6))
            dire = sorted(int(row[f"dire_h{i}"]) for i in range(1, 6))
            if len(set(radiant + dire)) != 10:
                raise ValueError(f"Invalid draft at snapshot row {number}")
            inputs = {
                "radiant_heroes": [heroes[str(key)]["localized_name"] for key in radiant],
                "dire_heroes": [heroes[str(key)]["localized_name"] for key in dire],
                "radiant_earned_gold": int(row["rad_total_nw"]),
                "dire_earned_gold": int(row["dire_total_nw"]),
            }
            if min(inputs["radiant_earned_gold"], inputs["dire_earned_gold"]) <= 0:
                raise ValueError(f"Invalid team gold at snapshot row {number}")
            example = {
                "task_key": TASK, "input": inputs, "label": duration - 600,
                "group_key": match, "split": "unassigned",
                "time_key": datetime.fromtimestamp(start, timezone.utc).date().isoformat(),
                "source_refs": [
                    {"file": SNAPSHOTS, "row": number},
                    {"archive": ARCHIVE, "file": TIMES, "row": duration_row, "column": "duration"},
                    {"archive": ARCHIVE, "file": DATES, "row": date_row, "column": "start_time"},
                    {"file": HEROES, "keys": [str(key) for key in radiant + dire], "field": "localized_name"},
                ],
            }
            dest.write(json.dumps(example, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
    if number != 1007768 or seen != starts.keys():
        raise ValueError("The snapshot cohort differs from the v3 chronology")
    metadata = {
        "name": "Professional Dota 2 match time remaining at minute ten", "dataset_id": "dota2_pro",
        "dataset_family": "opendota_professional_matches", "candidate_id": "B6-DOTA2",
        "source_url": RECORD, "version": "Zenodo v3 (2026-10-05), OpenDota constants 54d1b834",
        "source_citation": "Luis Alberto Sanchez Calderon (2026). Analysis-Ready Live Match Feature "
                           "Snapshots for Professional Dota 2 (2023–2026), v3. DOI: 10.5281/zenodo.23166182. "
                           "Telemetry: OpenDota (https://www.opendota.com/). Hero names: The OpenDota Project, "
                           "odota/dotaconstants, revision 54d1b83415ab32d25cd55ac6f3f1c81d6170f8b5.",
        "license": {"name": "CC BY 4.0 (match data), MIT (OpenDota hero-name lookup)",
                    "url": "https://creativecommons.org/licenses/by/4.0/",
                    "hero_lookup": {"url": CONSTANTS + "LICENSE",
                                    "notice": (work / NOTICE).read_text(encoding="utf-8")}},
        "source_files": inventory, "raw_rows_selected": number, "excluded_source_rows": number - len(seen),
        "target_transform": "audited_match_duration_seconds_minus_600",
        "preparation": "Joined one minute-ten feature row per match to audited duration in seconds and UTC start "
                       "date by match_id. Mapped each team's hero IDs to English names with a pinned OpenDota "
                       "dictionary. The source's rad_total_nw and dire_total_nw sum the five players' gold_t "
                       "values at 600 seconds. Dates are stored for partitioning. The outcome, later snapshots "
                       "and final match duration are excluded from the model input.",
        "split_guidance": "Assign by UTC match start year. Train on 2023–2024, validate on 2025, test on the "
                          "2026 matches through March 18 inclusive. The split measures performance on later "
                          "matches. The same heroes, players or teams may recur over time.",
        "quality_findings": [
            "One example per professional match that lasts beyond ten minutes and has timestamp-aligned telemetry.",
            "Dataset v3 removes 1,849 matches with shifted or irregular economic timestamps from v2.",
            "Hero names identify the draft. Their list order is a stable identifier order, not pick order.",
        ],
        "excluded_input_columns": ["match_id", "duration", "duration_min", "radiant_win", "start_time", "block"],
        "tasks": {TASK: {"target_name": "remaining match duration after ten minutes", "unit": "seconds",
                         "type": "continuous",
                         "instruction": "At the ten-minute mark of this professional Dota 2 match, estimate how "
                                        "many more seconds will elapse before the match ends.",
                         "field_description": "radiant_heroes and dire_heroes list the five heroes drafted by each "
                                              "side. radiant_earned_gold and dire_earned_gold give the total gold "
                                              "earned by each side through minute ten."}},
    }
    (output / "dota.meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
