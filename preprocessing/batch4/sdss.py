"""Build the fixed SDSS-IV DR17 spectroscopic galaxy subsample from SkyServer."""
import argparse
import csv
import hashlib
import json
import math
import subprocess
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

ENDPOINT = "https://skyserver.sdss.org/dr17/SkyServerWS/SearchTools/SqlSearch"
RELEASE = "https://www.sdss4.org/dr17/"
POLICY = "https://www.sdss4.org/collaboration/image-use-policy/"
BANDS = "ugriz"
TASK = "galaxy_spectroscopic_redshift"
FIELDS = [
    "objID", "ra", "dec", *["dered_" + b for b in BANDS],
    *["modelMagErr_" + b for b in BANDS], "specObjID", "redshift",
    "zErr", "class", "zWarning", "plate", "mjd", "fiberID", "survey", "sliceCount",
]
# SELECT MIN(plate), MAX(plate) FROM SpecObj returns 266, 12547 in DR17.
BLOCK_STARTS = range(1, 12502, 500)


def sql(start):
    return (
        "SELECT p.objID,p.ra,p.dec,p.dered_u,p.dered_g,p.dered_r,p.dered_i,p.dered_z,"
        "p.modelMagErr_u,p.modelMagErr_g,p.modelMagErr_r,p.modelMagErr_i,p.modelMagErr_z,"
        "s.specObjID,s.z AS redshift,s.zErr,s.class,s.zWarning,s.plate,s.mjd,s.fiberID,"
        "s.survey,COUNT(*) OVER () AS sliceCount FROM SpecObj s "
        "JOIN PhotoObj p ON s.bestObjID=p.objID WHERE p.clean=1 AND p.mode=1 "
        "AND s.class='GALAXY' AND s.zWarning=0 AND s.zErr>0 AND s.z>0 "
        f"AND s.fiberID%43=s.plate%43 AND s.plate BETWEEN {start} AND {start+499} "
        "ORDER BY s.specObjID"
    )


def query_url(start):
    return ENDPOINT + "?" + urlencode({"cmd": sql(start), "format": "csv"})


def block_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if stream.readline().strip() != "#Table1":
            raise ValueError(f"SkyServer response is not a CSV result: {path}")
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"Unexpected result columns in {path}: {reader.fieldnames!r}")
        rows = list(reader)
    if any(None in row or int(row["sliceCount"]) != len(rows) for row in rows):
        raise ValueError(f"Incomplete query response: {path}")
    return rows


def acquire(start, directory):
    filename = f"dr17-plates-{start:05d}-{start+499:05d}.csv"
    path = directory / filename
    if not path.exists():
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            subprocess.run(
                ["curl", "--fail", "--silent", "--show-error", "--location",
                 "--retry", "3", "--max-time", "180", query_url(start), "--output", str(tmp_path)],
                check=True,
            )
            block_rows(tmp_path)
            tmp_path.replace(path)
        finally:
            tmp_path.unlink(missing_ok=True)
    return path


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def candidate(row, path, index):
    if row["class"] != "GALAXY" or int(row["zWarning"]) != 0:
        raise ValueError("Unexpected spectroscopic quality in source")
    if not (0 < float(row["redshift"]) < math.inf and 0 < float(row["zErr"]) < math.inf):
        raise ValueError("Unexpected redshift quality in source")
    magnitudes = {b: float(row["dered_" + b]) for b in BANDS}
    errors = {b: float(row["modelMagErr_" + b]) for b in BANDS}
    # Explicit broad plausibility bounds remove catalog sentinels and ill-determined fits.
    if not (all(-10 < x < 40 for x in magnitudes.values()) and all(0 < x < 5 for x in errors.values())):
        return None
    ra, dec = float(row["ra"]), float(row["dec"])
    if not 0 <= ra < 360 or not -90 <= dec <= 90:
        raise ValueError("Invalid celestial coordinates")
    sky_cell = f"ra{int(ra//5):02d}-dec{min(35,int((dec+90)//5)):02d}"
    return {
        "input": {"dereddened_model_magnitude": magnitudes, "model_magnitude_error": errors},
        "label": float(row["redshift"]), "task_key": TASK, "entity_id": row["objID"],
        "group_key": sky_cell, "sky_cell_5deg": sky_cell, "split": "unassigned",
        "source_refs": [{"file": path.name, "row": index, "specObjID": row["specObjID"],
                         "objID": row["objID"], "plate": int(row["plate"]), "mjd": int(row["mjd"]),
                         "fiberID": int(row["fiberID"]), "survey": row["survey"]}],
    }


