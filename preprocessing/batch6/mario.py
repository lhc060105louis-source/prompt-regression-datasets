"""Build approximately one-month course clear rates from SMMnet observation pairs."""

import csv
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import sys
from typing import NamedTuple
from zipfile import ZipFile


ARCHIVE = "smmnet-v1.zip"
SHA256 = "feb220c673e57e2ed8b13fbc61b5242b4301372fe3905c75a546004bed4cb624"
SOURCE = "https://www.kaggle.com/datasets/leomauro/smmnet"
DOWNLOAD = "https://api.kaggle.com/v1/datasets/download/leomauro/smmnet?datasetVersionNumber=1"
COURSES = "courses.csv"
SNAPSHOTS = "course-meta.csv"
TASK = "future_clear_rate"
STYLES = {
    "marioBros": "Super Mario Bros.",
    "marioBros3": "Super Mario Bros. 3",
    "marioWorld": "Super Mario World",
    "marioBrosU": "New Super Mario Bros. U",
}


class Snapshot(NamedTuple):
    date: datetime
    row: int
    attempts: int
    clears: int
    players: int


def read_table(bundle, name):
    with bundle.open(name) as member, io.TextIOWrapper(member, encoding="utf-8", newline="") as data:
        yield from enumerate(csv.DictReader(data, delimiter="\t"), 1)


def select_pair(snapshots):
    first = min(snapshots, key=lambda s: s.date)
    if first.attempts < 10 or not 0 <= first.clears <= first.attempts:
        return None
    earliest = first.date + timedelta(days=23)
    latest = first.date + timedelta(days=37)
    target = first.date + timedelta(days=30)
    eligible = (s for s in snapshots if earliest <= s.date <= latest)
    last = min(eligible, key=lambda s: (abs(s.date - target), s.date), default=None)
    if last is None:
        return None
    attempts = last.attempts - first.attempts
    clears = last.clears - first.clears
    if attempts < 20 or not 0 <= clears <= attempts:
        return None
    return first, last, 100 * clears / attempts


def build(work, output):
    archive = work / ARCHIVE
    digest = hashlib.sha256()
    with archive.open("rb") as data:
        for chunk in iter(lambda: data.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != SHA256:
        raise ValueError("Expected the SMMnet version 1 archive published on May 13, 2019.")

    output.mkdir(parents=True, exist_ok=True)
    observations = defaultdict(list)
    with ZipFile(archive) as bundle:
        for row_number, row in read_table(bundle, SNAPSHOTS):
            date = row["catch"]
            timestamp_format = "%Y-%m-%d %H:%M:%S.%f" if "." in date else "%Y-%m-%d %H:%M:%S"
            observations[row["id"]].append(Snapshot(
                datetime.strptime(date, timestamp_format), row_number,
                int(row["attempts"]), int(row["clears"]), int(row["players"]),
            ))
        n_snapshots = row_number
        prepared = 0
        seen_courses = set()
        with (output / "mario.jsonl").open("w", encoding="utf-8") as dest:
            for row_number, course in read_table(bundle, COURSES):
                course_id = course["id"]
                if course_id in seen_courses:
                    raise ValueError(f"Duplicate course ID at {COURSES} row {row_number}")
                seen_courses.add(course_id)
                maker = course["maker"].strip().casefold()
                snapshots = observations.get(course_id, [])
                if not maker or len(snapshots) < 2:
                    continue
                pair = select_pair(snapshots)
                if pair is None:
                    continue
                first, last, percent = pair
                record = {
                    "task_key": TASK,
                    "input": {
                        "game_style": STYLES[course["gameStyle"]],
                        "initial_attempts": first.attempts,
                        "initial_clears": first.clears,
                        "initial_players": first.players,
                    },
                    "label": percent,
                    "group_key": hashlib.sha256(maker.encode("utf-8")).hexdigest(),
                    "split": "unassigned",
                    "source_refs": [
                        {"file": COURSES, "row": row_number, "course_id": course_id, "role": "course"},
                        {"file": SNAPSHOTS, "row": first.row, "course_id": course_id, "role": "baseline"},
                        {"file": SNAPSHOTS, "row": last.row, "course_id": course_id, "role": "follow_up"},
                    ],
                }
                dest.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                prepared += 1
    n_courses = len(seen_courses)
    if (n_courses, n_snapshots, prepared) != (115032, 292298, 2677):
        raise ValueError(f"Unexpected SMMnet counts: {n_courses}, {n_snapshots}, {prepared}")
    metadata = {
        "name": "Super Mario Maker future course clear rate (SMMnet)",
        "dataset_id": "smmnet", "dataset_family": "smmnet_course_snapshots",
        "candidate_id": "B6-SMM", "source_url": SOURCE, "version": "Kaggle v1, 2019-05-13",
        "source_citation": "Leonardo Mauro Pereira Moraes and Robson Leonardo Ferreira Cordeiro. "
                           "SMMnet: A Social Network of Games Dataset. SBBD Dataset Showcase Workshop, 2019. "
                           "Source telemetry from Nintendo's Super Mario Maker Bookmark.",
        "license": {"name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/",
                    "data_license_evidence": SOURCE, "author_attribution": "https://github.com/leomaurodesenv/smmnet#citation"},
        "source_files": [{"relativepath": ARCHIVE, "url": DOWNLOAD, "sha256": SHA256, "bytes": archive.stat().st_size}],
        "raw_rows_selected": n_courses, "excluded_source_rows": n_courses - prepared,
        "source_table_rows": {COURSES: n_courses, SNAPSHOTS: n_snapshots},
        "target_transform": "100 * (follow_up_clears - baseline_clears) / (follow_up_attempts - baseline_attempts)",
        "preparation": "One observation pair per course ID. At the earliest observed snapshot require at least "
                       "10 attempts. Select the snapshot 23 to 37 days later closest to day 30, choosing the "
                       "earlier snapshot for ties. Require at least 20 new attempts and valid clear counts. "
                       "The static style and three cumulative baseline counts are available at forecast time. "
                       "Provenance rows are 1-based data records in the two tab-separated archive members.",
        "split_guidance": "The suggested split sorts released group IDs and allocates whole groups 70/15/15 "
                          "by largest remainder. A group links courses from the same normalized maker ID and "
                          "courses with identical model-visible inputs.",
        "quality_findings": [
            "The target describes courses observed again about a month later with at least 20 further attempts. "
            "The released cohort therefore represents active courses with observed follow-up.",
            "Repeated attempts by the same player are part of the denominator. The initial snapshot may be later "
            "than the course creation date. The published difficulty, later counts and original clear-rate field "
            "are excluded from the inputs.",
        ],
        "tasks": {TASK: {
            "target_name": "future course clear rate", "unit": "percent", "type": "continuous",
            "instruction": "Estimate what percentage of new attempts at this Super Mario Maker course will "
                           "clear it over approximately the next 30 days. Return a percentage from 0 to 100.",
            "field_description": "game_style names the course's game style. initial_attempts counts attempts, "
                                 "initial_clears counts successful attempts, and initial_players counts players, "
                                 "all as recorded at the first observation.",
        }},
    }
    (output / "mario.meta.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
