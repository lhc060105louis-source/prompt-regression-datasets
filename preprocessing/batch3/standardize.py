"""Deterministic additive release preparation. Inputs are audited source candidates."""
import collections, gzip, hashlib, json, math, pathlib, sqlite3, statistics, sys
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/'publish'
def dump(x):return json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def digest(x):return hashlib.sha256(dump(x).encode()).hexdigest()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
def normalize(v):
 if isinstance(v,float):
  assert math.isfinite(v)
  n=float(format(v,'.12g'))
  assert v==0 or abs((n-v)/v)<=5.01e-12
  return int(n) if n.is_integer() else n
 if isinstance(v,dict):return {str(k):normalize(x) for k,x in v.items()}
 if isinstance(v,list):return [normalize(x) for x in v]
 assert v is None or isinstance(v,(str,int,bool)),type(v)
 return v
class Groups:
 def __init__(self):self.p={}
 def find(self,x):
  self.p.setdefault(x,x)
  if self.p[x]!=x:self.p[x]=self.find(self.p[x])
  return self.p[x]
 def union(self,a,b):
  a,b=self.find(a),self.find(b)
  if a!=b:self.p[max(a,b)]=min(a,b)
def has_null(v):
 return v is None or isinstance(v,dict) and any(has_null(x) for x in v.values()) or isinstance(v,list) and any(has_null(x) for x in v)
