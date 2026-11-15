"""Integrate approved batch into an isolated copy of the existing GitHub distribution."""
import collections, csv, gzip, hashlib, importlib.metadata, json, os, pathlib, platform, shutil
ROOT=pathlib.Path(__file__).resolve().parent;PUB=ROOT/'publish'
BASE=pathlib.Path(os.environ.get('JEV_BASE_RELEASE',str(ROOT/'baseline')))
SOURCES={'complex':'T1','empathy':'T2','asap2':'T3','freesolv':'S1','gb1':'S2','jdft2d':'S4','cmapss':'H1','camels_gb':'H2','auction':'O1','transcoding':'O2'}
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 old=load(BASE/'manifest.json');assert old['version']=='2.1.0';manifest=load(BASE/'manifest.json');oldchecks=load(BASE/'checksums.json')
 preserved={p:s for p,s in oldchecks.items() if p.startswith(('datasets/','sources/'))}
 for p,s in preserved.items():assert sha(PUB/p)==s,f'Existing valid file changed: {p}'
 save(PUB/'history/v2.1.0/manifest.json',old);save(PUB/'history/v2.1.0/checksums.json',oldchecks)
 reports=[];stats=[];metas={}
 for slug,cid in SOURCES.items():
  st=load(ROOT/'stats'/f'{slug}.json');validation=load(ROOT/'stats'/f'{slug}.validation.json');assert validation['status']=='passed'
  folder=PUB/pathlib.Path(st['files'][0]['path']).parent;meta=load(folder/'metadata.json');st['candidate_id']=cid;meta['candidate_id']=cid
  for item in meta['source_files']:
   if 'relativepath' not in item:item['relativepath']=item.pop('path')
  # Refresh source-level findings after final audits, preserving generated schema/templates/inventory.
  latest=load(ROOT/'candidates'/f'{slug}.meta.json')
  generated={'version','source_files','tasks','stats','deduplication_rule','sample_id_rule','numeric_precision','task_statistics','quality_flag_counts','record_schema_version'}
  for key,value in latest.items():
   if key not in generated:meta[key]=value
  if slug in ['auction','transcoding']:
   evidence=load(ROOT/'review_root.json')['units_evidence']
   meta['unit_evidence']={k:v for k,v in evidence.items() if k.startswith('auction' if slug=='auction' else 'transcoding')}
  st['excluded_source_rows']=latest.get('excluded_source_rows',0);meta['stats']=st;save(folder/'metadata.json',meta)
  shutil.copy2(ROOT/'stats'/f'{slug}.validation.json',folder/'record_validation.json')
  srcdir=PUB/'sources'/st['dataset_id'];srcdir.mkdir(parents=True,exist_ok=True)
  save(srcdir/'source_manifest.json',{'candidate_id':cid,'source_url':meta['source_url'],'source_version':meta.get('source_version'),'files':meta['source_files'],'raw_archives_included':False,'license':meta['license'],'citation':meta.get('source_citation'),'preparation':'See preprocessing/batch3 and per-dataset metadata. Raw files remain unmodified locally; prepared records are adapted.'})
  for item in meta['source_files']:
   rel=item['relativepath'];p=ROOT/rel;assert sha(p)==item['sha256'];name=p.name.lower()
   if (name.startswith(('readme','license','copying')) or name.endswith(('_metadata.json','license.html','license.md')) or name in ['figshare_v1.json']) and p.stat().st_size<200000:
    shutil.copy2(p,srcdir/p.name)
  raw=ROOT/'raw'/slug
  for name in ['validation.json','source_validation.json','population_validation.json','archive_inventory.json']:
   if (raw/name).exists():shutil.copy2(raw/name,srcdir/name)
  for p in raw.glob('*exclusions*.jsonl'):
   with p.open('rb') as source,(srcdir/(p.name+'.gz')).open('wb') as target,gzip.GzipFile(filename='',fileobj=target,mode='wb',mtime=0) as z:shutil.copyfileobj(source,z)
  stats.append(st);metas[slug]=meta;reports.append(validation)
 manifest['datasets'].extend(stats);manifest.update(version='2.2.0',source_release='2.2.0',distribution_version='2.2.0-github.1',updated_date='2026-11-15',dataset_count=len(manifest['datasets']),task_count=sum(d['task_count'] for d in manifest['datasets']),total_examples=sum(d['output_examples'] for d in manifest['datasets']),training_performed=False,local_only=False,splits_assigned=True,split_policy='Mixed: published official splits retained for CompLex, ASAP2, C-MAPSS; all other tasks unassigned. Cross-split dependent groups flagged. No new randomized split created.')
 manifest['total_selected_source_rows']=old['total_selected_source_rows']+sum(st['raw_rows_selected'] for st in stats)
 for key in ['collapsed_duplicate_examples','invalid_label_examples','excluded_source_rows']:manifest[key]=old[key]+sum(st.get(key,0) for st in stats)
 manifest['exclusion_count_note']='Source row exclusions only. Excluded engines/windows and unsampled temporal origins have separate source-specific counts; do not add these different units.'
 newcount=sum(st['output_examples'] for st in stats);manifest['batches'].append({'batch':3,'datasets':10,'tasks':sum(st['task_count'] for st in stats),'examples':newcount,'approved_candidate_ids':list(SOURCES.values())})
 save(PUB/'manifest.json',manifest)
 schema=load(BASE/'schema.json');schema['split']=manifest['split_policy'];schema['type']='continuous for measured/derived scalar targets; ordinal for ordered discrete scores such as ASAP2 1–6';schema['target_transform']='Per-source declared transformation; no new statistical scaling. Source means/relative fitness are identified in metadata.';schema['sample_id']='For batch 3 sha256([task_id,input_hash,label,official_split]) first 24 hex; earlier release IDs unchanged.';save(PUB/'schema.json',schema)
 readme=(BASE/'README.md').read_text(encoding='utf-8').replace('Release 2.1.0 · 29 sources · 33 regression tasks · 1,067,479 examples',f'Release 2.2.0 · 39 sources · {manifest["task_count"]} regression tasks · {manifest["total_examples"]:,} examples').replace('and all splits remain `unassigned`','and published official splits are retained where available; the remaining tasks have unassigned splits').replace('all 29 datasets','all 39 datasets').replace('`target_name`, `target_unit`, `target_transform`','`target_name`, `unit`, `target_transform`').replace('`unassigned` for this release','Official `train`/`validation`/`test` where provided, otherwise `unassigned`')
 readme=readme.replace('## Rebuild from original sources','## Rebuild the legacy v2.1.0 sources').replace('Using a separate Python environment is recommended.','For the ten newly added sources, use [batch 3 reproduction instructions](preprocessing/batch3/README.md). The commands below rebuild only the legacy 29 sources.\n\nUsing a separate Python environment is recommended.')
 if '中文说明：' in readme:readme=readme.split('中文说明：',1)[0]+f'中文说明：当前 v2.2.0 共 39 个来源、{manifest["task_count"]} 个任务、{manifest["total_examples"]:,} 条样本；旧 29 个来源文件保持不变。保留可用的官方划分，其他来源未分配划分。未训练。详见[质量报告](reports/quality_report_zh.md)。\n'
 readme+='\n## Approved expansion 2.2.0\n\nTen approved sources add lexical complexity, empathy/distress, essay quality, experimental hydration free energy, GB1 binding fitness, DFT exfoliation energy, engine remaining life, river flow, auction verification time and video transcoding time. All 29 original sources and their files remain byte-identical.\n\nASAP2 excludes third-party source reading materials. C-MAPSS uses 30-cycle windows at stride 10 plus endpoints; 17 short test engines are excluded. CAMELS-GB uses month-end forecast origins, seven complete historical daily records ending one day before the origin, and next-day flow labels; this is a sampled archival forecast task. No training was run.\n\nSee [batch 3 quality report](reports/quality_report_v2.2.0_zh.md), [source-level findings](reports/extension_metadata_summary.json), [full-record validation](reports/extension_validation.json), [approval ledger](docs/candidate_approval.csv), and [reproduction instructions](preprocessing/batch3/README.md). Official splits can still contain dependent groups; CompLex has such flagged groups. GB1 covers one protein background, and FreeSolv scaffold groups are imbalanced.\n'
 (PUB/'README.md').write_text(readme,encoding='utf-8')
 reader=PUB/'scripts/read_dataset.py';text=reader.read_text(encoding='utf-8');text=text.replace('dataset_id==f\'uci_{d["uci_id"]}\'','dataset_id==d.get("dataset_id", "uci_"+str(d.get("uci_id")))');reader.write_text(text,encoding='utf-8')
 cat=(BASE/'docs/catalogue.md').read_text(encoding='utf-8')+'\n## Approved structured and text expansion\n\n| Approval | Dataset ID | Source | Examples | Tasks | Data |\n|---|---|---|---:|---:|---|\n'
 licenses=(BASE/'DATA_LICENSES.md').read_text(encoding='utf-8')+'\n## Batch 3 attribution and adaptations\n\nThe license table above applies to the legacy UCI sources. New sources retain the individual licenses below. Prepared inputs select fields, serialize structures/history, group dependencies, round numeric storage, and add prompts. Third-party ASAP reading materials are excluded.\n\n'
 licenses=licenses.replace('Sources except UCI 925:','Legacy UCI sources except UCI 925:')
 examples=(BASE/'docs/examples.md').read_text(encoding='utf-8')+'\n## Added source previews\n\n'
 for slug,st in zip(SOURCES,stats):
  meta=metas[slug];folder=pathlib.Path(st['files'][0]['path']).parent.as_posix();cat+=f'| {SOURCES[slug]} | {st["dataset_id"]} | [{st["name"]}]({st["source_url"]}) | {st["output_examples"]:,} | {st["task_count"]} | [Files](../{folder}) |\n'
  lic=meta['license'];licenses+=f'### {SOURCES[slug]} — {meta["name"]}\n\nSource: {meta["source_url"]}\n\nLicense and evidence:\n```json\n{json.dumps(lic,ensure_ascii=False,indent=2)}\n```\n\nCitation: {json.dumps(meta.get("source_citation"),ensure_ascii=False)}\n\nSee [{st["dataset_id"]} metadata]({folder}/metadata.json) for changes and limitations.\n\n'
  examples+=f'- {SOURCES[slug]} [{meta["name"]}](../{folder}/preview.jsonl), {st["output_examples"]:,} records.\n'
 (PUB/'docs/catalogue.md').write_text(cat,encoding='utf-8');(PUB/'DATA_LICENSES.md').write_text(licenses.rstrip()+'\n',encoding='utf-8');(PUB/'docs/examples.md').write_text(examples,encoding='utf-8')
 sourceledger=ROOT.parents[1]/'outputs/Jev_26候选_审批清单.csv';rows=list(csv.DictReader(sourceledger.open(encoding='utf-8-sig')))
 for row in rows:
  row['approval']='approved_and_prepared_without_reading_materials' if row['candidate_id']=='T3' else 'approved_and_prepared' if row['candidate_id'] in SOURCES.values() else 'pending'
  if row['candidate_id'] in SOURCES.values():
   st=next(s for s in stats if s['candidate_id']==row['candidate_id']);row['source_size']=f'{st["raw_rows_selected"]:,} source rows; {st["output_examples"]:,} prepared records'
 with (PUB/'docs/candidate_approval.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 scripts=PUB/'preprocessing/batch3';scripts.mkdir(parents=True,exist_ok=True)
 for name in ['build_text.py','build_science.py','build_temporal.py','build_operations.py','standardize.py','validate_extension.py','package_extension.py','write_quality_report.py']:
  shutil.copy2(ROOT/name,scripts/name)
 packages={name:importlib.metadata.version(name) for name in ['pandas','numpy','requests']};save(scripts/'build_environment.json',{'python':platform.python_version(),'platform':platform.platform(),'packages':packages,'rdkit':metas['freesolv'].get('rdkit_version','See source metadata'), 'training_performed':False})
 (scripts/'requirements.txt').write_text('\n'.join(f'{k}=={v}' for k,v in packages.items())+'\nrdkit=='+metas['freesolv']['rdkit_version']+'\n',encoding='utf-8')
 (scripts/'README.md').write_text('''# Reproduce batch 3

These scripts only acquire/prepare/validate data; they never train. Use an isolated working directory and install requirements. Raw archives are not distributed. Source manifests freeze commit URLs and SHA256; compare every downloaded raw file before rebuilding. Mutable source documentation may need the recorded snapshot.

Run the source builders from this directory: `python build_text.py --download --build`, `python build_science.py --download --extra-sources --build --validate`, `python build_temporal.py --download`, and `python build_operations.py`. See each script `--help` where applicable. Each builder writes `raw/` and `candidates/` beside itself. RDKit is needed for FreeSolv canonicalization/scaffolds. The public ASAP test password is read from the repository README; third-party reading ZIPs are never requested.

`python standardize.py complex empathy asap2 freesolv gb1 jdft2d cmapss camels_gb auction transcoding` writes generated sources under `publish/`, then `python validate_extension.py` with the same IDs performs full record/source-candidate checks. Per-source builders also run original-row fidelity checks. The checked-in `package_extension.py` documents the original isolated integration; set JEV_BASE_RELEASE to a checkout of v2.1.0 and provide the approval ledger if rerunning integration in another workspace. It is not necessary for loading or validating published data. Use `python scripts/verify_release.py` from repository root to verify the distribution.

No random partition, fitted preprocessing, label imputation or experimental training is performed. Preserve official test sets and honor group/time dependencies when designing a later experiment.
''',encoding='utf-8')
 save(PUB/'reports/extension_validation.json',{'status':'passed','version':'2.2.0','records_added':newcount,'old_source_files_preserved':len(preserved),'old_manifest_version':'2.1.0','datasets':reports,'training_executed':False})
 save(PUB/'reports/extension_metadata_summary.json',{slug:{k:v for k,v in metas[slug].items() if k not in ['source_files','archive_members','tasks']} for slug in SOURCES})
 save(PUB/'reports/old_source_integrity.json',{'status':'passed','baseline_commit':'d9f763f0a70557c688c94735a98e93b4c2a87252','checked_files':preserved,'unchanged_sources':29,'unchanged_records':1067479})
 save(PUB/'reports/independent_reviews.json',{'reviews':[load(ROOT/p) for p in ['review_root.json','review_package.json','review_temporal.json']],'integration_resolutions':{'schema_prose':'Updated split, target transformation and sample ID descriptions for mixed data release.','operations_input_validation':'Full source projection assertions added and source builders rerun.','packaging_findings':'RDKit version, reproduction CLI, current counts and license scope corrected; independent follow-up review found no blockers.'}})
 # Quality report is generated separately after integration review.
 print(json.dumps({'sources':39,'tasks':manifest['task_count'],'records':manifest['total_examples'],'added':newcount,'old_files_preserved':len(preserved)}))
def checksums():
 checks={p.relative_to(PUB).as_posix():sha(p) for p in sorted(PUB.rglob('*')) if p.is_file() and '.git' not in p.relative_to(PUB).parts and p.name!='checksums.json' and '__pycache__' not in p.parts}
 # Historical checksums are themselves immutable evidence and can be hashed too.
 checks['history/v2.1.0/checksums.json']=sha(PUB/'history/v2.1.0/checksums.json');save(PUB/'checksums.json',checks)
if __name__=='__main__':main()
