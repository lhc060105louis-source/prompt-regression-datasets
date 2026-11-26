"""Export reproducible split suggestions for batch 5. Shards remain unchanged.

Example: python preprocessing/batch5/suggest_splits.py --root . -o batch5-splits.csv
CSV goes to stdout unless -o is used. Counts are printed to stderr.
"""
import argparse
import csv
import gzip
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path


PARTITIONS = ('train', 'validation', 'test')


def records(root, dataset):
    for shard in dataset['files']:
        with gzip.open(root / shard['path'], 'rt', encoding='utf-8') as stream:
            for line in stream:
                yield json.loads(line)


def grouped_assignments(group_ids, percentages):
    """Allocate whole groups by largest remainder, breaking ties in train/dev/test order."""
    ordered = sorted(group_ids)
    sizes = [len(ordered) * percent // 100 for percent in percentages]
    residues = [len(ordered) * percent % 100 for percent in percentages]
    for i in sorted(range(3), key=lambda i: -residues[i])[:len(ordered) - sum(sizes)]:
        sizes[i] += 1
    lookup = {}
    offset = 0
    for split, size in zip(PARTITIONS, sizes):
        lookup.update(dict.fromkeys(ordered[offset:offset + size], split))
        offset += size
    return lookup


def export_dataset(root, dataset, writer):
    ds = dataset['dataset_id']
    group_assignments = {}
    if ds == 'uci_607':
        loads = sorted({r['input']['load_current_a'] for r in records(root, dataset)})
        load_splits = {load: {1: 'validation', 4: 'test'}.get(index % 7, 'train') for index, load in enumerate(loads)}
    elif ds not in {'uci_396', 'fdm_aktepe'}:
        groups = {r['group_id'] for r in records(root, dataset)}
        fractions = (80, 10, 10) if ds in {'openipf', 'lancaster_sensorimotor'} else (70, 15, 15)
        group_assignments = grouped_assignments(groups, fractions)

    counts = Counter()
    seen_ids = set()
    assigned_groups = {}
    for record in records(root, dataset):
        if record['dataset_id'] != ds or record['split'] != 'unassigned':
            raise ValueError(f'Unexpected dataset or source split: {record["sample_id"]}')
        gid = record['group_id']
        if ds == 'uci_396':
            week = record['target_week_index']
            if not 8 <= week <= 51:
                raise ValueError(f'Unexpected target week {week}')
            split = 'train' if week <= 35 else 'validation' if week <= 43 else 'test'
        elif ds == 'fdm_aktepe':
            material = record['input']['material']
            split = 'test' if material in {'rpet', 'petg'} else 'validation' if material == 'tpu' else 'train'
        elif ds == 'uci_607':
            split = load_splits[record['input']['load_current_a']]
        else:
            split = group_assignments[gid]
        if ds != 'uci_396' and assigned_groups.setdefault(gid, split) != split:
            raise ValueError(f'Split crosses a group in {ds}')
        sample_id = record['sample_id']
        if sample_id in seen_ids:
            raise ValueError(f'Duplicate sample_id: {sample_id}')
        seen_ids.add(sample_id)
        writer.writerow((sample_id, ds, split))
        counts[split] += 1
    if sum(counts.values()) != dataset['output_examples']:
        raise ValueError(f'Split total disagrees with manifest for {ds}')
    return {key: counts[key] for key in PARTITIONS}


def export(root, stream):
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    datasets = [ds for ds in manifest['datasets'] if ds.get('batch') == 5]
    if not datasets:
        raise ValueError('No batch 5 datasets found in the release manifest.')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(('sample_id', 'dataset_id', 'split'))
    summary = {ds['dataset_id']: export_dataset(root, ds, writer) for ds in datasets}
    print(json.dumps(summary, indent=2), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('-o', '--output', type=Path, help='CSV destination (default: stdout)')
    args = parser.parse_args()
    if args.output is None:
        export(args.root, sys.stdout)
        return
    # Publish the file only after the entire manifest has been successfully checked.
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=args.output.parent,
                                         prefix='.batch5-splits-', delete=False) as stream:
            tmp = Path(stream.name)
            export(args.root, stream)
        os.replace(tmp, args.output)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
