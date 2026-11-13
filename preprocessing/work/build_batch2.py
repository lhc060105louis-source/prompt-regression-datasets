"""Memory-bounded construction: first batch data is retained byte-for-byte."""
import collections,csv,gc,gzip,hashlib,importlib.metadata,json,math,pathlib,shutil,time
import numpy as np
from load_batch2 import *
from batch2_contracts import CONTRACTS
from prepare_batch2 import prepare
from build_general import clean,dumps,digest,profile,save,Union
from general_specs import TEMPLATE

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()

def build_one(i):
    print(f'START {i}',flush=True)
    spec=CONTRACTS[i];folder=DEST/'datasets'/f'uci_{i}_{spec["key"]}';folder.mkdir(parents=True,exist_ok=True)
    raw=raw_frame(i);rawprofile=profile(raw);save(folder/'quality_profile_raw.json',rawprofile)
    d,features,targets,groupcols,extras,flags,notes,audit,exclusions,forbidden=prepare(i,raw)
    n=len(d);union=Union(n)
    for cols in ([groupcols] if groupcols else [])+extras:
        for ix in d.groupby(cols,dropna=False,sort=False).indices.values():
            if len(ix)>1:
                for k in ix[1:]:union.join(int(ix[0]),int(k))
    # Store only hashes and row indices, not the large repeated prompt strings.
    ihashes=[];seen_input={}
    for idx,values in enumerate(d[features].itertuples(index=False,name=None)):
        h=digest(dict(zip(features,values)));ihashes.append(h)
        if h in seen_input:union.join(idx,seen_input[h])
        else:seen_input[h]=idx
    del seen_input
    banned={x['source_index'] for x in exclusions}
    invalid=[];eligible={};input_label_sets=collections.defaultdict(set)
    for target,name,unit,kind in spec['targets']:
        for idx,value in enumerate(d[target]):
            if idx in banned:continue
            value=clean(value)
            if value is None or not isinstance(value,(int,float)) or value<0:
                invalid.append(dict(source_index=idx,file=str(d.at[idx,'_file']),row=int(d.at[idx,'_source_row']),target=target,reason='missing_nonfinite_or_negative_label'));continue
            key=(name,ihashes[idx],value)
            eligible.setdefault(key,[]).append(idx)
            input_label_sets[(name,ihashes[idx])].add(value)
    conflicted=sum(len(v)>1 for v in input_label_sets.values());del input_label_sets
    duplicates=sum(len(v)-1 for v in eligible.values())
    notes.append(dict(code='identical_input_different_labels',count=conflicted,action='retain_and_group',detail='Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target).'))
    notes.append(dict(code='duplicate_task_examples',count=duplicates,action='collapse_preserve_source_refs',detail='Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count.'))
    source=json.loads((DEST/'raw'/f'uci_{i}'/'source_manifest.json').read_text(encoding='utf-8'))
    api=json.loads((DEST/'raw'/f'uci_{i}'/'uci_metadata.json').read_text(encoding='utf-8'))['data']
    feature_arrays={c:d[c].to_numpy() for c in features}
    files=d['_file'].to_numpy();rownums=d['_source_row'].to_numpy();taskmap={x[1]:x for x in spec['targets']}
    observed_groups=set();nulls=0;flagged=0;task_labels=collections.defaultdict(list);task_lens=collections.defaultdict(list);first={}
    temporary=folder/'data.jsonl.tmp';count=0
    with temporary.open('w',encoding='utf-8',newline='\n') as f:
        for (name,ih,label),indices in eligible.items():
            idx=indices[0];target,_,unit,kind=taskmap[name]
            inp={c:clean(a[idx]) for c,a in feature_arrays.items()}
            tid=f'uci_{i}/{name}';prompt=TEMPLATE.format(task=spec['task'],target_name=name,target_unit=unit,context=spec['context'],input_json=dumps(inp))
            fl=sorted(set().union(*(flags[j] for j in indices)))
            r={'schema_version':'1.0.0','dataset_id':f'uci_{i}','dataset_name':api['name'],'dataset_family':'turkish_power_plant' if i==551 else f'uci_{i}','task_id':tid,'prompt_template_id':tid+'/v1','prompt':prompt,'label':label,'target_name':name,'target_unit':unit,'target_type':kind,'target_transform':'arithmetic_mean_of_four_source_runs' if i==440 else 'none_applied','input':inp,'source_refs':[dict(file=str(files[j]),row=int(rownums[j])) for j in indices],'duplicate_count':len(indices),'quality_flags':fl,'split':'unassigned','group_id':f'uci_{i}/g{union.root(idx):06d}','input_hash':ih,'sample_id':f'uci_{i}/'+digest([tid,ih,label])[:24]}
            if '_time' in d:r['time_key']=str(d.at[idx,'_time'])
            if '_entity' in d:r['entity_id']=str(d.at[idx,'_entity'])
            if i==440:r['target_observations']=[float(raw.at[idx,c]) for c in RUNS]
            f.write(dumps(r)+'\n');count+=1
            nulls+=any(v is None for v in inp.values());flagged+=bool(fl);observed_groups.add(r['group_id']);task_labels[tid].append(label);task_lens[tid].append(len(prompt));first.setdefault(tid,r)
            if count%50000==0:print(f'PROGRESS {i} {count}',flush=True)
    temporary.replace(folder/'data.jsonl')
    candidate_count=sum(len(v) for v in eligible.values())
    stats={'uci_id':i,'name':api['name'],'batch':2,'raw_rows_selected':n,'raw_exact_duplicate_rows':rawprofile['exact_duplicate_rows'],'candidate_task_examples':candidate_count,'invalid_label_examples':len(invalid),'excluded_source_rows':len(banned),'output_examples':count,'collapsed_duplicate_examples':duplicates,'task_count':len(task_labels),'split_groups':len(observed_groups),'input_field_count':len(features),'examples_with_null_input':nulls,'flagged_examples':flagged,'identical_input_different_label_groups':conflicted,'source_url':source['source_url'],'path':str((folder/'data.jsonl').relative_to(DEST)).replace('\\','/')}
    taskstats={tid:{'examples':len(y),'label_quantiles':pd.Series(y).quantile([0,.01,.5,.99,1]).to_dict(),'zero_labels':sum(v==0 for v in y),'prompt_characters':{'min':min(task_lens[tid]),'median':float(np.median(task_lens[tid])),'max':max(task_lens[tid])}} for tid,y in task_labels.items()}
    license_={'name':'CC0 1.0 Universal (PhysioNet original release)' if i==925 else 'CC BY 4.0 as recorded on UCI','source_url':'https://physionet.org/content/face-oral-temp-data/1.0.0/' if i==925 else source['source_url']}
    meta={'version':'2.0.0','record_schema_version':'1.0.0','stats':stats,'contract':spec,'input_fields':features,'excluded_input_columns':forbidden,'grouping_columns':groupcols,'extra_grouping_columns':extras,'grouping_rule':'Known semantic groups unioned with identical prepared inputs; group_id does not prove independence.','missing_policy':'No target imputation; invalid/missing targets excluded. Missing features remain null. Explicit invalid-ratio repairs audited.','split_policy':'unassigned; use contract split guidance; dataset-family holdouts decided before training','license':license_,'source_archive_sha256':source['archive_sha256'],'dataset_doi':api.get('dataset_doi'),'creators':api.get('creators'),'citation_paper':api.get('intro_paper'),'task_statistics':taskstats,'quality_findings':notes,'source_values_policy':'Original numeric labels except documented arithmetic mean for SGEMM; no learned scaling, clipping or target log transform.'}
    save(folder/'metadata.json',meta);save(folder/'quality_profile_prepared_features.json',profile(d[features+targets]));save(folder/'changes.json',audit);save(folder/'excluded_rows.json',exclusions);save(folder/'invalid_labels.json',invalid)
    save(folder/'prompt_templates.json',dict(version='1.0.0',language='English',template=TEMPLATE,task=spec['task'],context=spec['context'],targets=[dict(column=t[0],name=t[1],unit=t[2],type=t[3]) for t in spec['targets']]))
    with (folder/'preview.jsonl').open('w',encoding='utf-8') as f:
        for r in first.values():f.write(dumps(r)+'\n')
    print('DONE '+dumps(stats),flush=True)
    return stats

def snapshot():
    hist=DEST/'history/batch1';hist.mkdir(parents=True,exist_ok=True)
    for rel in ['manifest.json','checksums.json','reports/质量检查报告.md','reports/validation.json','README.md']:
        dst=hist/pathlib.Path(rel).name
        if not dst.exists():shutil.copy2(DEST/rel,dst)
    return json.loads((hist/'manifest.json').read_text(encoding='utf-8'))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--ids',nargs='*',type=int);args=parser.parse_args()
    snapshot();stats=[]
    for i in args.ids or IDS:
        stats.append(build_one(i));gc.collect()
    save(DEST/'reports/batch2_build_run.json',stats)
