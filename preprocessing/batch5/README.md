# Seven-source regression expansion

The prepared examples are in the [catalogue](../../docs/catalogue.md#release-240-additions). Each dataset directory includes a preview, prompt templates, source-row references and validation results.

## Suggested evaluation splits

The [assignment file](../../splits/batch5/assignments.csv.gz) contains one row per new example with `sample_id`, `dataset_id` and `split`. Join on `sample_id` to use these partitions. The [summary](../../splits/batch5/summary.json) gives row counts by dataset and partition. Source records keep `split=unassigned` because these are research partitions devised for this collection.

| Source | Evaluation question | Assignment |
|---|---|---|
| Lancaster | Can the model estimate sensory ratings for other words? | Keep all three dimensions of each word together. Allocate 80%, 10% and 10% of word groups to train, validation and test. Closely related word forms can still occur in different partitions. |
| OpenIPF | How well do pre-lift attributes predict results for unfamiliar athletes? | Allocate 80%, 10% and 10% of released groups. Groups link repeated source athlete identifiers and records with identical inputs. |
| UCI weekly sales | How well can the model forecast a later week for an observed product? | Across all products, use target weeks 8–35 for training, 36–43 for validation and 44–51 for testing. For each rolling one-week forecast, the preceding eight observed weeks are available at prediction time. |
| FDM | How well do process settings transfer to other polymers? | Use TPU for validation, PETG and recycled PET for testing, and the other material families for training. |
| Synchronous machine | How well does the model transfer to held-out loads on the same machine? | Sort load-current levels numerically. From a zero-based index, use remainder 1 modulo 7 for validation, remainder 4 for testing and the remaining levels for training. |
| Running biomechanics | How well do trial estimates transfer to other runners? | Keep all speeds for a runner together. Allocate 70%, 15% and 15% of groups. |
| BIDMC | How well do pulse-wave estimates transfer to other participants? | Keep all windows from a participant together. Allocate 70%, 15% and 15% of groups. |

Group allocations sort the released hashed group identifiers and apportion whole groups by largest remainder. The resulting record shares depend on group sizes. The exporter checks sample ID uniqueness, record totals and group separation for each applicable task. Recreate the CSV from the repository root with Python's standard library.

```sh
python3 preprocessing/batch5/suggest_splits.py --root . -o /tmp/batch5-splits.csv
```

## Rebuild from source snapshots

The source manifests record the original URLs, byte sizes, SHA-256 hashes, attribution and data rights. The OpenIPF bulk URL is updated weekly. For an exact rebuild supply the recorded 2026-11-21 ZIP at `WORK/openipf-2026-11-21.zip` if the live file has changed. The archive identifies upstream database revision `fb43e52f`. The published shards can be verified independently of upstream availability.

The build requires Python, curl and openpyxl to read the print experiment workbook. Use a scratch directory with several GB of free space. Source downloads, intermediate candidate files, SQLite databases and rebuilt shards are written under that directory.

```sh
python3 -m pip install openpyxl
python3 preprocessing/batch5/rebuild.py /tmp/batch5-rebuild
python3 scripts/verify_release.py
```

The build compares regenerated records against the release's uncompressed SHA-256 hashes. To inspect filters, input fields, label definitions or grouping rules, see each dataset's `metadata.json` and the corresponding converter in this directory.