def build(slug):
 src=ROOT/'candidates'/f'{slug}.jsonl';meta=json.loads(src.with_suffix('.meta.json').read_text(encoding='utf-8'))
 ds=meta['dataset_id'];folder=OUT/'datasets'/f'{ds}_{slug}'
 for item in meta['source_files']:
  rel=item.get('relativepath',item.get('path'))
  matches=[p for p in [ROOT/rel,ROOT/'raw'/rel,ROOT/'raw'/slug/rel] if p.is_file()]
  assert len(matches)==1,(slug,rel,matches)
  item['relativepath']=matches[0].relative_to(ROOT).as_posix();item.pop('path',None)
 for definition in meta['tasks'].values():
  if isinstance(definition['field_description'],dict):definition['field_description']='; '.join(f'{k}: {v}' for k,v in definition['field_description'].items())
 folder.mkdir(parents=True,exist_ok=True)
 # Rebuild only this new, approved source's generated shards, never baseline files.
 for p in folder.glob('part-*.jsonl.gz'):p.unlink()
 dbpath=ROOT/f'{slug}.sqlite'
 if dbpath.exists():dbpath.unlink()
 con=sqlite3.connect(dbpath);con.execute('CREATE TABLE r (id TEXT PRIMARY KEY,t TEXT,ih TEXT,y TEXT,sp TEXT,g TEXT,data TEXT)')
 con.execute('PRAGMA synchronous=OFF');con.execute('PRAGMA journal_mode=OFF')
 groups=Groups();inputgroups={};n=duplicates=0
 with src.open(encoding='utf-8') as f:
  for line in f:
   c=json.loads(line);n+=1
   if n%20000==0:print(f'{slug}: ingest {n}',flush=True)
   assert type(c['label']) in (int,float) and math.isfinite(c['label'])
   assert isinstance(c['input'],dict) and c['source_refs']
   c=normalize(c);ih=digest(c['input']);task=c['task_key'];sp=c.get('split','unassigned');g=str(c['group_key'])
   assert task in meta['tasks'];assert sp in ['train','validation','test','unassigned']
   groups.find(g)
   if ih in inputgroups:groups.union(g,inputgroups[ih])
   else:inputgroups[ih]=g
   key=digest([task,ih,c['label'],sp]);existing=con.execute('SELECT data,g FROM r WHERE id=?',(key,)).fetchone()
   if existing:
    prior=json.loads(existing[0]);prior['source_refs'].extend(c['source_refs']);prior['quality_flags']=sorted(set(prior.get('quality_flags',[])+c.get('quality_flags',[])))
    prior['duplicate_count']=prior.get('duplicate_count',1)+1;groups.union(g,existing[1]);con.execute('UPDATE r SET data=? WHERE id=?',(dump(prior),key));duplicates+=1
   else:con.execute('INSERT INTO r VALUES(?,?,?,?,?,?,?)',(key,task,ih,dump(c['label']),sp,g,dump(c)))
 con.commit();con.execute('CREATE INDEX ri ON r(ih)')
 conflict={x[0] for x in con.execute('SELECT ih FROM r GROUP BY ih HAVING count(DISTINCT sp)>1')}
 inconsistent={(x[0],x[1]) for x in con.execute('SELECT t,ih FROM r GROUP BY t,ih HAVING count(DISTINCT y)>1')}
 group_splits=collections.defaultdict(set)
 for g,sp in con.execute('SELECT DISTINCT g,sp FROM r'):group_splits[groups.find(g)].add(sp)
 crossgroups={g for g,ss in group_splits.items() if len(ss-{'unassigned'})>1}
 h=hashlib.sha256();files=[];raw=None;z=None;partbytes=0;count=flagged=nulls=0;taskstats={};splits=collections.Counter();flagstats=collections.Counter();preview=[]
 for key,task,ih,y,sp,g,data in con.execute('SELECT * FROM r ORDER BY rowid'):
  c=json.loads(data);definition=meta['tasks'][task];tid=f'{ds}/{task}';gid=f'{ds}/g'+digest(groups.find(g))[:24]
  flags=list(c.get('quality_flags',[]))
  if ih in conflict:flags.append('identical_input_cross_official_splits')
  if (task,ih) in inconsistent:flags.append('identical_input_multiple_labels')
  if groups.find(g) in crossgroups:flags.append('group_cross_official_splits')
  r={'schema_version':'1.0.0','dataset_id':ds,'dataset_name':meta['name'],'dataset_family':meta.get('dataset_family',ds),'task_id':tid,'prompt_template_id':tid+'/v1','label':c['label'],'target_name':definition['target_name'],'unit':definition['unit'],'type':definition.get('type','continuous'),'target_transform':meta.get('target_transform','none_applied'),'input':c['input'],'source_refs':c['source_refs'],'duplicate_count':c.get('duplicate_count',1),'quality_flags':sorted(set(flags)),'split':sp,'group_id':gid,'input_hash':ih,'sample_id':ds+'/'+digest([tid,ih,c['label'],sp])[:24]}
  r['prompt']=f"Task: {definition['instruction']}\nTarget: {definition['target_name']}\nTarget unit: {definition['unit']}\nInput format: a JSON object. null means missing.\nField definitions and context: {definition['field_description']}\nInput JSON: {dump(r['input'])}\nReturn only one numeric prediction for the target."
  for k,v in c.items():
   if k not in {'input','label','task_key','target_name','unit','target_type','group_key','source_refs','split','quality_flags','duplicate_count'}:r[k]=v
  line=(dump(r)+'\n').encode()
  if z is None or partbytes+len(line)>32*1024*1024 or files[-1]['records']>=20000:
   if z:z.close();raw.close()
   p=folder/f'part-{len(files)+1:05d}.jsonl.gz';raw=p.open('wb');z=gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=6);partbytes=0
   files.append({'path':p.relative_to(OUT).as_posix(),'records':0})
  z.write(line);h.update(line);files[-1]['records']+=1;partbytes+=len(line);count+=1
  if count%20000==0:print(f'{slug}: emit {count}',flush=True)
  flagged+=bool(flags);nulls+=has_null(r['input']);flagstats.update(r['quality_flags']);splits[sp]+=1
  if len(preview)<3:preview.append(r)
  st=taskstats.setdefault(task,{'labels':[],'prompt_chars_min':len(r['prompt']),'prompt_chars_max':0});st['labels'].append(r['label']);st['prompt_chars_min']=min(st['prompt_chars_min'],len(r['prompt']));st['prompt_chars_max']=max(st['prompt_chars_max'],len(r['prompt']))
 if z:z.close();raw.close()
 for sh in files:
  p=OUT/sh['path'];sh.update(sha256=sha(p),bytes=p.stat().st_size);assert sh['bytes']<50*1024*1024
 for task,st in taskstats.items():
  ys=st.pop('labels');st.update(records=len(ys),label_min=min(ys),label_max=max(ys),label_mean=normalize(statistics.mean(ys)),zero_labels=sum(v==0 for v in ys))
 stats={'dataset_id':ds,'name':meta['name'],'batch':3,'candidate_id':meta.get('candidate_id'),'raw_rows_selected':meta.get('raw_rows_selected'),'candidate_task_examples':n,'output_examples':count,'collapsed_duplicate_examples':duplicates,'invalid_label_examples':meta.get('invalid_label_examples',0),'excluded_source_rows':meta.get('excluded_source_rows',0),'task_count':len(taskstats),'split_groups':len(group_splits),'examples_with_null_input':nulls,'flagged_examples':flagged,'identical_input_different_label_groups':len(inconsistent),'cross_official_split_input_groups':len(conflict),'cross_official_split_entity_groups':len(crossgroups),'split_counts':dict(splits),'source_url':meta['source_url'],'files':files,'uncompressed_sha256':h.hexdigest()}
 if ds.startswith('uci_'):stats['uci_id']=int(ds[4:])
 meta.update(version='2.2.0',source_version=meta.get('version'),record_schema_version='1.0.0',stats=stats,task_statistics=taskstats,quality_flag_counts=dict(flagstats),numeric_precision={'id':'significant_digits_12_v1','relative_error_bound':5.01e-12},deduplication_rule='Same task, normalized input, normalized label AND official split; preserve all source_refs. Across-split copies retained and flagged, same-input dependencies unioned. Different labels retained.',sample_id_rule='sha256([task_id,input_hash,label,split]) first 24 hex; official split included to preserve split occurrences.')
 save(folder/'metadata.json',meta);save(folder/'prompt_templates.json',meta['tasks']);(folder/'preview.jsonl').write_text(''.join(dump(r)+'\n' for r in preview),encoding='utf-8')
 save(folder/'quality_validation.json',{'status':'passed','candidates':n,'records':count,'duplicate_occurrences_merged':duplicates,'finite_labels':True,'numeric_precision_checked':True,'official_split_occurrences_preserved':True,'quality_flag_counts':dict(flagstats),'training_executed':False})
 save(ROOT/'stats'/f'{slug}.json',stats);con.close();print(dump(stats),flush=True)
if __name__=='__main__':
 for slug in sys.argv[1:]:build(slug)
