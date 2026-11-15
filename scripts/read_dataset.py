"""Stream the distributed release with Python's standard library only."""
import gzip,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def iter_records(dataset_id=None,root=ROOT):
    root=pathlib.Path(root)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    selected=[d for d in manifest['datasets'] if dataset_id is None or dataset_id==d.get("dataset_id", "uci_"+str(d.get("uci_id")))]
    if not selected:raise ValueError(f'Unknown dataset_id: {dataset_id}')
    for dataset in selected:
        for shard in dataset['files']:
            with gzip.open(root/shard['path'],'rt',encoding='utf-8') as f:
                for line in f:yield json.loads(line)
