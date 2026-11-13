"""Versioned decimal precision for prepared data; raw files are never modified."""
import hashlib,json,math,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2 if pathlib.Path(__file__).parent.name=='scripts' else 1]
DEST=ROOT/'构造general数据集'
POLICY={'id':'significant_digits_12_v1','significant_digits':12,'rule':'Non-integral finite floats rounded to at most 12 significant decimal digits; integers, null and strings unchanged; no fixed decimal-place rounding or clipping.','relative_error_bound':5.01e-12,'scope':['input numeric values','label','target_observations'],'raw_files_changed':False}
def normalize(v):
    if type(v) is float:
        assert math.isfinite(v)
        if v.is_integer():return int(v)
        v=float(format(v,'.12g'))
        return int(v) if v.is_integer() else v
    if isinstance(v,dict):return {k:normalize(x) for k,x in v.items()}
    if isinstance(v,list):return [normalize(x) for x in v]
    return v
def dumps(v):return json.dumps(v,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def digest(v):return hashlib.sha256(dumps(v).encode()).hexdigest()
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
def convert(r):
    out=dict(r);out['input']=normalize(r['input']);out['label']=normalize(r['label'])
    if 'target_observations' in r:out['target_observations']=normalize(r['target_observations'])
    head,rest=r['prompt'].split('\nInput JSON: ',1);_,tail=rest.split('\nReturn only one numeric prediction',1)
    out['prompt']=head+'\nInput JSON: '+dumps(out['input'])+'\nReturn only one numeric prediction'+tail
    out['input_hash']=digest(out['input']);out['sample_id']=r['dataset_id']+'/'+digest([r['task_id'],out['input_hash'],out['label']])[:24]
    return out
def numeric_changes(old,new):
    changes=[]
    for k,v in old['input'].items():
        if v!=new['input'][k]:changes.append(('input.'+k,v,new['input'][k]))
    if old['label']!=new['label']:changes.append(('label',old['label'],new['label']))
    for k,(a,b) in enumerate(zip(old.get('target_observations',[]),new.get('target_observations',[]))):
        if a!=b:changes.append((f'target_observations.{k}',a,b))
    return changes

if __name__=='__main__':
    import collections
    m=json.loads((DEST/'manifest.json').read_text(encoding='utf-8'));results=[]
    for ds in m['datasets']:
        changed=collections.Counter();rows=0;absmax=0;relmax=0;examples=[];inputs={};keys=set();collisions=0;group_collisions=0
        for line in (DEST/ds['path']).open(encoding='utf-8'):
            r=json.loads(line);n=convert(r);c=numeric_changes(r,n)
            if c:rows+=1
            for field,a,b in c:
                changed[field]+=1;absmax=max(absmax,abs(a-b));relmax=max(relmax,abs(a-b)/abs(a))
                if len(examples)<5:examples.append([field,a,b])
            h=n['input_hash'];old=inputs.setdefault(h,r['group_id'])
            group_collisions+=old!=r['group_id']
            key=(n['task_id'],h,n['label']);collisions+=key in keys;keys.add(key)
        s=dict(uci_id=ds['uci_id'],path=ds['path'],changed_records=rows,changed_fields=dict(changed),max_absolute_change=absmax,max_relative_change=relmax,new_duplicate_records=collisions,new_cross_group_equal_inputs=group_collisions,examples=examples)
        assert relmax<=POLICY['relative_error_bound'];results.append(s)
        print(dumps({k:v for k,v in s.items() if k not in ['changed_fields','examples','path']}),flush=True)
    save(ROOT/'work/precision_scan.json',{'policy':POLICY,'datasets':results})
