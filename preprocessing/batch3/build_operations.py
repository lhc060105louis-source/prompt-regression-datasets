"""Approved UCI 713/335 source acquisition and lossless candidate projection; no training."""
import csv, hashlib, io, json, math, pathlib, urllib.request, zipfile
ROOT=pathlib.Path(__file__).resolve().parent
def save(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def acquire(ds,name,url):
 p=ROOT/'raw'/ds/name;p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():
  with urllib.request.urlopen(url,timeout=180) as r:p.write_bytes(r.read())
 return p,{'path':p.relative_to(ROOT).as_posix(),'url':url,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def number(s):
 v=float(s);assert math.isfinite(v)
 return int(v) if v.is_integer() else v
def build(ds,uid,slug):
 url=f'https://archive.ics.uci.edu/dataset/{uid}/{slug}'
 arc,source=acquire(ds,'source.zip',f'https://archive.ics.uci.edu/static/public/{uid}/{slug}.zip')
 page,license_source=acquire(ds,'source_page.html',url)
 assert 'CC BY 4.0' in page.read_text(encoding='utf-8')
 z=zipfile.ZipFile(arc);wanted='data.csv' if ds=='auction' else 'transcoding_mesurment.tsv'
 names=[x for x in z.namelist() if x.rsplit('/',1)[-1]==wanted];assert len(names)==1
 data=z.read(names[0]);(arc.parent/wanted).write_bytes(data)
 for name in z.namelist():
  if name.rsplit('/',1)[-1].lower()=='readme.txt':(arc.parent/'README.txt').write_bytes(z.read(name))
 reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig')),delimiter=',' if ds=='auction' else '\t')
 rows=list(reader);print(ds,len(rows),reader.fieldnames,flush=True)
 out=ROOT/'candidates'/f'{ds}.jsonl';out.parent.mkdir(exist_ok=True)
 flags_count={};invalid=[];groups=set()
 with out.open('w',encoding='utf-8',newline='\n') as f:
  for n,row in enumerate(rows,1):
   if ds=='auction':
    x={'bidder_capacities':[number(row[f'process.b{i}.capacity']) for i in range(1,5)],'property_price':number(row['property.price']),'property_product':number(row['property.product']),'property_winner':number(row['property.winner'])}
    y=number(row['verification.time']);group=json.dumps(x['bidder_capacities'],separators=(',',':'));flags=['source_aggregated_mean'];key='mean_verification_time';unit='ms'
   else:
    x={k:(v if k in ['codec','o_codec'] else number(v)) for k,v in row.items() if k not in ['id','utime','umem']}
    y=number(row['utime']);group=row['id'];flags=[];key='transcoding_time';unit='s'
    if x['i']+x['p']+x['b']!=x['frames']:flags.append('source_frame_count_mismatch')
    if x['i_size']+x['p_size']+x['b_size']!=x['size']:flags.append('source_size_component_mismatch')
    if any(x[k]<=0 for k in ['duration','bitrate','framerate','o_bitrate','o_framerate','width','height','o_width','o_height']):flags.append('nonpositive_input_preserved')
   if y<0:invalid.append({'row':n,'reason':'negative_runtime'});continue
   groups.add(group)
   for flag in flags:flags_count[flag]=flags_count.get(flag,0)+1
   r=dict(input=x,label=y,task_key=key,target_name=key,unit=unit,target_type='continuous',group_key=group,source_refs=[{'file':wanted,'row':n}],split='unassigned',quality_flags=flags)
   if ds=='transcoding':r['entity_id']=group
   f.write(json.dumps(r,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
 if ds=='auction':
  instruction='Estimate the mean verification runtime for the published four-bidder, six-product simultaneous multi-round auction model on its source execution setup.'
  description='bidder_capacities: ordered capacities of bidders 1 through 4, each the maximum number of products the bidder may win; property_price: queried price in source auction price units; property_product: queried product identifier; property_winner: queried bidder, with 0 indicating a price-only property. Verification outcome is not available as input.'
  findings=['The source table aggregates repeated seven-feature configurations into mean runtimes. Original replicate counts and run-level uncertainty cannot be reconstructed.','verification.result excluded as another measured outcome.','Group by ordered bidder-capacity configuration; unassigned splits require whole-group holdouts.']
 else:
  instruction='Estimate the recorded transcoding runtime on the source Intel i7-3720QM execution setup from input-video characteristics and the requested output encoding settings.'
  description='duration: original video duration in seconds; codec/o_codec: input/requested output codec; width,height,o_width,o_height: input/output pixel dimensions; bitrate,o_bitrate: source-recorded input/output bitrate values, unscaled; framerate,o_framerate: frames per second; i,p,b: source counts of I/P/B frames; frames: total frames; i_size,p_size,b_size,size: source-recorded component and total byte sizes. The source experiment transcodes short segments; full original duration is metadata, not a claim of processing every original frame. Output memory consumption is excluded.'
  findings=['Only the 68,784-row labeled transcoding measurement table is used. The companion unlabeled YouTube metadata table and video media are not republished.','umem is an execution outcome and is excluded; id is provenance/grouping only.','b_size is retained from the original source even when constant, unlike some OpenML projections.','Same-video configurations share a group. Fixed-hardware timings do not establish cross-hardware performance.']
 meta={'dataset_id':f'uci_{uid}','name':'Auction Verification' if ds=='auction' else 'Online Video Transcoding Time','candidate_id':'O1' if ds=='auction' else 'O2','source_url':url,'version':'UCI public archive snapshot 2026-11-15','license':{'name':'CC BY 4.0','url':'https://creativecommons.org/licenses/by/4.0/','evidence':license_source},'source_files':[source,license_source], 'source_citation':{'doi':'10.24432/C52K6N' if ds=='auction' else '10.24432/C58C9K','authors':['Elaheh Ordoni','Jakob Bach','Ann-Katrin Fleck'] if ds=='auction' else ['Tewodros Deneke']},'raw_rows_selected':len(rows),'excluded_source_rows':0,'invalid_label_examples':len(invalid),'candidate_task_examples':len(rows)-len(invalid),'grouping_rule':'ordered bidder capacity configuration' if ds=='auction' else 'source video id','split_policy':'unassigned; whole groups must remain together','excluded_input_columns':['verification.result','verification.time'] if ds=='auction' else ['id','umem','utime'],'quality_findings':findings,'source_profile':{'fields':reader.fieldnames,'groups':len(groups),'flags':flags_count},'target_transform':'source_mean_no_additional_transform' if ds=='auction' else 'none_applied','tasks':{key:{'instruction':instruction,'target_name':key,'unit':unit,'type':'continuous','field_description':description}}}
 save(ROOT/'candidates'/f'{ds}.meta.json',meta);save(ROOT/'candidates'/f'{ds}.invalid.json',invalid)
 # Independent reread of every projected label and included source field.
 prepared=[json.loads(line) for line in out.open(encoding='utf-8')]
 for rec in prepared:
  row=rows[rec['source_refs'][0]['row']-1]
  assert rec['label']==float(row['verification.time' if ds=='auction' else 'utime'])
  assert not set(rec['input']).intersection(meta['excluded_input_columns'])
  if ds=='auction':
   assert rec['input']=={'bidder_capacities':[number(row[f'process.b{i}.capacity']) for i in range(1,5)],'property_price':number(row['property.price']),'property_product':number(row['property.product']),'property_winner':number(row['property.winner'])}
  else:
   assert rec['input']=={k:(v if k in ['codec','o_codec'] else number(v)) for k,v in row.items() if k not in ['id','utime','umem']}
   assert rec['group_key']==row['id']
 assert len(rows)==(2043 if ds=='auction' else 68784)
 save(ROOT/'candidates'/f'{ds}.validation.json',{'status':'passed','source_rows':len(rows),'candidate_records':len(prepared),'label_source_matches':len(prepared),'input_columns_checked':True,'training_executed':False})
if __name__=='__main__':
 build('auction',713,'auction+verification')
 build('transcoding',335,'online+video+characteristics+and+transcoding+time+dataset')
