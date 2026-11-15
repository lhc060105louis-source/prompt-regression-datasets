# Reproduce batch 3

These scripts only acquire/prepare/validate data; they never train. Use an isolated working directory and install requirements. Raw archives are not distributed. Source manifests freeze commit URLs and SHA256; compare every downloaded raw file before rebuilding. Mutable source documentation may need the recorded snapshot.

Run the source builders from this directory: `python build_text.py --download --build`, `python build_science.py --download --extra-sources --build --validate`, `python build_temporal.py --download`, and `python build_operations.py`. See each script `--help` where applicable. Each builder writes `raw/` and `candidates/` beside itself. RDKit is needed for FreeSolv canonicalization/scaffolds. The public ASAP test password is read from the repository README; third-party reading ZIPs are never requested.

`python standardize.py complex empathy asap2 freesolv gb1 jdft2d cmapss camels_gb auction transcoding` writes generated sources under `publish/`, then `python validate_extension.py` with the same IDs performs full record/source-candidate checks. Per-source builders also run original-row fidelity checks. The checked-in `package_extension.py` documents the original isolated integration; set JEV_BASE_RELEASE to a checkout of v2.1.0 and provide the approval ledger if rerunning integration in another workspace. It is not necessary for loading or validating published data. Use `python scripts/verify_release.py` from repository root to verify the distribution.

No random partition, fitted preprocessing, label imputation or experimental training is performed. Preserve official test sets and honor group/time dependencies when designing a later experiment.
