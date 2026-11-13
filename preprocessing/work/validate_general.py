"""Full generated-data validation against original scalar targets; no training."""
import collections, gzip, hashlib, json, math, pathlib, shutil
from load_general import ROOT, DEST, frame
from general_specs import SPECS

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def validate():
    manifest=json.loads((DEST/'manifest.json').read_text(encoding='utf-8'))
    checksums=json.loads((DEST/'checksums.json').read_text(encoding='utf-8'))
    assert manifest['dataset_count']==18 and manifest['task_count']==21
    for rel,expected in checksums.items():assert sha(DEST/rel)==expected,('Checksum mismatch',rel)
    ids=set();groups={};rows_checked=0;source_labels_checked=0;nulls=0;tasks=collections.Counter();dataset_results=[]
    def forbid_constant(x): raise ValueError(f'Invalid JSON number {x}')
    with gzip.open(DEST/'combined/all.jsonl.gz','rt',encoding='utf-8') as combined:
        for dataset in manifest['datasets']:
            i=dataset['uci_id'];spec=SPECS[i];d=frame(i)
            source_rows={}
            for _,row in d.iterrows():
                file=str(row.get('_file',spec['source_file']))
                source_rows[(file,int(row['_source_row']))]=row
            folder=(DEST/dataset['path']).parent
            meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
            forbidden=set(meta['excluded_input_columns'])
            seen_pairs=set();source_refs_seen=set();group_by_source={};known_semantic_groups={};n=0
            task_target={t[1]:t[0] for t in spec['targets']}
            with (DEST/dataset['path']).open(encoding='utf-8') as f:
                for line in f:
                    assert combined.readline()==line,'Combined file differs from per-dataset order/content'
                    r=json.loads(line,parse_constant=forbid_constant)
                    assert r['sample_id'] not in ids,'Duplicate sample_id';ids.add(r['sample_id'])
                    assert r['dataset_id']==f'uci_{i}'
                    assert type(r['label']) in (int,float) and math.isfinite(r['label'])
                    assert isinstance(r['prompt'],str) and r['prompt'].strip()
                    assert r['split']=='unassigned'
                    assert not forbidden.intersection(r['input']),('Leakage column',i)
                    assert set(r['input'])==set(meta['input_fields'])
                    embedded=r['prompt'].split('\nInput JSON: ',1)[1].split('\nReturn only one numeric prediction',1)[0]
                    assert json.loads(embedded)==r['input']
                    assert r['duplicate_count']==len(r['source_refs'])
                    pair=(r['task_id'],r['input_hash'],r['label'])
                    assert pair not in seen_pairs;seen_pairs.add(pair)
                    gkey=(i,r['input_hash'])
                    if gkey in groups:assert groups[gkey]==r['group_id']
                    else:groups[gkey]=r['group_id']
                    if r['target_type']=='count':assert r['label']>=0 and float(r['label']).is_integer()
                    if i==186:assert 0<=r['label']<=10
                    if i==320:assert 0<=r['label']<=20
                    col=task_target[r['target_name']]
                    for ref in r['source_refs']:
                        key=(ref['file'],ref['row']);raw=source_rows[key]
                        assert float(raw[col])==r['label'],('Label differs from raw',i,key,col)
                        source_refs_seen.add(key);source_labels_checked+=1
                        if key in group_by_source:assert group_by_source[key]==r['group_id']
                        else:group_by_source[key]=r['group_id']
                        if i==189:semantic=('patient',int(raw['subject#']))
                        elif i==320:semantic=tuple(str(raw[x]) for x in spec['group'])
                        elif i in [275,492]:semantic=tuple(str(raw[x]) for x in spec['group'])
                        else:semantic=None
                        if semantic is not None:
                            if semantic in known_semantic_groups:assert known_semantic_groups[semantic]==r['group_id']
                            else:known_semantic_groups[semantic]=r['group_id']
                    for v in r['input'].values():
                        assert v is None or type(v) in (int,float,str,bool)
                        if isinstance(v,float):assert math.isfinite(v)
                    n+=1;rows_checked+=1;tasks[r['task_id']]+=1
                    nulls+=any(v is None for v in r['input'].values())
            assert n==dataset['output_examples']
            assert len(source_refs_seen)==dataset['raw_rows_selected'],'Missing source-row lineage'
            dataset_results.append({'uci_id':i,'examples_verified':n,'source_rows_accounted_for':len(source_refs_seen),'status':'passed'})
        assert combined.readline()=='','Unexpected extra combined records'
    assert rows_checked==manifest['total_examples']
    assert len(tasks)==21
    result={'status':'passed','checks':['18 datasets / 21 tasks','all stored file checksums','full JSON parsing and finite numeric labels','full label equality against every source reference','complete source-row lineage','unique sample IDs and task/input/label tuples','input excludes all target and prohibited columns','prompt embedded JSON equals structured input','known patient / student / time groups stay together','identical inputs share group IDs','multi-target source rows share group IDs','combined gzip equals per-dataset files record by record','all splits explicitly unassigned'], 'examples_verified':rows_checked,'source_label_links_verified':source_labels_checked,'examples_with_null_features':nulls,'tasks':dict(tasks),'datasets':dataset_results,'training_executed':False}
    (DEST/'reports/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'outputs/general_dataset_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for name in ['download_general.py','load_general.py','general_specs.py','build_general.py','validate_general.py']:
        p=ROOT/'work'/name
        if p.exists():shutil.copy2(p,DEST/'scripts'/name)
    checksums={str(p.relative_to(DEST)).replace('\\','/'):sha(p) for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='checksums.json'}
    (DEST/'checksums.json').write_text(json.dumps(checksums,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['datasets','tasks']},ensure_ascii=False,indent=2))

if __name__=='__main__':validate()
