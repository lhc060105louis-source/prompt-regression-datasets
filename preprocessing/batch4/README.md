# Reproduce the six-source expansion

The checked-in files under `datasets/` can be read directly using `scripts/read_dataset.py`. This directory reproduces the data files from the source snapshots recorded in the six source manifests. The builders use Python and the SDSS downloader also uses curl. See each source manifest for attribution and rights.

From the repository root, choose a scratch directory with several GB of free space. The following example fetches the archives and fixed economic vintage. The source server may update the FAOSTAT archive at the same URL. Compare its SHA-256 with the published manifest and use the recorded vintage when reproducing the release.

```sh
WORK=/tmp/jev-batch4-rebuild
mkdir -p "$WORK/candidates"
python3 - "$WORK" <<'PY'
import hashlib, json, pathlib, subprocess, sys
work = pathlib.Path(sys.argv[1])
for dataset_id in ("uci_1186", "uci_310", "uci_487", "faostat_qcl", "fred_md"):
    meta = json.loads(pathlib.Path("sources", dataset_id, "source_manifest.json").read_text())
    for item in meta["files"]:
        path = work / item["relativepath"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            subprocess.run(["curl", "--fail", "--location", "--retry", "3",
                            "--output", str(path), item["url"]], check=True)
        with path.open("rb") as data:
            digest = hashlib.sha256()
            for block in iter(lambda: data.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != item["sha256"]:
            raise ValueError(f"Source snapshot differs from the published release: {path}")
PY
python3 preprocessing/batch4/agri.py "$WORK" "$WORK/candidates"
python3 preprocessing/batch4/sensor.py "$WORK" "$WORK/candidates"
python3 preprocessing/batch4/fred.py "$WORK" "$WORK/candidates"
python3 preprocessing/batch4/sdss.py "$WORK" "$WORK/candidates"
python3 preprocessing/batch4/package.py "$WORK" paddy faostat uji gas fred sdss
```

The SDSS converter requests the recorded plate ranges from DR17 SkyServer. For byte-level replication, compare each resulting query snapshot to its entry in the SDSS source manifest. A successful build writes compressed records, templates, metadata, and per-source validation reports under `$WORK/publish/`. Compare the concatenated uncompressed shard hashes to `manifest.json`. To verify the downloaded GitHub distribution, run `python3 scripts/verify_release.py` from its root.

The packager reuses the batch 3 precision, prompt, grouping, deduplication and validation code. It creates SQLite work files in the scratch directory. Use a different scratch directory for concurrent builds of the same source.
