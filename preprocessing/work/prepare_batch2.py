import collections,hashlib,html,json,re
import numpy as np
from load_batch2 import *
from batch2_contracts import CONTRACTS
from build_general import clean,dumps,digest,profile,Union,save

NUMBER_WORDS=re.compile(r'\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion)\b',re.I)
MONEY_WORDS=re.compile(r'\b(?:prices?|priced|pricing|rates?|deposits?|dollars?|usd|fees?|payments?|specials?|discounts?|concessions?)\b|[$€£¥]',re.I)
def sanitize_listing(text):
    if text is None or pd.isna(text):return None
    text=html.unescape(str(text))
    text=re.sub(r'<[^>]*>',' ',text)
    text=re.sub(r'https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[link removed]',text)
    # Target-independent conservative removal: money clauses first, then ALL numbers.
    parts=re.split(r'(?<=[.!?;|])\s+|[\r\n]+',text)
    text=' '.join(p for p in parts if not MONEY_WORDS.search(p))
    text=re.sub(r'\d+(?:[,.]\s*\d+)*','[number removed]',text)
    text=NUMBER_WORDS.sub('[number removed]',text)
    text=re.sub(r'(?:\[number removed\][\s,-]*){2,}','[number removed] ',text)
    # Removing a digit can expose a previously hidden word boundary, e.g. FEE500.
    text=' '.join(p for p in re.split(r'(?<=[.!?;|])\s+|[\r\n]+',text) if not MONEY_WORDS.search(p))
    text=re.sub(r'\s+',' ',text).strip()
    return text or None

