"""Full prepared-record audit and candidate-to-release source fidelity check."""
import collections, gzip, hashlib, json, math, pathlib, sqlite3, sys
ROOT=pathlib.Path(__file__).resolve().parent
PUB=ROOT/'publish'
def js(x):return json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def hashobj(x):return hashlib.sha256(js(x).encode()).hexdigest()
def rounded(x):
 if isinstance(x,float):
  assert math.isfinite(x)
  return float(format(x,'.12g'))
 if isinstance(x,list):return [rounded(v) for v in x]
 if isinstance(x,dict):return {k:rounded(v) for k,v in x.items()}
 return x
def check_numbers(v):
 if isinstance(v,float):assert math.isfinite(v) and v==float(format(v,'.12g'))
 elif isinstance(v,dict):
  for x in v.values():check_numbers(x)
 elif isinstance(v,list):
  for x in v:check_numbers(x)
def validate(slug):
 stat=json.loads((ROOT/'stats'/f'{slug}.json').read_text());folder=PUB/pathlib.Path(stat['files'][0]['path']).parent
 meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'));ds=meta['dataset_id'];seen=set();tot=occ=0;keys={};group_splits=collections.defaultdict(set);groups_for_input={}
 # Disk-backed occurrence audit avoids retaining large history windows in RAM.
 dbpath=ROOT/f'{slug}.verify.sqlite'
 if dbpath.exists():dbpath.unlink()
 con=sqlite3.connect(dbpath);con.execute('PRAGMA synchronous=OFF');con.execute('PRAGMA journal_mode=OFF');con.execute('CREATE TABLE records (id TEXT PRIMARY KEY,data TEXT, occurrences INTEGER)')
 for shard in stat['files']:
  with gzip.open(PUB/shard['path'],'rt',encoding='utf-8') as f:
   for line in f:
    r=json.loads(line);tot+=1
    if tot%50000==0:print(f'{slug}: schema/hash audit {tot}',flush=True)
    assert type(r['label']) in (int,float) and math.isfinite(r['label'])
    assert r['sample_id'] not in seen;seen.add(r['sample_id'])
    assert r['input_hash']==hashobj(r['input'])
    assert r['sample_id']==ds+'/'+hashobj([r['task_id'],r['input_hash'],r['label'],r['split']])[:24]
    assert r['dataset_id']==ds and r['group_id'].startswith(ds+'/')
    prompt_input=r['prompt'].split('\nInput JSON: ',1)[1].rsplit('\nReturn only one numeric prediction for the target.',1)[0]
    assert json.loads(prompt_input)==r['input']
    task=r['task_id'].split('/',1)[1];definition=meta['tasks'][task]
    assert (r['target_name'],r['unit'],r['type'])==(definition['target_name'],definition['unit'],definition['type'])
    assert r['split'] in ('train','validation','test','unassigned')
    assert isinstance(r['source_refs'],list) and r['source_refs']
    assert not set(r['input']).intersection(meta.get('excluded_input_columns',[]))
    check_numbers(r['input']);check_numbers(r['label'])
    ih=r['input_hash'];group_splits[r['group_id']].add(r['split'])
    assert ih not in groups_for_input or groups_for_input[ih]==r['group_id'];groups_for_input[ih]=r['group_id']
    key=hashobj([task,ih,r['label'],r['split']]);con.execute('INSERT INTO records VALUES(?,?,?)',(key,line,r['duplicate_count']));occ+=r['duplicate_count']
 con.commit();candidates=0
 with (ROOT/'candidates'/f'{slug}.jsonl').open(encoding='utf-8') as f:
  for line in f:
   c=json.loads(line);x=rounded(c['input']);y=rounded(c['label'])
   # Numeric JSON integers are canonicalized to match the documented formatter.
   def integers(v):
    if isinstance(v,float) and v.is_integer():return int(v)
    if isinstance(v,list):return [integers(a) for a in v]
    if isinstance(v,dict):return {k:integers(a) for k,a in v.items()}
    return v
   x=integers(x);y=integers(y);ih=hashobj(x);key=hashobj([c['task_key'],ih,y,c['split']]);row=con.execute('SELECT data,occurrences FROM records WHERE id=?',(key,)).fetchone();assert row
   r=json.loads(row[0]);assert r['input']==x and r['label']==y and r['split']==c['split']
   for ref in c['source_refs']:assert ref in r['source_refs']
   assert row[1]>0;con.execute('UPDATE records SET occurrences=occurrences-1 WHERE id=?',(key,));candidates+=1
   if candidates%50000==0:print(f'{slug}: candidate fidelity {candidates}',flush=True)
 assert con.execute('SELECT count(*) FROM records WHERE occurrences!=0').fetchone()[0]==0
 assert candidates==occ==stat['candidate_task_examples'];assert tot==stat['output_examples']
 # All raw inventory hashes must verify against downloaded files.
 inventories=0
 for item in meta['source_files']:
  relative=item.get('relativepath',item.get('path'));assert relative
  path=ROOT/relative;assert path.exists(),path
  h=hashlib.sha256()
  with path.open('rb') as f:
   for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
  assert h.hexdigest()==item['sha256'];assert path.stat().st_size==item['bytes'];inventories+=1
 con.close()
 result={'status':'passed','dataset_id':ds,'records':tot,'source_candidate_occurrences':candidates,'raw_inventory_files_checked':inventories,'checks':['finite scalar labels','input/prompt equality','numeric precision','source-candidate label and input equality under declared rounding','all source references retained','official split occurrence preservation','same-input group closure','unique sample IDs','raw source checksums'],'training_executed':False}
 (ROOT/'stats'/f'{slug}.validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(js(result),flush=True)
if __name__=='__main__':
 for slug in sys.argv[1:]:validate(slug)
