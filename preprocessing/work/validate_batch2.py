"""Stream verification against source files, independent target reconstruction."""
import collections,gc,json,math,re
from load_batch2 import *
from batch2_contracts import CONTRACTS
from build_general import clean,dumps,digest,save
from build_batch2 import sha
from prepare_batch2 import MONEY_WORDS,NUMBER_WORDS

def validate_one(i):
    folder=DEST/'datasets'/f'uci_{i}_{CONTRACTS[i]["key"]}'
    meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'));stats=meta['stats']
    d=raw_frame(i);arrays={c:d[c].to_numpy() for c in d}
    lookup={(str(f),int(r)):k for k,(f,r) in enumerate(zip(d._file,d._source_row))}
    excluded=json.loads((folder/'excluded_rows.json').read_text(encoding='utf-8'))
    invalid=json.loads((folder/'invalid_labels.json').read_text(encoding='utf-8'))
    excluded_indices={e['source_index'] for e in excluded}
    invalid_pairs={(e['source_index'],e['target']) for e in invalid}
    targets={t[1]:t[0] for t in CONTRACTS[i]['targets']}
    seen=set();ids=set();pairs=set();ih_groups={};semantic_groups={};links=0;n=0
    for item in invalid:
        v=arrays[item['target']][item['source_index']]
        assert pd.isna(v) or not math.isfinite(float(v)) or v<0
    for line in (folder/'data.jsonl').open(encoding='utf-8'):
        r=json.loads(line,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
        assert r['sample_id'] not in ids;ids.add(r['sample_id'])
        assert r['dataset_id']==f'uci_{i}' and r['split']=='unassigned'
        assert type(r['label']) in (int,float) and math.isfinite(r['label'])
        assert set(r['input'])==set(meta['input_fields'])
        assert not set(meta['excluded_input_columns']).intersection(r['input'])
        assert r['input_hash']==digest(r['input'])
        embedded=r['prompt'].split('\nInput JSON: ',1)[1].split('\nReturn only one numeric prediction',1)[0]
        assert json.loads(embedded)==r['input']
        assert r['duplicate_count']==len(r['source_refs'])
        key=(r['task_id'],r['input_hash'],r['label']);assert key not in pairs;pairs.add(key)
        old=ih_groups.setdefault(r['input_hash'],r['group_id']);assert old==r['group_id']
        col=targets[r['target_name']]
        for ref in r['source_refs']:
            idx=lookup[(ref['file'],ref['row'])];pair=(idx,col)
            assert pair not in seen and idx not in excluded_indices and pair not in invalid_pairs
            seen.add(pair);links+=1
            if i==440:
                values=[float(arrays[c][idx]) for c in RUNS]
                assert r['target_observations']==values
                assert math.isclose(r['label'],sum(values)/4,rel_tol=1e-14,abs_tol=1e-12)
            else:assert float(arrays[col][idx])==r['label'],(i,idx,col)
            sem=None
            if i==925:
                sem=str(arrays['SubjectID'][idx])
                assert r['entity_id']==sem
                for c in THERMAL:
                    stem=c[:-1];cols=[stem+str(k) for k in range(1,5)]
                    if c=='T_LC1':cols[-1]='T_LC14'
                    vals=[float(arrays[x][idx]) for x in cols if pd.notna(arrays[x][idx])]
                    value=r['input'][stem.rstrip('_')+'_mean']
                    assert value is None if not vals else math.isclose(value,sum(vals)/len(vals),rel_tol=1e-14)
            elif i==501:sem=tuple(int(arrays[x][idx]) for x in ['year','month','day','hour'])
            elif i==560:sem=str(arrays['date'][idx])
            elif i==374:sem=str(arrays['date'][idx])[:10]
            elif i==162:sem=(int(arrays['X'][idx]),int(arrays['Y'][idx]))
            if sem is not None:
                old=semantic_groups.setdefault(sem,r['group_id']);assert old==r['group_id']
            if i==555:
                assert arrays['category'][idx]=='housing/rent/apartment'
                assert arrays['price_type'][idx]=='Monthly' and arrays['currency'][idx]=='USD'
                assert arrays['square_feet'][idx]>0
        for v in r['input'].values():
            assert v is None or type(v) in (str,int,float,bool)
            if type(v)==float:assert math.isfinite(v)
        if i==555:
            for c in ['title','body','amenities']:
                s=r['input'][c] or ''
                assert not re.search(r'\d',s) and not MONEY_WORDS.search(s) and not NUMBER_WORDS.search(s)
        if i==551:assert r['dataset_family']=='turkish_power_plant'
        if r['target_type']=='count':assert float(r['label']).is_integer() and r['label']>=0
        n+=1
    for idx in range(len(d)):
        for col in targets.values():
            assert (idx,col) in seen or idx in excluded_indices or (idx,col) in invalid_pairs,(i,idx,col)
    assert n==stats['output_examples'] and links==stats['candidate_task_examples']
    assert len(excluded_indices)==stats['excluded_source_rows']
    result=dict(uci_id=i,status='passed',examples_verified=n,source_label_links_verified=links,source_rows_accounted_for=len(d),excluded_rows=len(excluded_indices),invalid_labels=len(invalid),data_sha256=sha(folder/'data.jsonl'))
    print(json.dumps(result),flush=True);return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--ids',nargs='*',type=int);args=parser.parse_args()
    results=[]
    for i in args.ids or IDS:
        results.append(validate_one(i));gc.collect()
    save(DEST/'reports/batch2_validation.json',{'status':'passed','datasets':results,'training_executed':False})