def prepare(i,raw):
    d=raw.copy();spec=CONTRACTS[i];notes=[];audit=[];exclusions=[];group_columns=[];extra_group_columns=[]
    flags=collections.defaultdict(set)
    def note(code,count,action,detail):notes.append(dict(code=code,count=int(count),action=action,detail=detail))
    def exclude(mask,reason):
        for idx in d.index[mask]:exclusions.append(dict(source_index=int(idx),file=str(d.at[idx,'_file']),row=int(d.at[idx,'_source_row']),reason=reason))
    def invalid_to_null(col,mask,reason):
        for idx in d.index[mask]:
            audit.append(dict(source_index=int(idx),file=str(d.at[idx,'_file']),row=int(d.at[idx,'_source_row']),field=col,original=clean(d.at[idx,col]),replacement=None,reason=reason));flags[idx].add(reason)
        d.loc[mask,col]=np.nan
    targets=[t[0] for t in spec['targets']]
    drop=[];keep=None
    if i==10:
        drop=['symboling','normalized_losses']
        words={'two':2,'three':3,'four':4,'five':5,'six':6,'eight':8,'twelve':12}
        for c in ['num_doors','num_cylinders']:
            assert set(d[c].dropna())<=set(words)
            d[c]=d[c].map(words)
        group_columns=['make','body_style','engine_type','engine_size','wheel_base','length','width','height']
        note('insurance_features_removed',2,'remove','symboling is explicitly price-related in the source; insurance-loss summary also excluded.')
    elif i==265:
        note('protein_identity_unavailable',len(d),'limit_claim','CASP.csv only has RMSD and F1-F9. No protein IDs can be recovered from these supplied files; exact-input grouping does not establish new-protein generalization.')
    elif i==560:
        d['date']=pd.to_datetime(d.date,format='%d/%m/%Y').dt.strftime('%Y-%m-%d');d['_time']=d.date+' '+d.hour.astype(str).str.zfill(2)+':00:00'
        group_columns=['date']
        closed=d.functioning_day.eq('No');assert (d.loc[closed,'rented_bike_count']==0).all()
        note('closed_hours_zero_demand',closed.sum(),'retain_operating_status','Closed hours are not missing labels; keep functioning_day to distinguish them.')
        note('source_date_format',len(d),'parse_day_first','Actual CSV is DD/MM/YYYY, contrary to generic web wording. Converted to ISO date.')
    elif i==374:
        drop=['rv1','rv2'];d['_time']=pd.to_datetime(d.date).dt.strftime('%Y-%m-%d %H:%M:%S');d['_day']=d['_time'].str[:10];group_columns=['_day']
        assert np.array_equal(d.rv1,d.rv2)
        note('random_columns',2,'remove','rv1 and rv2 are exactly equal random controls, not domain predictors.')
        note('single_house',1,'limit_claim','No claim of generalization to new houses; source weather interpolation prevents an unqualified online-forecast claim.')
    elif i==501:
        d['timestamp']=pd.to_datetime(d[['year','month','day','hour']]).dt.strftime('%Y-%m-%d %H:%M:%S');d['_time']=d.timestamp;d['_entity']=d.station
        drop=['No','year','month','day','hour','PM10','SO2','NO2','CO','O3'];group_columns=['timestamp']
        assert not d.duplicated(['station','timestamp']).any()
        note('missing_pm25_labels',d['PM2.5'].isna().sum(),'exclude_label_missing','Do not impute PM2.5 outcomes; retain rows with missing meteorological inputs as null.')
        note('pollutant_targets_removed',5,'remove','Only meteorology, time and station are inputs; other same-hour pollutant concentrations excluded.')
        note('station_time_grain',d.station.nunique(),'preserve','12 stations x 35064 hours; same timestamp grouped across stations, and station saved as entity_id for separate station-held-out protocols.')
    elif i==551:
        d['_time']=d['_year'].astype(str)+':'+d['_source_row'].astype(str).str.zfill(6)
        for idx in d.index[d.AH>100]:flags[idx].add('humidity_above_100_source_value')
        note('source_family_overlap',1,'same_family_as_uci294','Same power plant as first-batch CCPP; both datasets share dataset_family=turkish_power_plant. No exact cross-source timestamps available.')
        note('emissions_units',2,'use_mg_per_m3','Official variable table lists both CO and NOx in mg/m^3, not ppm.')
    elif i==440:
        assert d[RUNS].notna().all().all() and (d[RUNS]>0).all().all()
        d['mean_runtime_ms']=d[RUNS].mean(axis=1);drop=RUNS
        group_columns=[c for c in d if c not in RUNS+['_file','_source_row','mean_runtime_ms']]
        assert not d.duplicated(group_columns).any()
        note('four_repeat_measurements',len(d),'arithmetic_mean_target','One mean-runtime target per configuration. Original four times saved in target_observations, never included in prompt. No fabricated variance label.')
        note('readme_internal_count_conflict',len(d),'use_file_count','Actual CSV has 241600 configurations; a paragraph of original Readme incorrectly says 261400.')
    elif i==332:
        drop=['url','timedelta']+[c for c in d if c.startswith(('kw_','self_reference_','LDA_'))]
        date=d.url.str.extract(r'/(\d{4}/\d{2}/\d{2})/',expand=False);assert date.notna().all()
        d['publication_date']=pd.to_datetime(date,format='%Y/%m/%d').dt.strftime('%Y-%m-%d');d['_time']=d.publication_date;group_columns=['url']
        for c in ['n_unique_tokens','n_non_stop_words','n_non_stop_unique_tokens']:
            invalid_to_null(c,(d[c]<0)|(d[c]>1),'ratio_outside_0_1_to_null')
        note('potential_future_share_features',12,'remove','Nine kw_* and three self_reference_* share-derived features excluded because their as-of-time provenance is not verifiable.')
        note('full_corpus_topic_features',5,'remove','LDA scores omitted because fitted-corpus provenance is not established.')
        note('variable_exposure_horizon',len(d),'limit_claim','Shares measured at collection with varying article ages. This is not a fixed 7-day/30-day future popularity label.')
    elif i==555:
        exclude(d.category.ne('housing/rent/apartment'),'not_apartment_category')
        exclude(d.price_type.ne('Monthly'),'not_unambiguous_monthly_rent')
        exclude(d.currency.ne('USD'),'not_usd')
        exclude(d.square_feet.le(0)|d.square_feet.isna(),'invalid_floor_area')
        for c in ['title','body']:
            out=d[c].map(sanitize_listing)
            for idx in d.index[d[c].fillna('')!=out.fillna('')]:
                audit.append(dict(source_index=int(idx),file=str(d.at[idx,'_file']),row=int(d.at[idx,'_source_row']),field=c,reason='target_independent_text_redaction',original_sha256=hashlib.sha256(str(d.at[idx,c]).encode()).hexdigest(),cleaned_sha256=hashlib.sha256(str(out.at[idx]).encode()).hexdigest(),original_characters=len(str(d.at[idx,c])),cleaned_characters=0 if pd.isna(out.at[idx]) else len(out.at[idx])))
            d[c]=out
        keep=['title','body','amenities','bathrooms','bedrooms','pets_allowed','square_feet','cityname','state','latitude','longitude']
        # Also sanitize free-text amenities so no numeric/currency bypass enters the prompt.
        d['amenities']=d.amenities.map(sanitize_listing)
        d['_time']=pd.to_datetime(d.time,unit='s',utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        # Do not group every missing address together. Available address/location is a conservative proxy.
        d['_property_proxy']=[('address:'+str(a).strip().casefold()+'|'+str(city)+'|'+str(state)) if pd.notna(a) else ('geo:'+str(lat)+'|'+str(lon)+'|'+str(area)+'|'+str(bed)) if pd.notna(lat) and pd.notna(lon) else 'id:'+str(id_) for a,city,state,lat,lon,area,bed,id_ in zip(d.address,d.cityname,d.state,d.latitude,d.longitude,d.square_feet,d.bedrooms,d.id)]
        d['_clean_text_key']=[digest([t,b]) if pd.notna(b) and len(b)>50 else 'id:'+str(id_) for t,b,id_ in zip(d.title,d.body,d.id)]
        group_columns=['id'];extra_group_columns=[['_property_proxy'],['_clean_text_key']]
        note('source_100k_actual_count',len(d),'use_larger_file_only','100K release contains 99492 rows. 10K file is archived but not concatenated.')
        note('numeric_text_redaction',len(audit),'conservative_label_independent_redaction','Removed financial clauses plus all digit sequences and spelled-out number words from title/body, using no target labels. Numeric property details remain in structured fields. Raw text preserved in archive.')
        note('price_and_identifiers_removed',1,'allowlist_features','price_display, address, listing ID, source and pricing/currency fields do not enter input; category/currency/period enforced by selection.')
        note('listing_identity_limit',d.address.isna().sum(),'preserve_proxy_grouping','Exact listing IDs, available address/geographic proxies and identical cleaned descriptions are unioned; this is not verified building identity and may over-group.')
    elif i==162:
        group_columns=['X','Y'];note('zero_and_skewed_target',(d.area==0).sum(),'retain_original_hectares','Zero burned areas retained. No log1p is applied, and large legitimate fires are not removed as outliers.')
    elif i==925:
        # Mean over available rounds per facial measurement; no cross-person fitting or imputation.
        newcols=[]
        for c in THERMAL:
            stem=c[:-1];cols=[stem+str(k) for k in range(1,5)]
            if c=='T_LC1':cols[-1]='T_LC14' # Typo present in both original CSV headers.
            assert set(cols)<=set(d)
            dest=stem.rstrip('_')+'_mean';d[dest]=d[cols].mean(axis=1,skipna=True);newcols.append(dest)
        keep=newcols+['device','Gender','Age','Ethnicity','T_atm','Humidity','Distance']
        group_columns=['SubjectID'];d['_entity']=d.SubjectID
        assert (d.groupby('SubjectID').aveOralM.nunique()<=1).all()
        assert not d.duplicated(['SubjectID','device']).any()
        note('original_release_scope',len(d),'use_both_devices','Original release: FLIR 1020 + ICI 1009 device records from 1026 subjects, not 2029 independent people. This extends the UCI 1020-row subset.')
        note('facial_round_aggregation',len(newcols),'within_record_available_mean','26 facial temperature descriptors plus blackbody offset averaged over available rounds. All-round-missing remains null. Both oral thermometer readings, ID, Time, Date and Cosmetics excluded.')
        note('oral_targets_no_disagreement',d.SubjectID.nunique(),'patient_grouping','Monitor-mode labels match for every subject measured on both devices. Other oral target never enters input.')
    for c in [c for c in d if pd.api.types.is_string_dtype(d[c])]:
        d[c]=d[c].str.strip()
    excluded_idx={e['source_index'] for e in exclusions}
    features=keep if keep is not None else [c for c in d if not c.startswith('_') and c not in targets+drop]
    for c in features:
        if pd.api.types.is_numeric_dtype(d[c]):invalid_to_null(c,d[c].notna()&~np.isfinite(d[c]),'nonfinite_feature_to_null')
    # Source-column allowlist/exclusions are explicit even for derived features.
    forbidden=[c for c in raw if not c.startswith('_') and c not in features]
    return d,features,targets,group_columns,extra_group_columns,flags,notes,audit,exclusions,forbidden
