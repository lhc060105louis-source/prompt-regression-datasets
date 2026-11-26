"""Build trial-level treadmill force and minute-level PPG respiratory-rate candidates."""
import argparse
import csv
import hashlib
import json
import math
import re
from bisect import bisect_left
from collections import Counter
from pathlib import Path

FIG_API = "https://api.figshare.com/v2/articles/4543435/versions/5"
PN_FILES = "https://physionet.org/files/bidmc/1.0.0/"
PN_PAGE = "https://physionet.org/content/bidmc/1.0.0/"
FREQUENCY = 125
MINUTE = 60 * FREQUENCY


def inventory(path, root, url, algo=None, expected=None):
    data = path.read_bytes()
    if algo and hashlib.new(algo, data).hexdigest() != expected:
        raise ValueError(f"Publisher checksum mismatch in {path.name}")
    return dict(relativepath=path.relative_to(root).as_posix(), url=url,
                sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def save(out, name, rows, metadata):
    out.mkdir(parents=True, exist_ok=True)
    with (out / (name + ".jsonl")).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    metadata.update(candidate_task_examples=len(rows), invalid_label_examples=0)
    (out / (name + ".meta.json")).write_text(
        json.dumps(metadata, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def group_key(dataset, value):
    return hashlib.sha256(f"{dataset}/{value}".encode()).hexdigest()[:20]


def fukuchi(root, out):
    directory = root / "fukuchi"
    catalog_path = directory / "version5.json"
    catalog = json.loads(catalog_path.read_bytes())
    assert catalog["version"] == 5 and catalog["license"]["name"] == "CC BY 4.0"
    files = [inventory(catalog_path, root, FIG_API)]
    info, = [item for item in catalog["files"] if item["id"] == 39452932]
    files.append(inventory(directory / info["name"], root, info["download_url"], "md5", info["computed_md5"]))
    with (directory / info["name"]).open(encoding="utf-8-sig", newline="") as f:
        meta_rows = list(csv.DictReader(f, delimiter="\t"))
    by_trial = {r["FileName"]: (i, r) for i, r in enumerate(meta_rows, 1)}
    trials = sorted((r for r in catalog["files"] if r["name"].endswith("forces.txt")), key=lambda r:r["name"])
    rows = []
    counts = Counter()
    force_rows = 0
    for item in trials:
        name = item["name"]
        parsed = re.fullmatch(r"RBDS(\d+)runT(25|35|45)forces\.txt", name)
        if not parsed:
            raise ValueError(name)
        path = directory / name
        files.append(inventory(path, root, item["download_url"], "md5", item["computed_md5"]))
        info_row, runner = by_trial[name]
        assert int(runner["Subject"]) == int(parsed[1])
        speed = int(parsed[2]) / 10
        with path.open(encoding="ascii", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            values = [float(r["Fy"]) for r in reader]
        if len(values) < 2 or not all(math.isfinite(x) for x in values):
            raise ValueError(f"Invalid force trial {name}")
        force_rows += len(values)
        counts[speed] += 1
        label = sorted(values)[math.ceil(.95 * len(values)) - 1]
        input_data = dict(speed_m_s=speed, height_cm=float(runner["Height"]), body_mass_kg=float(runner["Mass"]),
                          running_level=runner["Level"], training_sessions_per_week=int(runner["SessionsPerWk"]))
        rows.append(dict(task_key="vertical_force_p95", input=input_data, label=label, split="unassigned",
                         group_key=group_key("fukuchi", runner["Subject"]),
                         source_refs=[dict(file=name, row=1, last_row=len(values), column="Fy"),
                                      dict(file=info["name"], row=info_row)]))
    assert counts == {2.5: 31, 3.5: 39, 4.5: 31} and len({r["group_key"] for r in rows}) == 39
    save(out, "fukuchi", rows, dict(dataset_id="fukuchi_running", dataset_family="fukuchi_running",
        name="Fukuchi treadmill running biomechanics", candidate_id="B5-FUKUCHI",
        version="Figshare version 5; participant metadata file 39452932", source_url="https://doi.org/" + catalog["doi"],
        source_files=files, license=dict(name="CC BY 4.0", url=catalog["license"]["url"]),
        source_citation=dict(authors=[x["full_name"] for x in catalog["authors"]],
                             doi=catalog["doi"], paper="https://doi.org/10.7717/peerj.3298"),
        raw_rows_selected=force_rows, excluded_source_rows=0, source_profile=dict(
            trials=len(rows), runners=39, metadata_rows=len(meta_rows), trials_per_speed=dict(counts)),
        target_transform="Nearest-rank 95th percentile of every Fy sample in one original raw treadmill trial.",
        split_policy="Unassigned. Split by runner with all speeds from a person together.",
        grouping_rule="Hashed runner identifier shared by all trials of the same participant.",
        quality_findings=["The v5 sample includes 39 runners. The original paper analyzed an earlier subset.",
                          "Labels summarize absolute vertical forces in newtons on this treadmill, including swing phases. This statistic differs from the average of stride peaks."],
        tasks=dict(vertical_force_p95=dict(type="continuous",
            target_name="95th percentile vertical ground reaction force", unit="N",
            instruction="Estimate the 95th percentile of vertical ground reaction force over this treadmill running trial.",
            field_description="speed_m_s is the imposed treadmill speed. Height is in centimeters and body mass in kilograms. running_level and training_sessions_per_week are recorded participant characteristics."))))


def read_markers(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        data = csv.reader(f)
        assert [c.strip() for c in next(data)] == ["breaths ann1 [signal sample no]", "breaths ann2 [signal sample no]"]
        columns = [[], []]
        for row_idx, row in enumerate(data, 1):
            for k, v in enumerate(row):
                if v.strip().lower() in ("", "nan"):
                    continue
                columns[k].append((int(v), row_idx))
    for col in columns:
        if not col or any(x[0] < 1 or x[0] > 60001 for x in col):
            raise ValueError(f"Invalid annotation list in {path.name}")
    return [sorted(col) for col in columns]


def read_ppg(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        data = csv.reader(f, skipinitialspace=True)
        columns = [v.strip() for v in next(data)]
        idx = columns.index("PLETH")
        time = columns.index("Time [s]")
        values = []
        for i, row in enumerate(data):
            # The time column has limited significant digits at late time points.
            if abs(float(row[time]) - i / FREQUENCY) >= .006:
                raise ValueError(f"Unexpected sample timing in {path.name} row {i+1}")
            values.append(float(row[idx]) if row[idx].strip() else math.nan)
        if len(values) not in (60000, 60001):
            raise ValueError(f"Unexpected recording length in {path.name}: {len(values)}")
        return values


def bidmc(root, out):
    directory = root / "bidmc"
    sha_file = directory / "SHA256SUMS.txt"
    hashes = dict(reversed(s.split()) for s in sha_file.read_text().splitlines())
    files = [inventory(sha_file, root, PN_FILES + sha_file.name)]
    rows = []
    excluded = Counter()
    source_samples = 0
    duplicated_marks = 0
    endpoints = 0
    groups = set()
    for k in range(1,54):
        stem = f"bidmc_{k:02d}_"
        for suffix in ("Fix.txt", "Breaths.csv", "Signals.csv"):
            name = stem + suffix
            key = "bidmc_csv/" + name
            files.append(inventory(directory / name, root, PN_FILES + key, "sha256", hashes[key]))
        fix = (directory / (stem + "Fix.txt")).read_text()
        subject = re.search(r"(?im)^MIMIC II matched wdb ID:\s*(s\d+)\s*$", fix)[1]
        group = group_key("bidmc", subject)
        groups.add(group)
        columns = read_markers(directory / (stem + "Breaths.csv"))
        signal = read_ppg(directory / (stem + "Signals.csv"))
        source_samples += len(signal)
        endpoints += len(signal) - 8 * MINUTE
        for minute in range(8):
            a, b = minute * MINUTE, (minute + 1) * MINUTE
            segment = signal[a:b]
            counts, annotation_rows = [], []
            for col in columns:
                marks = [x[0] for x in col]
                # CSV sample 1 is zero seconds; a 60-second interval is [a+1,b+1) in CSV sample numbers.
                lo, hi = bisect_left(marks, a+1), bisect_left(marks, b+1)
                retained = col[lo:hi]
                unique_samples = len({x[0] for x in retained})
                counts.append(unique_samples)
                duplicated_marks += len(retained) - unique_samples
                annotation_rows.append(sorted(x[1] for x in retained))
            if not all(math.isfinite(x) for x in segment):
                excluded["nonfinite_pleth"] += 1
                continue
            if max(segment) == min(segment):
                excluded["flat_pleth"] += 1
                continue
            if min(counts) < 2:
                excluded["fewer_than_two_marks_from_either_annotator"] += 1
                continue
            # 25 source points per bin, 300 means per minute. Only PLETH enters this representation.
            feature = [math.fsum(segment[i:i+25])/25 for i in range(0, MINUTE, 25)]
            rows.append(dict(task_key="manual_respiratory_rate", input=dict(pleth_5hz_mean=feature),
                label=sum(counts)/2, group_key=group, split="unassigned",
                source_refs=[dict(file=stem+"Signals.csv", row=a+1, last_row=b, column="PLETH"),
                             dict(file=stem+"Breaths.csv", row=min(x[0] for x in annotation_rows), ann1_rows=annotation_rows[0], ann2_rows=annotation_rows[1])],
                time_key={"recording": k, "window_start_s": minute*60}, annotator_breath_counts=counts,
                quality_flags=["annotator_counts_differ_by_more_than_two"] if abs(counts[0]-counts[1])>2 else []))
    assert len(rows)+sum(excluded.values()) == 424
    save(out, "bidmc", rows, dict(dataset_id="bidmc_ppg", dataset_family="mimic_ii_matched_waveform",
        name="BIDMC PPG and manually annotated respiratory rate", candidate_id="B5-BIDMC",
        version="PhysioNet 1.0.0", source_url=PN_PAGE, source_files=files,
        license=dict(name="Open Data Commons Attribution License v1.0", url="https://physionet.org/content/bidmc/view-license/1.0.0/",
            source_notice=PN_FILES+"LICENSE", upstream_notice="https://archive.physionet.org/copying.shtml#data",
            modifications="The authors extracted eight-minute segments from 53 MIMIC-II matched waveform ICU stays, manually annotated breaths twice on the impedance waveform and exported multiple formats. This adaptation uses PPG-only five-Hz block means and the mean manual breath count in one-minute windows."),
        source_citation=dict(authors=["Marco Pimentel","Alistair Johnson","Peter Charlton","David Clifton"],
                             doi="10.13026/C2208R", paper="https://doi.org/10.1109/TBME.2016.2613124", repository="PhysioNet"),
        raw_rows_selected=source_samples, excluded_source_rows=endpoints,
        source_profile=dict(recordings=53, subject_groups=len(groups), considered_windows=424,
                            excluded_windows=dict(excluded), endpoint_samples_outside_windows=endpoints,
                            repeated_within_annotator_marks=duplicated_marks),
        target_transform="Mean of two independent manual breath counts over exactly 60 seconds. For each annotator, sort one-based sample numbers and count each marked sample once; preserve every contributing source row.",
        split_policy="Unassigned. All recordings for the same MIMIC-II matched-waveform subject must remain in one partition.",
        grouping_rule="Hash of the source matched-waveform subject ID. Only the hashed group appears in published records.",
        quality_findings=["Single ICU cohort. The minute windows within one recording are dependent.",
                          "125-Hz PLETH is averaged in contiguous 25-sample bins. The signal scale is the published monitor scale. Breath annotations are derived from impedance respiration, which is excluded from input.",
                          "Windows with nonfinite PLETH, constant PLETH or fewer than two marks from either annotator are excluded; count disagreement is otherwise retained."],
        tasks=dict(manual_respiratory_rate=dict(target_name="mean manually annotated respiratory rate",
            unit="breaths/min", type="continuous", instruction="Estimate respiratory rate from this one-minute bedside photoplethysmogram.",
            field_description="pleth_5hz_mean gives 300 consecutive 0.2-second averages of the pulse oximeter PLETH waveform, in original monitor amplitude units and chronological order."))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_dir", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--only", choices=["bidmc","fukuchi"])
    args = parser.parse_args()
    for build in (fukuchi, bidmc):
        if args.only is None or args.only == build.__name__:
            build(args.raw_dir, args.out_dir)
