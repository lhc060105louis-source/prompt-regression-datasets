"""Reproducible, source-pinned preparation of approved text regression sources.

Only approved text/labels and source documentation are fetched. In particular,
ASAP third-party source reading texts and empathy news articles are not fetched.
"""
from pathlib import Path
import csv, hashlib, io, json, math, sys, zipfile, re
from collections import Counter, defaultdict
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
OUT = ROOT / 'candidates'
SOURCES = {
 'complex': ('MMU-TDMLab/CompLex','4b31c2bd34da4c1265f9db3d727d95ee23099f14'),
 'empathy': ('wwbp/empathic_reactions','3ddbf6b35c789f99c930a349f3fc26b4b2d9ae2e'),
 'asap2': ('scrosseye/ASAP_2.0','060ab225ca0984c0bf43ff222bf6bb2bc6195b6f'),
}

def dump(path, value):
 path.parent.mkdir(parents=True, exist_ok=True)
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def fetch(ds,path):
 repo,commit=SOURCES[ds]
 url=f'https://raw.githubusercontent.com/{repo}/{commit}/{quote(path)}'
 target=RAW/ds/path
 if not target.exists():
  target.parent.mkdir(parents=True,exist_ok=True)
  response=requests.get(url,timeout=180);response.raise_for_status()
  target.write_bytes(response.content)
 return target

def download():
 for ds in SOURCES: fetch(ds,'Readme.md' if ds=='complex' else 'README.md')
 for stage,tail in [('train','train'),('trial','trial'),('test-labels','test')]:
  for kind in ['single','multi']:fetch('complex',f'{stage}/lcp_{kind}_{tail}.tsv')
 fetch('empathy','data/responses/data/messages.csv')
 for stage in ['train','test']:fetch('asap2',f'ASAP_2_Final_github_{stage}.zip')

def inspect():
 for ds in SOURCES:
  print(ds,(RAW/ds/('Readme.md' if ds=='complex' else 'README.md')).read_text(encoding='utf-8'))
 for path in (RAW/'asap2').glob('*.zip'):
  with zipfile.ZipFile(path) as z:
   print(path.name,[(x.filename,x.file_size,x.compress_type,x.flag_bits) for x in z.infolist()])
   for name in z.namelist():
    if name.endswith('.csv'):
     try:
      data=z.read(name,pwd=b'asap2_test').decode('utf-8-sig')
      rows=list(csv.DictReader(io.StringIO(data)))
      print('rows',len(rows),'columns',list(rows[0]),'first nontext',{k:v for k,v in rows[0].items() if len(v)<100})
     except Exception as e:print(type(e).__name__,str(e))

def sha(value):return hashlib.sha256(value).hexdigest()
def text_key(value):return sha(re.sub(r'\s+',' ',value).strip().casefold().encode())
def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def records(path,delimiter=','):
 # CompLex is literal tab-delimited text; quotation marks belong to sentences.
 # CSV-style quoting would merge test records whose sentence begins with a quote.
 with path.open(encoding='utf-8-sig',newline='') as f:
  rows=list(csv.DictReader(f,delimiter=delimiter,quoting=csv.QUOTE_NONE if delimiter=='\t' else csv.QUOTE_MINIMAL))
 assert all(None not in r and all(v is not None for v in r.values()) for r in rows)
 return rows

class UnionFind:
 def __init__(self):self.parent={}
 def find(self,key):
  self.parent.setdefault(key,key)
  if self.parent[key]!=key:self.parent[key]=self.find(self.parent[key])
  return self.parent[key]
 def join(self,a,b):
  a,b=self.find(a),self.find(b)
  if a!=b:self.parent[max(a,b)]=min(a,b)

