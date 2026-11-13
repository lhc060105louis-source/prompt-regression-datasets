import collections, csv, gzip, hashlib, json, math, pathlib, shutil, sys
from load_general import ROOT, DEST, pd, frame, located
from general_specs import SPECS, STUDENT_MAPS, TEMPLATE
import numpy as np

VERSION='1.0.0'
def clean(value):
    if isinstance(value,dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [clean(v) for v in value]
    if value is None or value is pd.NA: return None
    if isinstance(value,np.generic): value=value.item()
    if isinstance(value,float):
        if not math.isfinite(value): return None
        return int(value) if value.is_integer() else value
    return value
def dumps(v): return json.dumps(clean(v),ensure_ascii=False,allow_nan=False,separators=(',',':'))
def digest(v): return hashlib.sha256(dumps(v).encode()).hexdigest()
def save(path,obj): path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(clean(obj),ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')

def profile(d):
    d=d.drop(columns=[c for c in d if c.startswith('_')])
    result={'rows':len(d),'columns':len(d.columns),'exact_duplicate_rows':int(d.duplicated().sum()),'column_profiles':{}}
    for c in d:
        s=d[c];p={'dtype':str(s.dtype),'missing_count':int(s.isna().sum()),'missing_rate':float(s.isna().mean()),'distinct_nonmissing':int(s.nunique())}
        if pd.api.types.is_numeric_dtype(s):
            p.update({'nonfinite_count':int((~np.isfinite(s.astype(float)) & s.notna()).sum()),'zero_count':int((s==0).sum()),'negative_count':int((s<0).sum()),'quantiles':s.quantile([0,.01,.25,.5,.75,.99,1]).to_dict()})
        else:p['top_values']=s.value_counts(dropna=False).head(12).to_dict()
        result['column_profiles'][c]=p
    return result

class Union:
    def __init__(self,n):self.parents=list(range(n))
    def root(self,a):
        while self.parents[a]!=a:
            self.parents[a]=self.parents[self.parents[a]];a=self.parents[a]
        return a
    def join(self,a,b):
        a,b=self.root(a),self.root(b)
        if a!=b:self.parents[max(a,b)]=min(a,b)

def build_one(i,spec):
    d=frame(i).reset_index(drop=True)
    raw_profile=profile(d)
    folder=DEST/'datasets'/f'uci_{i}_{spec["key"]}'
    folder.mkdir(parents=True,exist_ok=True)
    source=json.loads((DEST/'raw'/f'uci_{i}'/'source_manifest.json').read_text(encoding='utf-8'))
    api=json.loads((DEST/'raw'/f'uci_{i}'/'uci_metadata.json').read_text(encoding='utf-8'))['data']
    findings=[];changes=[];flags=collections.defaultdict(list)
    def finding(code,count,action,detail,severity='medium'):
        findings.append(dict(code=code,count=int(count),action=action,detail=detail,severity=severity))
    def fix(mask,col,new,reason,flag=True):
        for idx in d.index[mask]:
            changes.append({'source_row':int(d.at[idx,'_source_row']),'source_file':d.at[idx,'_file'] if '_file' in d else spec['source_file'],'field':col,'original':clean(d.at[idx,col]),'replacement':clean(new),'reason':reason})
            if flag: flags[idx].append(reason)
        d.loc[mask,col]=new
    # Trim strings while preserving meaningful literal categories such as holiday='None'.
    for c in [c for c in d if pd.api.types.is_string_dtype(d[c])]:
        if c.startswith('_'):continue
        stripped=d[c].str.strip()
        for idx in d.index[d[c].notna() & (stripped!=d[c])]:
            changes.append({'source_row':int(d.at[idx,'_source_row']),'field':c,'original':d.at[idx,c],'replacement':stripped.at[idx],'reason':'trim_surrounding_whitespace'})
        d[c]=stripped
    if i==1:
        fix(d.height_scaled<=0,'height_scaled',np.nan,'nonpositive_shell_height_to_null')
        m=d.height_scaled>d.length_scaled
        for idx in d.index[m]:flags[idx].append('height_exceeds_length_review')
        finding('source_scaled_features',len(d),'retain_source_scale','Original documentation states continuous features were scaled; prompts do not label them as unscaled mm/g.')
        finding('nonpositive_height',len([x for x in changes if x['reason']=='nonpositive_shell_height_to_null']),'replace_feature_with_null','Physical height zero is invalid; preserve label and raw source.')
        finding('height_exceeds_length',m.sum(),'retain_and_flag','Potential outliers are not silently clipped or deleted.')
        d['sex']=d['sex'].map({'M':'male','F':'female','I':'infant'})
        assert d.sex.notna().all()
    if i==9:
        finding('missing_horsepower',d.horsepower.isna().sum(),'retain_as_null','Six missing horsepower values; no all-data mean imputation.')
    if i==294:
        sheets=pd.read_excel(located(i,'Folds5x2_pp.xlsx'),sheet_name=None)
        signatures=[sorted(pd.util.hash_pandas_object(x,index=False).tolist()) for x in sheets.values()]
        assert all(x==signatures[0] for x in signatures[1:]),'Power-plant sheets are not identical multisets'
        finding('reshuffled_workbook_copies',len(sheets)-1,'use_only_first_sheet',f'{len(sheets)} sheets each contain the same {len(d)} records in different orders.')
        m=d.RH>100
        for idx in d.index[m]:flags[idx].append('relative_humidity_above_100_retained')
        finding('relative_humidity_above_100',m.sum(),'retain_and_flag','Small exceedance may reflect measurement/rounding; not automatically clipped.')
    compositions=None
    if i==464:
        u=pd.read_csv(located(i,'unique_m.csv'))
        assert len(u)==len(d) and np.array_equal(u.critical_temp.to_numpy(),d.critical_temp.to_numpy())
        element_cols=[c for c in u if c not in ['critical_temp','material']]
        amounts=u[element_cols].to_numpy(dtype=float)
        assert (amounts>=0).all() and (amounts.sum(axis=1)>0).all()
        # Group equivalent empirical compositions, retaining 12 decimal digits of fractions.
        fractions=amounts/amounts.sum(axis=1,keepdims=True)
        compositions=[digest(np.round(row,12).tolist()) for row in fractions]
        finding('aligned_composition_table',len(u),'use_for_grouping_only','Verified exact rowwise target alignment; unique_m.csv is not appended as independent samples. Composition fractions rounded to 12 decimals for grouping.')
    if i==320:
        same=d.duplicated(spec['group']+['subject']).sum()
        finding('student_identity_proxy_collision',same,'conservatively_group','Official 13-field matching key is not unique within a course. It is a leakage-control proxy, not an exact student identity.')
        finding('previous_grades_and_absences',len(d),'remove_features','G1/G2 and cumulative absences removed. Survey timing is not known, so this is not advertised as a verified start-of-year forecast.')
    if i==189:
        finding('repeated_patients',d['subject#'].nunique(),'group_by_patient','All recordings and both outcomes for a patient share a split group.')
        finding('interpolated_labels',len(d),'retain_and_disclose','Original names file explicitly describes both UPDRS scores as linearly interpolated, not independently observed at every voice recording.')
    if i==597:
        fix(d.department=='sweing','department','sewing','correct_documented_department_typo',flag=False)
        d['date']=pd.to_datetime(d.date,format='%m/%d/%Y').dt.strftime('%Y-%m-%d')
        m=d.actual_productivity>1
        for idx in d.index[m]:flags[idx].append('productivity_above_one_source_value')
        finding('target_exceeds_documented_0_1_range',m.sum(),'retain_and_flag','Observed productivity can exceed 1; do not clip labels or constrain output to [0,1].')
        finding('missing_wip',d.wip.isna().sum(),'retain_as_null','Missing WIP is confined to finishing department; do not replace with zero.')
        finding('ambiguous_feature_timing',len(d),'define_retrospective_task','Remove incentive and idle variables. Remaining production measures are used for conditional estimation, not claimed available pre-shift.')
    if i==275:
        assert (d.casual+d.registered==d.cnt).all()
        finding('direct_target_components',len(d),'remove_casual_and_registered','Verified casual + registered == cnt on every row.')
        finding('website_row_count_mismatch',len(d),'use_actual_file_count',f'Actual hour.csv has {len(d)} rows; API reports {api["num_instances"]}. Daily aggregates are excluded.')
        finding('normalization_and_season_documentation_conflict',len(d),'retain_normalized_values_and_drop_season','Website and archive disagree on temperature normalization and season code descriptions. No inverse conversion is performed; season is dropped as redundant to date.')
        for col in ['holiday','workingday']:d[col]=d[col].map({0:'no',1:'yes'})
    if i==492:
        literal_none=(d.holiday=='None').sum()
        d['holiday']=d.holiday.replace({'None':'no holiday'})
        finding('literal_None_is_not_missing',literal_none,'decode_as_no_holiday','Read CSV with keep_default_na=False; None is a valid no-holiday category.')
        fix(d.temp<=0,'temp',np.nan,'nonpositive_kelvin_to_null')
        finding('invalid_kelvin',sum(x['reason']=='nonpositive_kelvin_to_null' for x in changes),'replace_feature_with_null','Zero Kelvin is invalid ambient temperature, not a missing target.')
        m=d.rain_1h>1000
        for idx in d.index[m]:flags[idx].append('extreme_rainfall_gt_1000_mm_review')
        finding('extreme_rainfall',m.sum(),'retain_and_flag','One reported hourly rainfall is 9831.3 mm; flagged for review, not silently winsorized.')
        finding('multiple_rows_per_timestamp',len(d)-d.date_time.nunique(),'retain_distinct_weather_rows_and_group','Traffic labels agree within each timestamp, but some weather values differ; no arbitrary weather aggregation.')
    if i==186:
        finding('red_white_subsets',len(d),'combine_with_wine_type',f'Red={int((d.wine_type=="red").sum())}; white={int((d.wine_type=="white").sum())}. Treat as one source family.')

    target_cols=[t[0] for t in spec['targets']]
    features=[c for c in d if not c.startswith('_') and c not in target_cols+spec['exclude']]
    # Student task is explicit in task ID AND input. Both courses remain one family.
    candidates=[];invalid=[];union=Union(len(d));seen_semantic={};seen_input={}
    for idx,row in d.iterrows():
        if compositions is not None:semantic=['composition',compositions[idx]]
        elif spec['group']:semantic=[clean(row[c]) for c in spec['group']]
        else:semantic=['source_record',idx]
        sh=digest(semantic)
        if sh in seen_semantic:union.join(idx,seen_semantic[sh])
        else:seen_semantic[sh]=idx
        inp={c:clean(row[c]) for c in features}
        if i==320:
            for c,mapping in STUDENT_MAPS.items():
                if c in inp:
                    if inp[c] not in mapping:raise ValueError(f'Unknown category {c}: {inp[c]}')
                    inp[c]=mapping[inp[c]]
        ih=digest(inp)
        if ih in seen_input:union.join(idx,seen_input[ih])
        else:seen_input[ih]=idx
        file=str(row.get('_file',spec['source_file']))
        ref={'file':file,'row':int(row['_source_row'])}
        for col,name,unit,kind in spec['targets']:
            label=clean(row[col])
            if label is None or not isinstance(label,(int,float)) or isinstance(label,bool):
                invalid.append(dict(source=ref,target=col,reason='missing_or_nonfinite_numeric_label'));continue
            task_id=f'uci_{i}/{name}'
            if i==320:task_id+='/'+row['subject']
            prompt=TEMPLATE.format(task=spec['task'],target_name=name,target_unit=unit,context=spec['context'],input_json=dumps(inp))
            r={'schema_version':VERSION,'dataset_id':f'uci_{i}','dataset_name':source['name'],'dataset_family':'turkish_power_plant' if i==294 else f'uci_{i}', 'task_id':task_id,'prompt_template_id':f'uci_{i}/{name}/v1','prompt':prompt,'label':label,'target_name':name,'target_unit':unit,'target_type':kind,'target_transform':'none_applied; source_negative_log' if i==504 else 'none_applied','input':inp,'source_refs':[ref],'duplicate_count':1,'quality_flags':sorted(set(flags[idx])),'split':'unassigned','_idx':idx,'_input_hash':ih}
            if i in [275,597,492]:r['time_key']=str(row[{275:'dteday',597:'date',492:'date_time'}[i]])
            if i==477:r['time_key']=float(row['transaction_date'])
            candidates.append(r)
    # Collapse identical task/input/label pairs; preserve all their source references.
    merged={};input_labels=collections.defaultdict(set)
    for r in candidates:
        input_labels[(r['task_id'],r['_input_hash'])].add(r['label'])
        key=(r['task_id'],r['_input_hash'],r['label'])
        if key in merged:
            existing=merged[key];existing['source_refs']+=r['source_refs'];existing['duplicate_count']+=1
            existing['quality_flags']=sorted(set(existing['quality_flags']+r['quality_flags']))
        else:merged[key]=r
    repeated_different=sum(len(v)>1 for v in input_labels.values())
    finding('identical_input_different_labels',repeated_different,'retain_labels_and_group','Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted.')
    finding('duplicate_task_examples',len(candidates)-len(merged),'collapse_preserve_source_refs','Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous.')
    records=[]
    for key,r in merged.items():
        idx=r.pop('_idx');ih=r.pop('_input_hash')
        r['group_id']=f'uci_{i}/g{union.root(idx):06d}'
        r['input_hash']=ih
        r['sample_id']=f'uci_{i}/'+digest([r['task_id'],ih,r['label']])[:24]
        records.append(r)
    stats={'uci_id':i,'name':source['name'],'raw_rows_selected':len(d),'raw_exact_duplicate_rows':raw_profile['exact_duplicate_rows'],'candidate_task_examples':len(candidates),'invalid_label_examples':len(invalid),'output_examples':len(records),'collapsed_duplicate_examples':len(candidates)-len(records),'task_count':len({r['task_id'] for r in records}),'split_groups':len({r['group_id'] for r in records}),'input_field_count':len(features),'examples_with_null_input':sum(any(v is None for v in r['input'].values()) for r in records),'flagged_examples':sum(bool(r['quality_flags']) for r in records),'identical_input_different_label_groups':repeated_different,'source_url':source['source_url'],'path':str((folder/'data.jsonl').relative_to(DEST)).replace('\\','/')}
    with (folder/'data.jsonl').open('w',encoding='utf-8',newline='\n') as f:
        for r in records:f.write(dumps(r)+'\n')
    task_summary={}
    for tid in sorted({r['task_id'] for r in records}):
        subset=[r for r in records if r['task_id']==tid];labels=pd.Series([r['label'] for r in subset]);lengths=pd.Series([len(r['prompt']) for r in subset])
        task_summary[tid]={'examples':len(subset),'label_quantiles':labels.quantile([0,.01,.5,.99,1]).to_dict(),'zero_labels':int((labels==0).sum()),'prompt_characters':{'min':int(lengths.min()),'median':float(lengths.median()),'max':int(lengths.max())}}
    meta={'version':VERSION,'stats':stats,'contract':spec,'input_fields':features,'excluded_input_columns':target_cols+spec['exclude'],'grouping_rule':spec['group_note']+' Identical prepared inputs are additionally unioned to prevent duplicate-input leakage.','deduplication_policy':'One example per identical task/input/label; source_refs and duplicate_count preserve multiplicity. Different labels retained.','missing_policy':'null; no statistical imputation; two nonpositive Abalone heights and ten nonpositive Metro Kelvin temperatures are converted to null in their respective sources.','split_policy':'UNASSIGNED: choose dataset-family holdouts and appropriate grouped/chronological splits before training. group_id prevents known overlap but does not prove independence.','license':{'name':'CC BY 4.0, as stated by the UCI dataset page','url':'https://creativecommons.org/licenses/by/4.0/','source_url':source['source_url'],'verified_date':'2026-11-09'},'source_archive_sha256':source['archive_sha256'],'dataset_doi':api.get('dataset_doi'),'creators':api.get('creators'),'citation_paper':api.get('intro_paper'),'task_statistics':task_summary,'quality_findings':findings,'source_values_policy':'No learned feature scaling, target normalization, truncation, oversampling or label clipping; unknown physical units explicitly identified.'}
    save(folder/'metadata.json',meta)
    save(folder/'quality_profile_raw.json',raw_profile)
    save(folder/'quality_profile_prepared_features.json',profile(d[features+target_cols]))
    save(folder/'changes.json',changes)
    save(folder/'invalid_labels.json',invalid)
    save(folder/'prompt_templates.json',{'version':VERSION,'language':'English','template':TEMPLATE,'task':spec['task'],'context':spec['context'],'targets':[dict(column=t[0],name=t[1],unit=t[2],type=t[3]) for t in spec['targets']]})
    with (folder/'preview.jsonl').open('w',encoding='utf-8') as f:
        for tid in task_summary:
            f.write(dumps(next(r for r in records if r['task_id']==tid))+'\n')
    return stats,meta,records

def main():
    (DEST/'reports').mkdir(exist_ok=True)
    (DEST/'combined').mkdir(exist_ok=True)
    summaries=[];metas=[]
    # gzip mtime=0 ensures deterministic compressed output.
    with (DEST/'combined/all.jsonl.gz').open('wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as combined:
            for i,spec in SPECS.items():
                stats,meta,records=build_one(i,spec)
                for r in records:combined.write((dumps(r)+'\n').encode('utf-8'))
                summaries.append(stats);metas.append(meta)
                print(dumps(stats),flush=True)
    with (DEST/'reports/dataset_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(summaries[0]));writer.writeheader();writer.writerows(summaries)
    manifest={'version':VERSION,'created_date':'2026-11-09','datasets':summaries,'dataset_count':len(summaries),'task_count':sum(x['task_count'] for x in summaries),'total_selected_source_rows':sum(x['raw_rows_selected'] for x in summaries),'total_examples':sum(x['output_examples'] for x in summaries),'collapsed_duplicate_examples':sum(x['collapsed_duplicate_examples'] for x in summaries),'invalid_label_examples':sum(x['invalid_label_examples'] for x in summaries),'combined_path':'combined/all.jsonl.gz','training_performed':False,'splits_assigned':False,'prompt_language':'English','local_only':True}
    save(DEST/'manifest.json',manifest)
    lines=['# 第一批通用回归数据构建与质量报告','',f"已下载并处理 {manifest['dataset_count']} 个 UCI 来源，得到 {manifest['task_count']} 个回归任务、{manifest['total_examples']:,} 条统一记录。未训练，未上传外部实验追踪服务。",'',f"选定原始数据表共 {manifest['total_selected_source_rows']:,} 行；展开多目标后，合并了 {manifest['collapsed_duplicate_examples']:,} 条完全相同的任务/输入/标签记录。无效标签排除数：{manifest['invalid_label_examples']}。重复来源行保存在每条记录的 source_refs 与 duplicate_count 中。",'','| UCI | 数据集 | 选定源行数 | 任务数 | 最终记录 | 合并重复记录 | 含缺失输入记录 | 分组数 |','|---|---|---:|---:|---:|---:|---:|---:|']
    for x in summaries:lines.append(f"| {x['uci_id']} | {x['name']} | {x['raw_rows_selected']:,} | {x['task_count']} | {x['output_examples']:,} | {x['collapsed_duplicate_examples']:,} | {x['examples_with_null_input']:,} | {x['split_groups']:,} |")
    lines+=['','## 关键处理和限制','','- 保留官方压缩包、解压文件、API元数据和SHA-256校验和；CCPP只读取第一个工作表，已验证其余4个是相同记录的不同排序。','- 葡萄酒合并红白子集并加入类型；学生保留两门课程；供暖/制冷和两种UPDRS分别展开为标量回归任务。','- 无任何目标插补、裁剪、标准化或对数再变换。QSAR目标保留原始负对数尺度。缺失特征以null表达。','- 合并完全相同的任务/输入/标签；同输入不同标签保留，分在同一个group_id。重复样本可能是真实重复测量，因此保留来源和multiplicity以便恢复权重。','- Metro的字符串None表示非节日，不能当缺失；10条0K温度转为null；1条9831.3毫米降雨保留但标记，使用严格质量子集时可排除带quality_flags的记录。','- Abalone的2条零高度转为null；存储值按原尺度保留。没有把缩放数值误标为原始毫米/克。','- 服装生产率37条标签超过1，保留并标记；506条WIP缺失集中在finishing部门，没有填成0。','- Parkinsons标签是线性插值评分；所有声音记录按42名患者分组。学生使用官方13字段匹配代理，同一代理可能对应多个记录，不能声称已恢复精确学生ID。','- 时间任务定义为给定同期观测条件的估计；没有宣称使用当时未知的实测天气进行未来预测。学生去掉G1/G2和累计缺勤，但调查时间未充分记录，不能宣称严格学年初预测。','- group_id只控制已知关联；未来还需先做dataset_family级留出，再对训练池采用时间/分组划分。当前split均为unassigned；不要直接随机拆开合并文件。','- Superconductivity prompt较长，未截断。记录字符长度而非未经测量的token数；训练前应使用实际Jev tokenizer核查上下文长度。','','## 逐数据集检查结果','']
    for meta in metas:
        x=meta['stats'];lines+=[f"### {x['uci_id']} — {x['name']}",'',f"[官方来源]({x['source_url']})；建议划分：{meta['contract']['split']}。",'']
        for finding in meta['quality_findings']:lines.append(f"- `{finding['code']}`：{finding['count']}；{finding['detail']} 处理：{finding['action']}。")
        lines.append('')
    lines+=['## 训练前实验追踪预留','','本次不启动训练。后续训练前应固定数据版本、分组/时间划分、prompt版本、采样比例与随机种子；记录每任务training/validation同定义指标及step/epoch。优先本地CSV/JSONL或TensorBoard；W&B上传须单独授权。小验证集可全量，大数据集可先固定抽样并记录样本范围与评估成本，在关键checkpoint做全量评估。未执行的指标不会因日志工具自动补算。']
    report='\n'.join(lines)+'\n'
    (DEST/'reports/质量检查报告.md').write_text(report,encoding='utf-8')
    (ROOT/'outputs/general_dataset_quality_report.md').write_text(report,encoding='utf-8')
    save(DEST/'schema.json',{'format':'UTF-8 JSON Lines','required':['sample_id','dataset_id','dataset_family','task_id','prompt','label','input','source_refs','group_id','split'],'label':'finite JSON number, never string; scalar target','prompt':'English task-specific context + input JSON; excludes labels and provenance','input':'original-scale typed feature object; null allowed; no statistical imputation','source_refs':'one or more original file/1-based data row references; excludes header row','duplicate_count':'number of identical task/input/label source occurrences collapsed','group_id':'known-dependence grouping key, dataset-scoped; does not replace chronological splitting','split':'unassigned in this release','quality_flags':'review flags for preserved source anomalies or explicitly replaced measurements; no flag is not a guarantee of clean data','target_transform':'no additional transform applied; QSAR source labels already transformed'})
    readme=f'''# 构造general数据集

第一批18个UCI数据集；{manifest['task_count']}个任务；{manifest['total_examples']:,}条统一prompt+数值标签记录。版本{VERSION}。

未训练；未划分train/validation/test；未进行任何外部实验日志上传。

## 文件布局

- `datasets/uci_ID_NAME/data.jsonl`：18份可直接读取的统一数据，每行一个JSON对象。
- `combined/all.jsonl.gz`：相同记录的合并压缩版，使用gzip读取；不要与分数据集文件重复混合。
- `datasets/.../metadata.json`：任务、单位、排除字段、分组方式、统计和来源。
- `datasets/.../prompt_templates.json`：固定英文模板。`preview.jsonl`包含每任务一个示例。
- `datasets/.../quality_profile_*.json`：逐字段类型、缺失、分位数、重复和分布检查。
- `datasets/.../changes.json`：具体修改审计；`invalid_labels.json`：无效标签排除记录。
- `raw/`：下载的原始压缩包、解压文件、原始说明、API元数据和下载清单。
- `reports/质量检查报告.md`、`reports/dataset_summary.csv`：检查结论和汇总。
- `manifest.json`、`schema.json`、`checksums.json`：版本、格式和校验信息。
- `scripts/`：可复现构建和验证脚本。

## 使用约定

模型输入只读取`prompt`，监督标签只读取数值型`label`。`input`便于检查和改模板；source_refs、group_id、quality_flags等不是模型输入。所有字段和标签保留来源数值尺度；不虚构目标物理单位。模板没有要求生成推理文本，也没有构造不存在的不确定性标签。

每条记录保存原始文件和数据行号，重复记录的所有来源合并保存。quality_flags非空的记录仍保留，可据质量报告选择严格子集，但不要盲目删掉所有缺失特征记录。

先决定哪些完整数据家族作为未见任务评估，再按metadata中的分组/时间建议划分。多目标同一来源、同患者、同材料、同小时不可跨集合。标签归一化和填补参数只能从以后划定的训练部分拟合。

当前日期、单位与分类编码依原始文档解释。README或metadata中明确标记的缺陷仍需在研究结论中披露。原始文件不因本次清洗而改变。

## 本地复现

脚本依赖Python、pandas、numpy、openpyxl、xlrd。本次Excel读取组件位于项目`work/vendor`，其余版本见`build_environment.json`。在项目根目录运行`python work/build_general.py`重建，运行`python work/validate_general.py`验证。scripts中保存同版源代码，迁移后需保留项目布局或相应调整根目录常量。下载脚本依赖先前候选CSV，已在scripts中存档。
'''
    (DEST/'README.md').write_text(readme,encoding='utf-8')
    scriptdir=DEST/'scripts';scriptdir.mkdir(exist_ok=True)
    for name in ['download_general.py','load_general.py','general_specs.py','build_general.py','validate_general.py']:
        p=ROOT/'work'/name
        if p.exists():shutil.copy2(p,scriptdir/name)
    shutil.copy2(ROOT/'outputs/uci_regression_candidates.csv',scriptdir/'uci_regression_candidates.csv')
    import importlib.metadata
    environment={'python':sys.version,'packages':{x:importlib.metadata.version(x) for x in ['pandas','numpy','openpyxl','xlrd']},'training_executed':False}
    save(DEST/'build_environment.json',environment)
    (scriptdir/'requirements.txt').write_text('\n'.join(f'{k}=={v}' for k,v in environment['packages'].items())+'\n',encoding='utf-8')
    checksums={str(p.relative_to(DEST)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DEST.rglob('*')) if p.is_file() and p.name not in ['checksums.json']}
    save(DEST/'checksums.json',checksums)
    print('TOTAL '+dumps(manifest),flush=True)

if __name__=='__main__':main()