def build(raw_dir, out_dir):
    directory = raw_dir / "sdss"
    directory.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        paths = list(pool.map(lambda start: acquire(start, directory), BLOCK_STARTS))
    seen_objects = set()
    surveys = Counter()
    cells = Counter()
    rejected = Counter()
    source_files = []
    source_count = 0
    bounds = [math.inf, -math.inf]
    with (out_dir / "sdss.jsonl").open("w", encoding="utf-8", newline="\n") as out:
        for start, path in zip(BLOCK_STARTS, paths):
            rows = block_rows(path)
            if [int(r["specObjID"]) for r in rows] != sorted(int(r["specObjID"]) for r in rows):
                raise ValueError("Non-deterministic spectrum order")
            source_files.append({"relativepath": path.relative_to(raw_dir).as_posix(), "url": query_url(start),
                                 "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                 "rows": len(rows)})
            source_count += len(rows)
            for index, row in enumerate(rows, 1):
                if not (start <= int(row["plate"]) < start + 500 and int(row["fiberID"]) % 43 == int(row["plate"]) % 43):
                    raise ValueError("Sample outside published cohort rule")
                record = candidate(row, path, index)
                if record is None:
                    rejected["photometry_outside_validity_cuts"] += 1
                    continue
                if row["objID"] in seen_objects:
                    rejected["repeated_photometric_object"] += 1
                    continue
                seen_objects.add(row["objID"])
                cells[record["group_key"]] += 1
                surveys[row["survey"]] += 1
                bounds = [min(bounds[0], record["label"]), max(bounds[1], record["label"])]
                out.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
    if len(seen_objects) + sum(rejected.values()) != source_count or not seen_objects:
        raise ValueError("Source count mismatch or empty selection")
    meta = {
        "dataset_id": "sdss_dr17", "name": "SDSS-IV DR17 Galaxy Spectroscopic Redshift", "candidate_id": "SDSS",
        "source_url": RELEASE, "version": "SDSS-IV DR17, SkyServer plate-fiber subsample v1",
        "license": {"name": "Public domain (SDSS public data releases)", "url": POLICY},
        "source_citation": {"authors": ["SDSS Collaboration", "Abdurro’uf et al."], "doi": "10.3847/1538-4365/ac4414",
                            "acknowledgments": "https://www.sdss4.org/collaboration/citing-sdss/"},
        "source_files": source_files, "raw_rows_selected": source_count,
        "candidate_task_examples": len(seen_objects), "excluded_source_rows": sum(rejected.values()),
        "invalid_label_examples": 0, "grouping_rule": "5-degree RA/Dec rectangular sky cells after unique object selection",
        "split_policy": "unassigned; reserve entire sky cells for regional generalization",
        "excluded_input_columns": ["classification", "spectroscopic redshift", "redshift error", "quality flags",
                                   "coordinates", "survey", "plate", "mjd", "fiberID", "object and spectrum identifiers"],
        "quality_findings": [
            "Fixed systematic subsample of clean primary photometric objects matched to primary spectroscopic GALAXY observations with unflagged positive redshift and positive formal error. One fiber residue per plate (modulo 43), not a volume-complete or random sample of the sky.",
            "Require all five corrected model magnitudes within (-10,40) mag and catalog model-magnitude errors within (0,5) mag. First passing source row in plate-block and ascending spectrum ID order per photometric object.",
            "Parent DR17 optical catalog coverage and spectroscopic target selection determine representativeness. The label is measured spectroscopically; no spectroscopic quantities enter the model input.",
            "Sky cells are rectangular coordinate bins, not equal-area. Adjacent cells can contain correlated objects.",
        ],
        "source_profile": {"excluded_by_reason": dict(rejected), "surveys": dict(surveys), "occupied_sky_cells": len(cells),
                           "redshift_range": bounds, "query_plate_range": [1, 13000]},
        "target_transform": "none_applied",
        "tasks": {TASK: {"instruction": "Estimate the spectroscopic redshift of an SDSS galaxy from its broadband photometry.",
                         "target_name": "spectroscopic redshift", "unit": "dimensionless", "type": "continuous",
                         "field_description": "dereddened_model_magnitude gives extinction-corrected SDSS model magnitudes in the u, g, r, i, and z imaging filters. model_magnitude_error gives the reported model photometry error per filter, in magnitudes. The z filter is a photometric band."}},
    }
    write_json(out_dir / "sdss.meta.json", meta)
    print(f"SDSS: {source_count} selected source rows, {len(seen_objects)} candidate records, exclusions {dict(rejected)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_dir", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    build(args.raw_dir, args.out_dir)