def base_meta(ds,name,tasks,fields):
 repo,commit=SOURCES[ds]
 entries=[]
 for p in sorted((RAW/ds).rglob('*')):
  if not p.is_file() or p.name in ['quality_audit.json','source_manifest.json','validation.json']:continue
  rel=p.relative_to(RAW/ds).as_posix()
  entries.append({'relativepath':rel,'url':f'https://raw.githubusercontent.com/{repo}/{commit}/{quote(rel)}',
                  'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
 readme='Readme.md' if ds=='complex' else 'README.md'
 return {'dataset_id':ds,'name':name,'source_url':f'https://github.com/{repo}',
 'license':{'name':'CC BY 4.0','url':'https://creativecommons.org/licenses/by/4.0/',
            'evidence_url':f'https://github.com/{repo}/blob/{commit}/{readme}',
            'evidence_file':readme,'scope':'Dataset text and numeric ratings; excludes third-party article/reading-material full texts.'},
 'version':commit,'commit':commit,'source_files':entries,'tasks':tasks,'field_descriptions':fields,
 'downloaded_at':'2026-11-15','training_executed':False,
 'text_policy':'Original selected text and capitalization preserved byte-for-byte after UTF-8/CSV decoding; grouping uses a separate whitespace-normalized casefolded hash. No spelling correction, truncation, label imputation, or score transformation.',
 'raw_archives_included_in_distribution':False}

def finalize(ds,rows,meta,source_rows,excluded,invalid):
 assert all(isinstance(x['label'],(int,float)) and math.isfinite(x['label']) for x in rows)
 assert all(x['input'] for x in rows)
 exact=Counter((x['task_key'],encoded(x['input']),x['label']) for x in rows)
 inputs=defaultdict(set);splits=defaultdict(set);group_splits=defaultdict(set)
 for x in rows:
  key=(x['task_key'],encoded(x['input']))
  inputs[key].add(x['label']);splits[key].add(x['split'])
  group_splits[x['group_key']].add(x['split'])
 for x in rows:
  if len(splits[(x['task_key'],encoded(x['input']))])>1:x['quality_flags'].append('identical_input_crosses_official_splits')
  if len(group_splits[x['group_key']])>1:x['quality_flags'].append('group_crosses_official_splits')
  if len(inputs[(x['task_key'],encoded(x['input']))])>1:x['quality_flags'].append('identical_input_has_different_labels')
 meta.update(raw_rows_selected=source_rows,candidate_task_examples=len(rows),excluded_source_rows=len(excluded),invalid_label_examples=len(invalid),
             excluded_rows=excluded,invalid_labels=invalid,
             split_counts=dict(Counter(x['split'] for x in rows)),task_counts=dict(Counter(x['task_key'] for x in rows)),
             groups=len(group_splits),groups_crossing_official_splits=sum(len(s)>1 for s in group_splits.values()),
             exact_duplicate_candidate_rows=sum(n-1 for n in exact.values()),
             identical_input_different_label_groups=sum(len(s)>1 for s in inputs.values()),
             identical_input_cross_split_groups=sum(len(s)>1 for s in splits.values()),
             quality_flag_counts=dict(Counter(f for x in rows for f in x['quality_flags'])),
             validation={'status':'passed','checks':['All retained labels finite and within documented rating scale',
                'Every retained input and label compared with its original decoded CSV/TSV row',
                'Every source row accounted for; invalid/missing labels never imputed',
                'Explicit input allowlists exclude source IDs, other scores, bins, demographics and article full texts',
                'Official splits retained; cross-split identical inputs and connected groups counted and flagged',
                'Source version, downloaded bytes and SHA256 recorded'],'training_executed':False})
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/f'{ds}.jsonl').open('w',encoding='utf-8',newline='\n') as f:
  for x in rows:f.write(encoded(x)+'\n')
 dump(OUT/f'{ds}.meta.json',meta)
 dump(RAW/ds/'source_manifest.json',{'dataset_id':ds,'commit':meta['commit'],'source_files':meta['source_files']})
 dump(RAW/ds/'validation.json',{'dataset_id':ds,'status':'passed','raw_rows':source_rows,'candidate_rows':len(rows),
       'candidate_sha256':sha((OUT/f'{ds}.jsonl').read_bytes()),'source_files':meta['source_files'],'checks':meta['validation']['checks'],
       'exact_duplicate_candidate_rows':meta['exact_duplicate_candidate_rows'],'groups_crossing_official_splits':meta['groups_crossing_official_splits'],
       'quality_flag_counts':meta['quality_flag_counts'],'training_executed':False})
 print(json.dumps({'dataset':ds,'raw_rows':source_rows,'candidates':len(rows),'groups':meta['groups'],
                   'cross_split_groups':meta['groups_crossing_official_splits'],'flags':meta['quality_flag_counts']}),flush=True)

def build_complex():
 ds='complex';rows=[];n=0;invalid=[];excluded=[];uf=UnionFind()
 originals={}
 for folder,tail,split in [('train','train','train'),('trial','trial','validation'),('test-labels','test','test')]:
  for kind in ['single','multi']:
   rel=f'{folder}/lcp_{kind}_{tail}.tsv'
   for number,r in enumerate(records(RAW/ds/rel,'\t'),1):
    n+=1;ref={'file':rel,'row':number,'source_id':r['id']}
    try:label=float(r['complexity']);assert math.isfinite(label) and 0<=label<=1
    except (ValueError,AssertionError):invalid.append({**ref,'reason':'missing_nonfinite_or_out_of_range_complexity'});continue
    if not r['sentence'].strip() or not r['token'].strip():excluded.append({**ref,'reason':'empty_sentence_or_token'});continue
    tok='token:'+r['token'].casefold().strip();sent='sentence:'+text_key(r['sentence']);uf.join(tok,sent)
    inp={'sentence':r['sentence'],'target_token':r['token'],'corpus':r.get('corpus',r.get('subcorpus')),'expression_type':kind}
    flags=[]
    if r['token'].casefold() not in r['sentence'].casefold():flags.append('target_token_not_literal_substring')
    row={'input':inp,'label':label,'task_key':'lexical_complexity','target_name':'lexical_complexity','unit':'dimensionless (0-1)',
      'target_type':'continuous','group_key':tok,'source_refs':[ref],'split':split,'quality_flags':flags}
    originals[(rel,number)]=(r,kind);rows.append(row)
 for x in rows:
  x['group_key']='complex/'+sha(uf.find(x['group_key']).encode())[:24]
  ref=x['source_refs'][0];r,kind=originals[(ref['file'],ref['row'])]
  assert x['label']==float(r['complexity']) and x['input']=={'sentence':r['sentence'],'target_token':r['token'],'corpus':r.get('corpus',r.get('subcorpus')),'expression_type':kind}
 fields={'sentence':'Original English sentence providing context.','target_token':'Word or multiword expression to assess.','corpus':'Source domain: bible, biomed or europarl.','expression_type':'single for a single word, multi for a multiword expression.'}
 meta=base_meta(ds,'CompLex 2.0 / SemEval 2021 Task 1',{'lexical_complexity':{'instruction':'Predict the lexical complexity of the target word or expression in its English sentence. Scores range from 0 (least complex) to 1 (most complex).','target_name':'lexical_complexity','unit':'dimensionless (0-1)','type':'continuous','field_description':fields}},fields)
 meta.update(grouping_rule='Connected components of casefolded target tokens and whitespace-normalized casefolded sentences, spanning both expression types. Group IDs do not alter official splits.',
  split_policy='Official train retained; official trial mapped to validation; labelled test retained as test. Connected groups or exact inputs crossing official partitions are flagged. For a strict grouped evaluation, assign entire groups jointly before fitting; never use row order as a feature.',
  source_citation='Shardlow et al. (2021), SemEval-2021 Task 1: Lexical Complexity Prediction, https://aclanthology.org/2021.semeval-1.1/',
  quality_findings=['Sentence-level deduplication would discard distinct lexical targets and is not performed.','TSV is parsed without CSV quote handling: quotation marks in sentences are literal source text.','Trial uses column subcorpus; train/test use corpus. Both are mapped to input.corpus without changing their values.','Original file order can reflect complexity; source row and ID are provenance only.','Crowd-averaged Likert ratings are continuous on the published 0-1 scale.'])
 finalize(ds,rows,meta,n,excluded,invalid)

def build_empathy():
 ds='empathy';rel='data/responses/data/messages.csv';source=records(RAW/ds/rel);rows=[];invalid=[];excluded=[];uf=UnionFind()
 for number,r in enumerate(source,1):
  ref={'file':rel,'row':number,'source_id':r['message_id'],'response_id':r['response_id'],'article_id':r['article_id']}
  if not r['essay'].strip():excluded.append({**ref,'reason':'empty_essay'});continue
  response='response:'+r['response_id'];uf.join(response,'essay:'+text_key(r['essay']))
  for target in ['empathy','distress']:
   try:label=float(r[target]);assert math.isfinite(label) and 1<=label<=7
   except (ValueError,AssertionError):invalid.append({**ref,'task':target,'reason':'missing_nonfinite_or_out_of_range_score'});continue
   rows.append({'input':{'essay':r['essay']},'label':label,'task_key':target,'target_name':target,'unit':'self-report scale (1-7)',
     'target_type':'continuous','group_key':response,'source_refs':[ref],'split':'unassigned','quality_flags':['self_reported_state'],
     'entity_id':'empathy/'+r['response_id']})
 for x in rows:
  x['group_key']='empathy/'+sha(uf.find(x['group_key']).encode())[:24]
  r=source[x['source_refs'][0]['row']-1]
  assert x['input']=={'essay':r['essay']} and x['label']==float(r[x['task_key']])
 fields={'essay':'Original English reaction essay written after reading a news story; the news article itself is not included.'}
 tasks={t:{'instruction':f"Estimate the reaction writer's self-reported {'empathic concern' if t=='empathy' else 'personal distress'} on the published scale from 1 (low) to 7 (high).",'target_name':t,'unit':'self-report scale (1-7)','type':'continuous','field_description':fields} for t in ['empathy','distress']}
 meta=base_meta(ds,'Empathic Reactions (EMNLP 2018)',tasks,fields)
 meta.update(grouping_rule='Connected components of source response_id and whitespace-normalized casefolded essay. response_id is a questionnaire response/session key, not a verified permanent participant identifier. Both targets share the same group.',
  split_policy='No new fixed split imposed. Future splits must hold out entire groups jointly across both targets. Repeated article IDs are preserved in source_refs for a separate article-disjoint evaluation; response grouping alone does not enforce article independence.',
  source_citation='Buechel, Buffone, Slaff, Ungar and Sedoc (2018), Modeling Empathy and Distress in Reaction to News Stories, https://aclanthology.org/D18-1507/',
  source_response_groups=len(set(r['response_id'] for r in source)),source_article_groups=len(set(r['article_id'] for r in source)),
  quality_findings=['Two separately supervised tasks are generated from each valid reaction; the other target and binary label fields are always excluded from input.','Labels measure the writer self-reported state and are not an objective external measure of empathy.','Only reaction essays are redistributed; no news articles fetched.'])
 finalize(ds,rows,meta,len(source),excluded,invalid)

def asap_source(stage):
 path=RAW/'asap2'/f'ASAP_2_Final_github_{stage}.zip';name=f'ASAP_2_Final_github_{stage}.csv'
 with zipfile.ZipFile(path) as z:data=z.read(name,pwd=b'asap2_test')
 return name,list(csv.DictReader(io.StringIO(data.decode('utf-8-sig')))),sha(data)

def build_asap():
 ds='asap2';rows=[];n=0;excluded=[];invalid=[];members=[];originals={};prompt_counts=Counter();assignments=defaultdict(set);missing_assignments=Counter();ids=set()
 for stage in ['train','test']:
  name,source,digest=asap_source(stage);rel=f'ASAP_2_Final_github_{stage}.zip::{name}'
  members.append({'archive':f'ASAP_2_Final_github_{stage}.zip','member':name,'sha256':digest,'records':len(source)})
  for number,r in enumerate(source,1):
   n+=1;ref={'file':rel,'row':number,'source_id':r['essay_id'],'prompt_name':r['prompt_name']}
   assert r['set']==stage and r['essay_id'] not in ids;ids.add(r['essay_id'])
   try:label=int(r['score']);assert 1<=label<=6
   except (ValueError,AssertionError):invalid.append({**ref,'reason':'missing_or_invalid_ordinal_score'});continue
   if not r['full_text'].strip():excluded.append({**ref,'reason':'empty_essay'});continue
   assignment=None if r['assignment'] in ['NA',''] else r['assignment']
   inp={'prompt_name':r['prompt_name'],'assignment':assignment,'essay':r['full_text']}
   flags=['ordinal_human_score','third_party_reading_material_omitted','student_identity_unavailable']
   if assignment is None:flags.append('assignment_missing_in_source')
   rows.append({'input':inp,'label':label,'task_key':'holistic_essay_score','target_name':'holistic_essay_score','unit':'ordinal score (1-6)',
      'target_type':'ordinal','group_key':'asap2/essay-'+text_key(r['full_text'])[:24],
      'source_refs':[ref],'split':stage,'quality_flags':flags})
   originals[(rel,number)]=r;prompt_counts[r['prompt_name']]+=1;assignments[r['prompt_name']].add(assignment)
   if assignment is None:missing_assignments[r['prompt_name']]+=1
 for x in rows:
  ref=x['source_refs'][0];r=originals[(ref['file'],ref['row'])]
  assert x['input']['essay']==r['full_text'] and x['input']['prompt_name']==r['prompt_name'] and x['label']==int(r['score'])
  assert x['input']['assignment']==(None if r['assignment'] in ['NA',''] else r['assignment'])
 fields={'prompt_name':'Original assignment topic/title, not an essay or student identifier.','assignment':'Original short assignment instructions if available; null means the source literal NA/empty, never inferred.','essay':'Original student essay. Third-party source reading materials are excluded.'}
 task={'instruction':'Predict the human holistic quality score for this persuasive essay on the ordered scale from 1 (lowest quality) to 6 (highest quality). Use the assignment topic and instructions when supplied. Source reading materials are not supplied.','target_name':'holistic_essay_score','unit':'ordinal score (1-6)','type':'ordinal','field_description':fields}
 meta=base_meta(ds,'ASAP 2.0 (essay and assignment only)',{'holistic_essay_score':task},fields)
 meta.update(grouping_rule='Whitespace-normalized casefolded essay text hashes. Source essay IDs are unique but are not student IDs; student-disjointness cannot be established. For prompt transfer, hold out whole prompt_name topics in a separate evaluation.',
  split_policy='Official train/test assignments preserved exactly. No official validation partition is provided; derive any validation split within train only, retaining connected groups. Exact/normalized duplicates across official splits are flagged, not silently reassigned.',
  source_citation='Crossley et al., ASAP 2.0 corpus; repository https://github.com/scrosseye/ASAP_2.0 ; paper https://zenodo.org/records/14781349',
  archive_members=members,prompt_counts=dict(prompt_counts),unique_source_essay_ids=len(ids),
  assignment_available_prompts=sum(any(x is not None for x in values) for values in assignments.values()),assignment_total_prompts=len(assignments),
  missing_assignment_rows_by_prompt=dict(missing_assignments),
  excluded_input_columns=['essay_id','score','set','pubpriv','economically_disadvantaged','student_disability_status','ell_status','race_ethnicity','gender','grade_level','essay_word_count','task'],
  known_cross_dataset_overlap='Publisher states that a substantial subset comes from PERSUADE 2.0. Do not treat PERSUADE and ASAP2 as independent sources in future joint splits; compare original essay identity/text first.',
  quality_findings=['The pinned archives contain 24,728 rows (17,307 train and 7,421 test); README states 24,278 and component counts sum to 24,700. File counts take precedence in this release.',
    'Labels are six ordered integer scores, not genuinely continuous measurements.','All seven prompts have short assignment instructions in some rows; 28 individual rows across five prompts have literal NA, preserved as null without filling from another essay.',
    'No third-party reading-material ZIP was downloaded or published. This is an essay/assignment-only score prediction variant; source-evidence faithfulness cannot be fully evaluated without reading materials.',
    'No student IDs are exposed by the source schema; essay IDs cannot prove student-disjointness.'])
 finalize(ds,rows,meta,n,excluded,invalid)

def build():
 build_complex();build_empathy();build_asap()

if __name__=='__main__':
 if '--download' in sys.argv:download()
 if '--inspect' in sys.argv:inspect()
 if '--build' in sys.argv:build()
