"""Verify all packaged checksums and uncompressed dataset hashes/counts."""
import gzip,hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()
def main():
    manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    checks=json.loads((ROOT/'checksums.json').read_text(encoding='utf-8'))
    for rel,expected in checks.items():assert sha(ROOT/rel)==expected,rel
    total=0
    for dataset in manifest['datasets']:
        h=hashlib.sha256();count=0
        for shard in dataset['files']:
            assert sha(ROOT/shard['path'])==shard['sha256'];n=0
            with gzip.open(ROOT/shard['path'],'rb') as f:
                for line in f:h.update(line);n+=1
            assert n==shard['records'];count+=n
        assert count==dataset['output_examples']
        assert h.hexdigest()==dataset['uncompressed_sha256']
        total+=count
    assert total==manifest['total_examples']
    print(f'Passed: {len(manifest["datasets"])} sources, {manifest["task_count"]} tasks, {total:,} records.')
if __name__=='__main__':main()
