"""Reproducible approved H1/H2 preparation; local files only unless --download.

No training, imputation, normalization, or publication is performed.
"""
from __future__ import annotations
import argparse, calendar, csv, hashlib, io, json, math, pathlib, zipfile
from collections import Counter
from datetime import date, timedelta
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / 'raw'
OUT = ROOT / 'candidates'
RECORD = '8344e4f3-d2ea-44f5-8afa-86d2987543a9'
URLS = {
 'cmapss': {
  'CMAPSSData.zip':'https://zenodo.org/records/15346912/files/CMAPSSData.zip?download=1',
  'zenodo_metadata.json':'https://zenodo.org/api/records/15346912',
 },
 'camels_gb': {
  'CAMELS_GB_v1.zip':f'https://data-package.ceh.ac.uk/data/{RECORD}.zip',
  'supporting_documents.zip':f'https://data-package.ceh.ac.uk/sd/{RECORD}.zip',
  'catalogue_metadata.json':f'https://catalogue.ceh.ac.uk/documents/{RECORD}?format=json',
  'ogl_eidc_license.html':'https://eidc.ac.uk/licences/ogl/plain',
 }
}

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()

def save(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')

def emit(f,obj):
 f.write(json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')

def inventory(ds):
 return [dict(relativepath=f'raw/{ds}/{n}',url=u,sha256=sha(RAW/ds/n),bytes=(RAW/ds/n).stat().st_size)
         for n,u in URLS[ds].items() if (RAW/ds/n).exists()]

def download(ds):
 import requests
 for n,u in URLS[ds].items():
  p=RAW/ds/n;p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists() and p.stat().st_size: continue
  temp=p.with_suffix(p.suffix+'.partial')
  with requests.get(u,stream=True,timeout=(30,180)) as r:
   r.raise_for_status()
   with temp.open('wb') as f:
    for b in r.iter_content(1024*1024): f.write(b)
  temp.replace(p)
  print('Downloaded',n,p.stat().st_size,flush=True)

def cmapss():
 ds='cmapss';raw=RAW/ds;OUT.mkdir(parents=True,exist_ok=True)
 archive=raw/'CMAPSSData.zip'
 assert hashlib.md5(archive.read_bytes()).hexdigest()=='79a22f36e80606c69d0e9e4da5bb2b7a'
 z=zipfile.ZipFile(archive)
 meta_source=json.loads((raw/'zenodo_metadata.json').read_text('utf-8'))
 assert meta_source['metadata']['license']['id']=='cc-by-4.0'
 fields=['cycle']+[f'operational_setting_{i}' for i in range(1,4)]+[f'sensor_{i}' for i in range(1,22)]
 counts=Counter();by_subset={};labels=[];exclusions=[];files=[]
 with (OUT/f'{ds}.jsonl').open('w',encoding='utf-8',newline='\n') as out:
  for subset,expected in [('FD001',(100,100)),('FD002',(260,259)),('FD003',(100,100)),('FD004',(249,248))]:
   by_subset[subset]={}
   for split,expected_engines in zip(('train','test'),expected):
    name=f'{split}_{subset}.txt';blob=z.read(name)
    arr=np.loadtxt(io.BytesIO(blob));assert arr.ndim==2 and arr.shape[1]==26 and np.isfinite(arr).all()
    assert np.array_equal(arr[:,:2],arr[:,:2].astype(int))
    engines=np.unique(arr[:,0].astype(int));assert engines.tolist()==list(range(1,expected_engines+1))
    files.append(dict(file=name,sha256=hashlib.sha256(blob).hexdigest(),rows=len(arr),columns=26))
    counts['raw_sensor_rows']+=len(arr);counts[f'{split}_engines']+=len(engines)
    n=0;short=0
    rul_name=f'RUL_{subset}.txt';ruls=np.loadtxt(io.BytesIO(z.read(rul_name))).astype(int)
    assert len(ruls)==expected[1] and (ruls>=0).all()
    for engine in engines:
     indices=np.flatnonzero(arr[:,0]==engine);rows=arr[indices];end=int(rows[-1,1])
     assert rows[:,1].astype(int).tolist()==list(range(1,end+1))
     if end<30:
      short+=1;exclusions.append(dict(file=name,engine=int(engine),reason='fewer_than_30_observed_cycles',observed_cycles=end));continue
     ends=sorted(set(range(30,end+1,10))|{end}) if split=='train' else [end]
     counts['short_history_origin_cycles_not_selected']+=min(29,end)
     if split=='train': counts['valid_history_origins_not_selected_by_stride']+=max(0,end-29-len(ends))
     for t in ends:
      history=rows[t-30:t,1:].tolist()
      for row in history: row[0]=int(row[0])
      label=end-t if split=='train' else int(ruls[engine-1])
      group=f'{subset}/{split}/engine_{engine:03d}'
      refs=[dict(file=name,row=int(indices[t-1])+1,history_start_row=int(indices[t-30])+1,history_end_row=int(indices[t-1])+1)]
      if split=='train': refs[0]['failure_row']=int(indices[-1])+1
      else: refs.append(dict(file=rul_name,row=int(engine)))
      assert len(history)==30 and history[0][0]==t-29 and history[-1][0]==t
      obj=dict(input={'subset':subset,'history_columns':fields,'history':history},label=label,
        task_key='remaining_useful_life',target_name='remaining_useful_life',unit='cycles',target_type='continuous',
        group_key=group,entity_id=group,source_refs=refs,split=split,
        quality_flags=['simulated_measurements','overlapping_history_windows' if split=='train' else 'official_test_endpoint'],
        timestamp=t,history_start=t-29,forecast_origin=t,label_provenance={'definition':'failure_cycle_minus_origin' if split=='train' else 'official_test_endpoint_RUL','uncapped':True})
      emit(out,obj);n+=1;labels.append(label)
    by_subset[subset][split]={'raw_rows':len(arr),'engines':len(engines),'examples':n,'engines_excluded_short_history':short}
    counts[f'{split}_examples']+=n;counts['excluded_short_test_engines']+=short if split=='test' else 0
   blob=z.read(f'RUL_{subset}.txt');files.append(dict(file=f'RUL_{subset}.txt',sha256=hashlib.sha256(blob).hexdigest(),rows=expected[1],columns=1))
 desc='history_columns defines each of the 30 chronological history rows: cycle (operating cycles), three operational settings, and sensor_1 through sensor_21. Sensor and setting values retain original published scales; individual physical units are unspecified in the source readme. subset identifies the published operating-condition/fault scenario. No engine ID is an input feature.'
 meta=dict(dataset_id=ds,name='NASA C-MAPSS turbofan degradation',candidate_id='H1',source_url='https://zenodo.org/records/15346912',
   version='Zenodo record 15346912, version 1',license={'id':'CC-BY-4.0','url':'https://creativecommons.org/licenses/by/4.0/','evidence':'zenodo_metadata.json metadata.license.id=cc-by-4.0','attribution':'NASA Ames Prognostics Center of Excellence; A. Saxena, K. Goebel, D. Simon and N. Eklund (2008).'},
   source_citation='A. Saxena, K. Goebel, D. Simon and N. Eklund (2008). Damage Propagation Modeling for Aircraft Engine Run-to-Failure Simulation. PHM08. Dataset DOI: 10.5281/zenodo.15346912.',
   source_files=inventory(ds),archive_members=files,raw_rows_selected=counts['raw_sensor_rows'],candidate_task_examples=len(labels),output_examples=len(labels),
   invalid_label_examples=0,excluded_source_rows=0,excluded_engines=counts['excluded_short_test_engines'],exclusion_unit='test_engine_trajectories',exclusions=exclusions,
   source_row_policy='No original sensor rows or RUL labels are edited/deleted; 265256 sensor rows are read. Candidate selection excludes 17 short test trajectories and unsampled training origins. Those counts are engines/origins, not raw rows.',
   raw_record_counts={'sensor_rows':counts['raw_sensor_rows'],'official_test_RUL_rows':counts['test_engines'],'train_engines':counts['train_engines'],'test_engines':counts['test_engines']},
   tasks={'remaining_useful_life':{'instruction':'Estimate the remaining useful life of this simulated turbofan engine at the end of the observed history. Predict the number of operating cycles remaining until failure; the target is not capped.','target_name':'remaining_useful_life','unit':'cycles','type':'continuous','field_description':desc}},
   field_descriptions=desc,grouping_rule='One group per published subset, official split and engine; overlapping windows from one engine remain together. Train and test unit numbers are separate engines.',
   split_policy='Original train/test membership is preserved. No validation split is fitted or assigned. Future validation must reserve whole training engines; never randomly split overlapping windows. Official test engines with fewer than 30 cycles are excluded and enumerated.',
   sampling={'history_cycles':30,'train_stride_cycles':10,'train_endpoint_rule':'30,40,... plus each engine final cycle exactly once','test_endpoint_rule':'one official endpoint per eligible engine','short_histories':'excluded without padding'},
   counts=dict(counts),by_subset=by_subset,quality_findings=['Synthetic simulation with sensor noise; no real-engine generalization is established.','RUL is derived from train failure time and read directly from official endpoint labels for test.','Training histories overlap; all windows of an engine share a group.','The source readme final-column sensor26 typo is resolved from the 26-column schema: 2 identifiers + 3 settings + 21 sensors.','The source readme FD004 train/test engine counts are reversed: full-file counts are 249 train and 248 test; actual aggregate counts are 709 train and 707 test.','No scaling, missing-value imputation, RUL cap, or training was performed.'],
   label_summary={'min':min(labels),'max':max(labels),'zero_count':sum(x==0 for x in labels)},validation={'status':'passed','checks':['published ZIP MD5 matches','all raw arrays finite and 26 columns','actual 709 train and 707 test engines; official RUL lengths match test engines','cycles contiguous starting at 1','every candidate has precisely 30 past cycles','all labels nonnegative and source-aligned','no cross-engine history','official split preserved']})
 save(OUT/f'{ds}.meta.json',meta)
 save(raw/'archive_inventory.json',files)
 (raw/'readme.txt').write_bytes(z.read('readme.txt'))
 print('C-MAPSS',json.dumps(dict(counts)),flush=True)

def camels_gb():
 ds='camels_gb';raw=RAW/ds;OUT.mkdir(parents=True,exist_ok=True)
 z=zipfile.ZipFile(raw/'CAMELS_GB_v1.zip')
 crate=json.loads(z.read('ro-crate-metadata.json'))
 manifest={x['@id']:x for x in crate['@graph'] if x.get('@type')=='File' and 'sha256' in x}
 names=sorted(n for n in z.namelist() if '/timeseries/' in n and n.endswith('.csv'))
 assert len(names)==671
 attr_name=next(n for n in z.namelist() if n.endswith('/CAMELS_GB_topographic_attributes.csv'))
 blob=z.read(attr_name);assert hashlib.sha256(blob).hexdigest()==manifest[attr_name]['sha256']
 attrs=pd.read_csv(io.BytesIO(blob),dtype={'gauge_id':str},float_precision='round_trip')
 assert len(attrs)==671 and attrs.gauge_id.is_unique
 attr_rows={str(r['gauge_id']):(i+1,r) for i,r in attrs.iterrows()}
 attr_selected={'area':'catchment_area_km2','gauge_elev':'gauge_elevation_m_asl','gauge_lat':'gauge_latitude_degrees','gauge_lon':'gauge_longitude_degrees'}
 values=['precipitation','pet','temperature','discharge_spec']
 columns=['date','precipitation_mm_per_day','potential_evapotranspiration_mm_per_day','temperature_degC','discharge_mm_per_day']
 calendar_days=pd.date_range('1970-10-01','2015-09-30',freq='D')
 expected_dates=calendar_days.strftime('%Y-%m-%d').tolist()
 origins=np.flatnonzero(calendar_days.is_month_end)
 counts=Counter();by_catchment=[];files=[];labels=[];earliest=None;latest=None
 exclusions_path=raw/'window_exclusions.jsonl'
 with (OUT/f'{ds}.jsonl').open('w',encoding='utf-8',newline='\n') as out, exclusions_path.open('w',encoding='utf-8',newline='\n') as excluded:
  for n,name in enumerate(names,1):
   gauge=name.rsplit('/',1)[-1].split('_')[4]
   blob=z.read(name);digest=hashlib.sha256(blob).hexdigest();assert digest==manifest[name]['sha256']
   df=pd.read_csv(io.BytesIO(blob),float_precision='round_trip')
   assert df['date'].tolist()==expected_dates and len(df)==len(calendar_days)
   arr=df[values].to_numpy(dtype=float)
   attr_row,attr=attr_rows[gauge]
   static={outname:None if pd.isna(attr[col]) else float(attr[col]) for col,outname in attr_selected.items()}
   assert static['catchment_area_km2'] is not None and static['catchment_area_km2']>0
   local=Counter();local['raw_rows']=len(df);local['raw_missing_discharge']=int((~np.isfinite(arr[:,3])).sum())
   local['raw_negative_discharge']=int((arr[:,3]<0).sum())
   files.append(dict(file=name,rows=len(df),sha256=digest,bytes=len(blob)))
   for idx in origins:
    origin=expected_dates[idx];target_idx=int(idx)+1;local['month_end_origins']+=1
    reason=None
    if target_idx>=len(df): reason='target_date_outside_published_period'
    elif not math.isfinite(float(arr[target_idx,3])): reason='missing_or_nonfinite_label'
    elif arr[target_idx,3]<0: reason='negative_discharge_label'
    elif idx<7: reason='insufficient_history'
    else:
     # d-7,...,d-1: one conservative daily lag protects against water/calendar-day ambiguity.
     history_values=arr[idx-7:idx]
     if not np.isfinite(history_values).all(): reason='incomplete_history'
     elif (history_values[:,3]<0).any(): reason='negative_discharge_in_history'
    if reason:
     local[reason]+=1;emit(excluded,dict(file=name,forecast_origin=origin,target_row=target_idx+1 if target_idx<len(df) else None,reason=reason));continue
    target_date=expected_dates[target_idx]
    history=[[expected_dates[j],*arr[j].tolist()] for j in range(idx-7,idx)]
    label=float(arr[target_idx,3]);assert len(history)==7
    assert date.fromisoformat(history[-1][0])+timedelta(days=2)==date.fromisoformat(target_date)
    group='catchment_'+gauge
    obj=dict(input={'catchment_attributes':static,'forecast_origin_date':origin,'target_date':target_date,'history_columns':columns,'history':history},
      label=label,task_key='next_day_specific_discharge',target_name='next_day_specific_discharge',unit='mm/day',target_type='continuous',
      group_key=group,entity_id=gauge,split='unassigned',quality_flags=['monthly_origin_sampling','one_day_history_availability_lag','retrospective_archive'],
      source_refs=[dict(file=name,row=target_idx+1,history_start_row=int(idx)-6,history_end_row=int(idx)),dict(file=attr_name,row=attr_row)],
      timestamp=origin,history_start=history[0][0],history_end=history[-1][0],forecast_origin=origin,target_time=target_date,
      label_provenance={'column':'discharge_spec','definition':'published_daily_specific_discharge','imputed':False})
    if any(v is None for v in static.values()): obj['quality_flags'].append('missing_static_attribute')
    emit(out,obj);labels.append(label);local['examples']+=1
    earliest=target_date if earliest is None or target_date<earliest else earliest
    latest=target_date if latest is None or target_date>latest else latest
   counts.update(local);by_catchment.append({'gauge_id':gauge,**dict(local)})
   if n%100==0:print('CAMELS catchments',n,'examples',len(labels),flush=True)
 assert len(by_catchment)==671 and counts['month_end_origins']==671*len(origins)
 files.append(dict(file=attr_name,rows=len(attrs),sha256=hashlib.sha256(z.read(attr_name)).hexdigest(),bytes=len(z.read(attr_name))))
 catalogue=json.loads((raw/'catalogue_metadata.json').read_text('utf-8'))
 assert any('Open Government Licence' in x.get('value','') for x in catalogue['licences'])
 desc='history_columns defines seven chronological daily records. precipitation and potential_evapotranspiration use mm/day; temperature uses degrees Celsius; discharge uses mm/day. The last history date is one day before forecast_origin_date, providing a conservative availability lag for water-day/calendar-day conventions. target_date is the following date after the forecast origin. Static inputs are catchment area (km^2), gauge elevation (m above sea level), latitude/longitude (degrees); null means an unavailable static attribute. No catchment identifier, full-period hydrological statistic, or target-day weather is an input.'
 exclusion_reasons={k:v for k,v in counts.items() if k in ['target_date_outside_published_period','missing_or_nonfinite_label','negative_discharge_label','insufficient_history','incomplete_history','negative_discharge_in_history']}
 meta=dict(dataset_id=ds,name='CAMELS-GB v1 next-day specific discharge',candidate_id='H2',source_url=f'https://catalogue.ceh.ac.uk/documents/{RECORD}',version='CAMELS-GB v1, published 2020-02-20; source members SHA-256 checked against EIDC RO-Crate',
   license={'id':'OGL-UK-3.0','url':'https://eidc.ac.uk/licences/ogl/plain','canonical_url':'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/','evidence':'catalogue_metadata.json licences; ogl_eidc_license.html',
   'attribution':['Contains data supplied by UK Centre for Ecology & Hydrology.','Copyright UK Centre for Ecology & Hydrology.','Copyright University of Bristol.','Contains Environment Agency information, copyright Environment Agency and/or database right.','Derived from UK bedrock hydrogeological mapping and UK superficial productivity mapping, BGS copyright UKRI.','Coxon et al. (2020), DOI 10.5285/8344e4f3-d2ea-44f5-8afa-86d2987543a9.']},
   source_citation='Coxon, G.; Addor, N.; Bloomfield, J.P.; Freer, J.; Fry, M.; Hannaford, J.; Howden, N.J.K.; Lane, R.; Lewis, M.; Robinson, E.L.; Wagener, T.; Woods, R. (2020). Catchment attributes and hydro-meteorological timeseries for 671 catchments across Great Britain (CAMELS-GB). NERC Environmental Information Data Centre. https://doi.org/10.5285/8344e4f3-d2ea-44f5-8afa-86d2987543a9',
   source_files=inventory(ds),archive_members=files,raw_rows_selected=counts['raw_rows'],candidate_task_examples=counts['month_end_origins'],output_examples=len(labels),invalid_label_examples=counts['missing_or_nonfinite_label']+counts['negative_discharge_label'],
   excluded_source_rows=0,excluded_candidate_windows=sum(exclusion_reasons.values()),exclusion_unit='catchment_month_end_forecast_origins',exclusion_counts=exclusion_reasons,exclusions_file='raw/camels_gb/window_exclusions.jsonl',exclusions_sha256=sha(exclusions_path),
   source_row_policy='All original daily rows are retained unchanged in the raw archive. Monthly forecast opportunities are selected or excluded; exclusion counts are candidate windows, not original rows.',
   tasks={'next_day_specific_discharge':{'instruction':'Predict the river specific discharge for target_date in millimetres per day. The forecast origin is the end of forecast_origin_date. Use the seven supplied daily archive records, which end one day before the origin to allow for daily aggregation timing.','target_name':'next_day_specific_discharge','unit':'mm/day','type':'continuous','field_description':desc}},
   field_descriptions=desc,grouping_rule='One group per catchment ID. Catchment IDs are provenance only. Groups are not asserted to be spatially independent; nested/nearby catchments may be correlated.',
   split_policy='Unassigned. For future-time validation, divide by target date and require every history date to remain before its target; reserve a gap of at least 8 days at boundaries. For unseen-catchment evaluation reserve whole catchments and preferably whole river basins/spatial regions. No random row splitting.',
   sampling={'forecast_origins':'every calendar month-end in the complete published 1970-10-01 to 2015-09-30 period','history_records':7,'history_end_days_before_origin':1,'target_days_after_origin':1,'monthly_origin_count_per_catchment':len(origins),'reason':'Cover all catchments and all years while limiting near-repeated prompts and source size; this is a deterministic monthly subsample of daily forecasting opportunities, not all daily rows.','missing_policy':'Exclude missing/nonfinite or negative discharge label; exclude incomplete histories; never impute; preserve missing static attributes as null.'},
   counts=dict(counts),by_catchment=by_catchment,quality_findings=['Monthly origins are sampled; this does not support unbiased daily-event or flood-frequency evaluation.','Rainfall labelled d may aggregate 09:00 d to 09:00 d+1; NRFA flows may use water days or calendar days. The one-day history lag prevents overlap with the next-day target for these conventions.','Retrospectively revised and spatially processed meteorological archives do not establish real-time operational availability.','Only topographic area and gauge coordinates/elevation are selected; full-period q_mean, runoff ratio, flow quantiles and climate summaries are excluded.','Missing discharge is not zero. Zero flow is retained.','Label is the published discharge_spec in mm/day, not an invented conversion from discharge_vol.','Catchment boundary and flow observation uncertainties remain; neighboring/nested catchments are not independent.','No normalization, imputation, model fitting or training was performed.'],
   timing_references=['https://nrfa.ceh.ac.uk/data/about-data/daily-flow-data/gauged-daily-flow-data','CAMELSGB_EIDC_SupportingDocumentation.rtf: CEH-GEAR source rainfall definition and Table 1'],
   label_summary={'min':min(labels),'max':max(labels),'zero_count':sum(x==0 for x in labels),'first_target_date':earliest,'last_target_date':latest},
   validation={'status':'passed','checks':['671 source time series and one topographic table match official RO-Crate SHA-256','every daily date exactly matches the complete source calendar','all output labels and history cells are finite','seven consecutive past records with one-day availability lag','source rows are 1-based excluding CSV headers','all monthly origins accounted for as retained or explicitly excluded','no target-day measurements or full-period statistics enter input']})
 assert len(labels)+sum(exclusion_reasons.values())==counts['month_end_origins']
 save(OUT/f'{ds}.meta.json',meta);save(raw/'archive_inventory.json',files)
 print('CAMELS-GB',json.dumps(dict(counts)),flush=True)

def validate_source(ds):
 """Independent pass: reload candidates and raw arrays, verify every used value."""
 raw=RAW/ds;candidate=OUT/f'{ds}.jsonl';meta=json.loads((OUT/f'{ds}.meta.json').read_text('utf-8'))
 checked=0;history_cells=0;split_counts=Counter();seen=set()
 if ds=='cmapss':
  z=zipfile.ZipFile(raw/'CMAPSSData.zip')
  arrays={n:np.loadtxt(io.BytesIO(z.read(n))) for n in z.namelist() if n.endswith('.txt') and n.startswith(('train_','test_','RUL_'))}
  expected=set();short=[]
  for name,a in arrays.items():
   if name.startswith('RUL'):continue
   split,subset=name.removesuffix('.txt').split('_')
   for engine in np.unique(a[:,0]).astype(int):
    end=int(a[a[:,0]==engine][-1,1])
    if end<30:short.append((name,int(engine),end));continue
    ends=set(range(30,end+1,10))|{end} if split=='train' else {end}
    expected.update((name,int(engine),t) for t in ends)
  with candidate.open(encoding='utf-8') as f:
   for line in f:
    obj=json.loads(line);ref=obj['source_refs'][0];a=arrays[ref['file']];row=ref['row']-1;engine=int(a[row,0]);t=int(a[row,1])
    assert set(obj['input'])=={'subset','history_columns','history'}
    history=np.asarray(obj['input']['history'],dtype=float)
    assert history.shape==(30,25) and np.array_equal(history,a[row-29:row+1,1:])
    assert (a[row-29:row+1,0]==engine).all()
    if obj['split']=='train':label=int(a[a[:,0]==engine][-1,1])-t
    else:label=int(arrays['RUL_'+obj['input']['subset']+'.txt'][engine-1])
    assert obj['label']==label and obj['forecast_origin']==t and obj['history_start']==t-29
    assert obj['group_key']==f'{obj["input"]["subset"]}/{obj["split"]}/engine_{engine:03d}'
    key=(ref['file'],engine,t);assert key not in seen;seen.add(key)
    history_cells+=history.size;checked+=1;split_counts[obj['split']]+=1
  assert seen==expected and len(short)==17
  detail={'raw_train_engines':709,'raw_test_engines':707,'eligible_test_engines':690,'excluded_short_test_engines':short,'checks':['all input sensor/settings/cycle cells equal raw array slices','every label equals source-derived train RUL or official test RUL','every required stride/final/test endpoint exactly once','group and official split match source engine','all 17 short test engine exclusions independently reconstructed']}
 else:
  z=zipfile.ZipFile(raw/'CAMELS_GB_v1.zip');last_name=None;df=None
  attr_name=next(n for n in z.namelist() if n.endswith('/CAMELS_GB_topographic_attributes.csv'))
  attrs=pd.read_csv(io.BytesIO(z.read(attr_name)),dtype={'gauge_id':str},float_precision='round_trip')
  with candidate.open(encoding='utf-8') as f:
   for line in f:
    obj=json.loads(line);ref=obj['source_refs'][0];name=ref['file']
    if name!=last_name:
     df=pd.read_csv(io.BytesIO(z.read(name)),float_precision='round_trip');last_name=name
    row=ref['row']-1;origin_idx=row-1
    assert set(obj['input'])=={'catchment_attributes','forecast_origin_date','target_date','history_columns','history'}
    assert obj['label']==float(df.iloc[row]['discharge_spec']) and math.isfinite(obj['label']) and obj['label']>=0
    assert obj['target_time']==df.iloc[row]['date']==obj['input']['target_date']
    origin=date.fromisoformat(obj['input']['forecast_origin_date'])
    assert origin.day==calendar.monthrange(origin.year,origin.month)[1]
    assert date.fromisoformat(obj['target_time'])==origin+timedelta(days=1)
    expected=df.iloc[origin_idx-7:origin_idx][['date','precipitation','pet','temperature','discharge_spec']].values.tolist()
    assert obj['input']['history']==expected and len(expected)==7
    assert date.fromisoformat(expected[-1][0])+timedelta(days=1)==origin
    assert ref['history_start_row']==origin_idx-6 and ref['history_end_row']==origin_idx
    attr=attrs.iloc[obj['source_refs'][1]['row']-1]
    assert obj['entity_id']==str(attr.gauge_id)
    for source,target in {'area':'catchment_area_km2','gauge_elev':'gauge_elevation_m_asl','gauge_lat':'gauge_latitude_degrees','gauge_lon':'gauge_longitude_degrees'}.items():
     value=None if pd.isna(attr[source]) else float(attr[source]);assert obj['input']['catchment_attributes'][target]==value
    key=(name,row);assert key not in seen;seen.add(key)
    history_cells+=7*4;checked+=1;split_counts[obj['split']]+=1
    if checked%50000==0:print('SOURCE VALIDATION progress',ds,checked,flush=True)
  assert checked==meta['output_examples']
  detail={'checks':['every candidate label equals raw discharge_spec cell','every historical date/meteorological/flow value equals source row','all static attributes equal original topographic table','month-end origins, next-day labels and conservative availability lag verified on every record','no duplicate source target rows','only allowlisted input fields are present']}
 result=dict(status='passed',dataset_id=ds,records_checked=checked,history_numeric_cells_checked=history_cells,split_counts=dict(split_counts),candidate_sha256=sha(candidate),**detail)
 save(raw/'source_validation.json',result)
 meta['source_validation']=result;save(OUT/f'{ds}.meta.json',meta)
 print('SOURCE VALIDATION',ds,checked,history_cells,flush=True)

def validate_camels_population():
 """Reconstruct valid target dates with rolling masks rather than emission loops."""
 z=zipfile.ZipFile(RAW/'camels_gb'/'CAMELS_GB_v1.zip');counts=Counter();per=[]
 for name in sorted(n for n in z.namelist() if '/timeseries/' in n and n.endswith('.csv')):
  df=pd.read_csv(io.BytesIO(z.read(name)),float_precision='round_trip');dates=pd.to_datetime(df['date'])
  historical=df[['precipitation','pet','temperature','discharge_spec']].to_numpy(float)
  row_ok=pd.Series(np.isfinite(historical).all(axis=1)&(historical[:,3]>=0))
  # At target row j, required history is j-8,...,j-2.
  history_ok=row_ok.rolling(7).sum().shift(2).eq(7)
  target_ok=np.isfinite(df['discharge_spec'])&(df['discharge_spec']>=0)
  selected=dates.dt.day.eq(1)&(df.index>0)
  n=int((selected&target_ok&history_ok).sum())
  counts['eligible_windows']+=n;counts['target_dates_within_period']+=int(selected.sum())
  counts['missing_target_labels']+=int((selected&~target_ok).sum())
  counts['incomplete_histories_after_valid_label']+=int((selected&target_ok&~history_ok).sum())
  per.append({'file':name,'eligible_windows':n})
 meta=json.loads((OUT/'camels_gb.meta.json').read_text('utf-8'))
 assert counts['eligible_windows']==meta['output_examples']
 assert counts['missing_target_labels']==meta['exclusion_counts']['missing_or_nonfinite_label']
 assert counts['incomplete_histories_after_valid_label']==meta['exclusion_counts']['incomplete_history']
 report={'status':'passed','method':'Independent target-date-first rolling-validity masks; compare to emitter counts.','counts':dict(counts),'by_file':per}
 save(RAW/'camels_gb'/'population_validation.json',report)
 print('POPULATION VALIDATION',json.dumps(dict(counts)),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');parser.add_argument('--validate-only',action='store_true');parser.add_argument('--dataset',choices=['cmapss','camels_gb','all'],default='all');args=parser.parse_args()
 for name in ['cmapss','camels_gb'] if args.dataset=='all' else [args.dataset]:
  if args.download: download(name)
  if not args.validate_only:globals()[name]()
  validate_source(name)
  if name=='camels_gb':validate_camels_population()
