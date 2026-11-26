"""Make two archival next-month regression tasks from the October 2026 FRED-MD release."""
import csv
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path

FILE = "2026-10-md.csv"
URL = "https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/research/fred-md/monthly/" + FILE
SHA = "56df9d964f9c846c076a924bad81c3a8ba85f865805c8a564b10c2ffeaaeebfe"
SERIES = {
    "CPIAUCSL": ("US all-items consumer price index, seasonally adjusted", "index (1982-1984 = 100)"),
    "UNRATE": ("US civilian unemployment rate, seasonally adjusted", "percent"),
}
HISTORY = 24


def build(raw, output):
    path = raw / FILE
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA:
        raise ValueError(f"Unexpected vintage or corrupted file: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if next(reader)["sasdate"] != "Transform:":
            raise ValueError("Expected FRED-MD transformation codes")
        records = list(reader)
    months = [datetime.strptime(r["sasdate"], "%m/%d/%Y") for r in records]
    serial = [d.year * 12 + d.month for d in months]
    assert serial == list(range(serial[0], serial[-1] + 1))
    month_keys = [d.strftime("%Y-%m") for d in months]
    history_fields = "The two arrays contain 24 consecutive US monthly observations, oldest to newest. CPIAUCSL is the seasonally adjusted all-items CPI (1982-1984=100). UNRATE is the seasonally adjusted civilian unemployment rate in percent. first_month dates the first observation. Data use the October 2026 vintage."
    tasks = {code.lower(): dict(target_name=name, unit=unit, type="continuous",
             instruction=f"Estimate the {name} for the month following the history.",
             field_description=history_fields) for code, (name, unit) in SERIES.items()}
    values = {code: [float(r[code]) if r[code].strip() else None for r in records] for code in SERIES}
    output.mkdir(parents=True, exist_ok=True)
    missing = 0
    with (output / "fred.jsonl").open("w", encoding="utf-8") as f:
        for i in range(HISTORY, len(records)):
            inputs = {"first_month": month_keys[i-HISTORY], **{c: v[i-HISTORY:i] for c,v in values.items()}}
            for code in SERIES:
                label = values[code][i]
                if label is None:
                    missing += 1
                    continue
                assert math.isfinite(label)
                row = dict(input=inputs, label=label, task_key=code.lower(), group_key=month_keys[i],
                           split="unassigned", time_key=month_keys[i], history_end=month_keys[i-1],
                           source_refs=[dict(file=FILE, row=i+2, column=code, history_start_row=i-HISTORY+2, history_end_row=i+1)])
                f.write(json.dumps(row, allow_nan=False) + "\n")
    meta = dict(name="FRED-MD archival next-month CPI and unemployment", dataset_id="fred_md",
                dataset_family="us_bls_macro_history", version="2026-10", raw_rows_selected=len(records),
                invalid_label_examples=missing, source_url="https://www.stlouisfed.org/research/economists/mccracken/fred-databases",
                license={"terms":"BLS public-domain series, citation requested. Scope limited to CPIAUCSL and UNRATE.",
                         "sources":["https://www.bls.gov/opub/copyright-information.htm"] + ["https://fred.stlouisfed.org/series/"+s for s in SERIES]},
                source_citation="US Bureau of Labor Statistics, CPIAUCSL and UNRATE, via FRED and FRED-MD, Federal Reserve Bank of St. Louis, October 2026 vintage.",
                source_files=[dict(relativepath=FILE, url=URL, sha256=SHA, bytes=path.stat().st_size)], tasks=tasks,
                preparation="Revised-history task. Input ends one calendar month before target. The first 24 months provide history only. Missing input cells remain null. References count the Transform: line as CSV data row 1.",
                split_guidance="Split both tasks by target month together. Account for overlapping windows. This snapshot contains later revisions and does not support real-time forecasting claims.")
    (output/"fred.meta.json").write_text(json.dumps(meta, indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
