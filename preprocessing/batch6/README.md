# Esports and game regression tasks

Each of the three datasets has one scalar target. Source rows and any helper dictionary entries are recorded in `source_refs`. The English prompt contains only the features available at the stated observation point. The [catalogue](../../docs/catalogue.md#release-250-additions) lists the prepared records, and the [source notices](../../DATA_LICENSES.md#release-250-attribution) credit the original data.

| Task | Label | Suggested evaluation |
|---|---|---|
| Dota 2 professional matches | Seconds remaining after minute ten. The converter joins the minute-ten draft and earned gold to the audited match duration and subtracts 600 seconds. | Use matches starting in 2023–2024 for training, 2025 for validation and 2026 through March 18 for testing. Each match contributes one example. |
| Super Mario Maker | Percentage of additional attempts that clear a course over approximately the next 30 days. The input uses the course style and counters at the first observation. | Keep courses from one maker and courses with identical input together. The eligible population is active courses with a follow-up snapshot 23 to 37 days later. |
| StarCraft II SkillCraft1 | Average actions per minute for a replay, estimated from league, age, weekly play and lifetime play. | Keep identical background profiles together. The cohort contains respondents with reported age and playtime. |

For the two grouped tasks, sort the released group IDs and allocate 70%, 15% and 15% of groups by largest remainder. Partition sizes by example vary with group size. The [CSV](../../splits/batch6/assignments.csv.gz) joins to records on `sample_id`. The records retain `split=unassigned` because these are suggested partitions for the new regression tasks.

## Rebuild and verify

From the repository root, run the following commands with Python 3.9 or later and curl. Use a scratch directory with a few GB of free space. The first command downloads pinned source files, checks their SHA-256 digests, regenerates the records and suggested partitions, and compares them with the release. The second verifies the entire published collection.

```sh
python3 preprocessing/batch6/rebuild_games.py /tmp/regression-games-rebuild
python3 scripts/verify_release.py
```

To regenerate only the assignments and partition counts from the distributed shards, run the following command.

```sh
python3 preprocessing/batch6/split_games.py /tmp/regression-games-splits
```
