# Prompt Regression Datasets

Multi-domain regression data represented as **English prompts paired with numeric labels**.

**Release 2.1.0 · 29 sources · 33 regression tasks · 1,067,479 examples**

Domains include materials, energy, transport, housing, biology, environmental monitoring, computing, and social data. This is a data preparation release for general regression research. It does **not** demonstrate model generalization: no model has been trained or evaluated, and all splits remain `unassigned`.

## Load the data

The prepared data is included in this repository as ordinary gzip-compressed JSONL files. No Git LFS or external dataset download is required to use it.

```bash
git clone https://github.com/lhc060105louis-source/prompt-regression-datasets.git
cd prompt-regression-datasets
```

Python's standard library is sufficient:

```python
from scripts.read_dataset import iter_records

for example in iter_records(dataset_id="uci_440"):
    prompt = example["prompt"]
    label = example["label"]  # a JSON number, not a string
    print(prompt, label)
    break

# Omit dataset_id to stream all 29 datasets in manifest order.
```

Each dataset directory has `part-00001.jsonl.gz` (and further parts for larger datasets), metadata, a directly readable `preview.jsonl`, prompt templates, and quality/audit files. Each data shard contains at most 100,000 records. Decompressing and concatenating a dataset's shards reproduces its original prepared JSONL byte for byte.

The [manifest](manifest.json) lists every shard, count, and checksum. Browse the [dataset catalogue](docs/catalogue.md). Read [actual examples](docs/examples.md), [the Chinese quality report](reports/quality_report_zh.md), and [source attributions and data licenses](DATA_LICENSES.md).

## Record format

| Field | Meaning |
|---|---|
| `prompt` | Task instructions, target unit, field definitions, and input JSON |
| `label` | One finite numeric regression target; never embedded as the answer in the prompt |
| `input` | Typed feature object matching the JSON inside the prompt |
| `task_id`, `dataset_id`, `dataset_family` | Task and source identity, including known related-source families |
| `target_name`, `target_unit`, `target_transform` | Target definition and any documented transformation |
| `source_refs`, `duplicate_count` | Original file/row lineage and multiplicity of merged examples |
| `group_id`, optional `entity_id`, `time_key` | Known dependencies for later group/time-aware splitting |
| `quality_flags` | Preserved anomalies or documented repairs; absence is not proof of clean data |
| `sample_id`, `input_hash` | Content-derived identifiers |
| `split` | `unassigned` for this release |

Some SGEMM records additionally contain `target_observations`, the four original runtime measurements. These are outcomes and must **not** be model inputs.

Prepared non-integral numbers use at most **12 significant digits**. Integers, missing values (`null`), strings, and units are preserved. This storage cap is not a claim of measurement precision. Precision changes are bounded by approximately 5×10⁻¹² relative error. Four additional superconductivity examples became exact duplicates and were merged with all source references retained.

## Quality and intended use

- The source labels were checked before precision normalization; the current release was checked against that validated version under the declared rounding rule. Packaging checks establish byte equality after decompression.
- Missing targets are excluded, never imputed. Missing features remain `null`. Target-related input columns are excluded where identified.
- Rental text removes monetary clauses, digits, and spelled-out numbers independently of the target label. This sacrifices some useful prose; source location inconsistencies and possible shared-room listings remain limitations.
- GPU targets are the arithmetic mean of four measured runs on fixed hardware. This release does not invent uncertainty labels or establish cross-hardware generalization.
- Infrared data uses the original FLIR/ICI release: 2,029 device records from 1,026 people. Both oral-thermometer targets are excluded from inputs; subject groups span devices.
- Protein IDs are unavailable, so descriptor grouping cannot establish unseen-protein evaluation. News share counts have varying exposure horizons. Several weather/energy tasks are contemporaneous estimation tasks rather than strict future forecasts.
- Gas-turbine emissions and CCPP share the `turkish_power_plant` family. Keep related families together when holding out unseen datasets.

Before training, choose whole-task/family holdouts, appropriate temporal/subject splits, and task sampling weights. Do not randomly split the concatenated corpus or let large datasets dominate by accident. Fit any learned preprocessing only on the training partition. Record training/validation metrics, configurations, and checkpoints from the start of an experiment. No external experiment logging is enabled here.

## Contents and verification

```text
datasets/       compressed prepared records, metadata, previews, audit files
sources/        source manifests and UCI metadata, including attribution
reports/        source/precision/packaging quality and validation reports
docs/           complete example prompts
scripts/        standard-library reader and release verifier
preprocessing/  original preprocessing pipeline, dependency versions, candidate list
manifest.json   release counts, data shard locations and SHA-256 hashes
checksums.json  checksums for distributed files
```

```bash
python scripts/verify_release.py
```

Large audit JSON files are gzip-compressed; numeric precision audits contain old/new sample IDs and changed field values. Raw source archives and local historical copies are not duplicated in this Git repository. Download URLs and archive hashes are retained under `sources/`. Historical references in the detailed quality report describe the original build workspace, which can be regenerated below.

## Rebuild from original sources

Using a separate Python environment is recommended. The recorded build used Python 3.13. Rebuilding downloads the official UCI/PhysioNet sources and needs several GB of local disk space; it performs no training.

```bash
python -m pip install -r preprocessing/requirements.txt
python preprocessing/rebuild.py
```

The original working layout is preserved under `preprocessing/work/`. The rebuild writes to the ignored `preprocessing/构造general数据集/` directory, including original downloads, the combined JSONL archive, intermediate reports, and historical copies. It does not overwrite the distributed `datasets/` files. The entry point refuses to overwrite an existing build directory.

## Attribution

Please cite the original dataset authors and source DOIs listed in [DATA_LICENSES.md](DATA_LICENSES.md), as well as the version/commit of this collection when used. Source data is attributed to its original creators. The repository provides preprocessing and repackaging; it is not an official UCI or PhysioNet release.

中文说明：本仓库包含当前 v2.1.0 的完整处理后数据，共 29 个来源、33 个任务、1,067,479 条样本。数据已按来源分片压缩，格式为 prompt + 数值标签。尚未划分训练/验证集，也未训练模型。详见[质量报告](reports/quality_report_zh.md)。
