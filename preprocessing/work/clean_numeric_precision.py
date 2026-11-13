"""Apply audited precision v2.1.0 after the original two-batch construction."""
import collections,copy,gc,gzip,json,pathlib,shutil,sys
from numeric_precision import *
sys.path.insert(0,str(ROOT/'work/vendor'))
import pandas as pd
from build_general import profile

HISTORY=DEST/'history/v2.0.0_before_precision'
STAGE=ROOT/'work/precision_v2_1_stage'
DATE='2026-11-13'

def merge(records):
    result={}
    for r in records:
        key=r['sample_id']
        if key not in result:result[key]=r;continue
        first=result[key]
        assert first['group_id']==r['group_id']
        assert all(first[k]==v for k,v in r.items() if k not in ['source_refs','duplicate_count','quality_flags'])
        first['source_refs']+=r['source_refs'];first['duplicate_count']+=r['duplicate_count']
        first['quality_flags']=sorted(set(first['quality_flags'])|set(r['quality_flags']))
    return result.values()

def stage_dataset(ds,scan):
    rel=pathlib.Path(ds['path']);folder=DEST/rel.parent;dst=STAGE/rel.parent;dst.mkdir(parents=True,exist_ok=True)
    meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    if not scan['changed_records']:
        meta['version']='2.1.0';meta['numeric_precision']=POLICY
        meta['prepared_profile_scope']='Original prepared table before task deduplication/label exclusions, retained from v2.0.0.'
        save(dst/'metadata.json',meta)
        return dict(ds),dict(uci_id=ds['uci_id'],status='passed',examples_verified=ds['output_examples'],changed_records=0,data_sha256=sha(DEST/rel))
    auditpath=dst/'numeric_precision_changes.jsonl.gz';audit=[]
    def converted():
        with (DEST/rel).open(encoding='utf-8') as f,gzip.open(auditpath,'wt',encoding='utf-8') as log:
            for line in f:
                r=json.loads(line);n=convert(r);changes=numeric_changes(r,n)
                if changes:log.write(dumps({'old_sample_id':r['sample_id'],'new_sample_id':n['sample_id'],'source_refs':r['source_refs'],'changes':[{'field':c,'before':a,'after':b} for c,a,b in changes]})+'\n')
                yield n
    records=merge(converted()) if scan['new_duplicate_records'] else converted()
    labels=collections.defaultdict(list);lengths=collections.defaultdict(list);first={};groups=set();nulls=0;flagged=0;n=0;refs=0
    featurecols={c:[] for c in meta['input_fields']};targetcol=meta['contract']['targets'][0][0];targetvalues=[]
    seen=set();input_groups={};input_labels=collections.defaultdict(set)
    with (dst/'data.jsonl').open('w',encoding='utf-8',newline='\n') as f:
        for r in records:
            assert r['sample_id'] not in seen;seen.add(r['sample_id'])
            assert input_groups.setdefault(r['input_hash'],r['group_id'])==r['group_id']
            input_labels[(r['task_id'],r['input_hash'])].add(r['label'])
            f.write(dumps(r)+'\n');n+=1;refs+=len(r['source_refs']);groups.add(r['group_id'])
            nulls+=any(v is None for v in r['input'].values());flagged+=bool(r['quality_flags'])
            labels[r['task_id']].append(r['label']);lengths[r['task_id']].append(len(r['prompt']));first.setdefault(r['task_id'],r)
            for c,v in r['input'].items():featurecols[c].append(v)
            targetvalues.append(r['label'])
    assert n==ds['output_examples']-scan['new_duplicate_records'] and refs==ds['candidate_task_examples']
    stats=dict(ds,output_examples=n,collapsed_duplicate_examples=ds['collapsed_duplicate_examples']+scan['new_duplicate_records'],split_groups=len(groups),examples_with_null_input=nulls,flagged_examples=flagged,identical_input_different_label_groups=sum(len(v)>1 for v in input_labels.values()))
    del input_labels,input_groups,seen,records
    meta['version']='2.1.0';meta['stats']=stats;meta['numeric_precision']=POLICY
    meta['prepared_profile_scope']='Final normalized, eligible, deduplicated output records. Raw profile retains the original source-table scope.'
    meta['source_values_policy']+=' Prepared numeric values now follow significant_digits_12_v1; exact originals remain in raw and the versioned history.'
    meta['task_statistics']={tid:{'examples':len(y),'label_quantiles':pd.Series(y).quantile([0,.01,.5,.99,1]).to_dict(),'zero_labels':sum(v==0 for v in y),'prompt_characters':{'min':min(lengths[tid]),'median':float(pd.Series(lengths[tid]).median()),'max':max(lengths[tid])}} for tid,y in labels.items()}
    meta['task_statistics']=normalize(meta['task_statistics'])
    for finding in meta['quality_findings']:
        if finding['code']=='duplicate_task_examples':finding['count']=stats['collapsed_duplicate_examples']
        if finding['code']=='identical_input_different_labels':finding['count']=stats['identical_input_different_label_groups']
    meta['quality_findings'].append({'code':'numeric_precision_12_significant_digits','count':scan['changed_records'],'action':'round_prepared_numbers_rebuild_prompt_rehash_and_merge_exact_duplicates','detail':'Conservative decimal precision cap; original source files unchanged. All changes and old/new IDs retained in numeric_precision_changes.jsonl.gz.'})
    save(dst/'metadata.json',meta)
    featurecols[targetcol]=targetvalues
    save(dst/'quality_profile_prepared_features.json',normalize(profile(pd.DataFrame(featurecols))))
    with (dst/'preview.jsonl').open('w',encoding='utf-8') as f:
        for r in first.values():f.write(dumps(r)+'\n')
    save(dst/'numeric_precision_summary.json',scan)
    result=dict(uci_id=ds['uci_id'],status='passed',examples_verified=n,changed_records=scan['changed_records'],source_label_links_verified=refs,additional_duplicates_merged=scan['new_duplicate_records'],data_sha256=sha(dst/'data.jsonl'))
    return stats,result

def verify_staged(ds,scan):
    from decimal import Decimal
    rel=pathlib.Path(ds['path']);newpath=STAGE/rel if scan['changed_records'] else DEST/rel
    # Independent numerical bounds and decimal precision, plus exact source lineage.
    def expected():
        for line in (DEST/rel).open(encoding='utf-8'):
            old=json.loads(line);new=convert(old)
            for field,a,b in numeric_changes(old,new):
                da,db=Decimal(str(a)),Decimal(str(b))
                assert abs(da-db)<=abs(da)*Decimal('5.01e-12')
                assert b!=0 or a==0
            yield new
    exp=merge(expected()) if scan['new_duplicate_records'] else expected()
    count=0;source_links=0
    with newpath.open(encoding='utf-8') as f:
        for e in exp:
            line=f.readline();assert line
            actual=json.loads(line,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
            assert actual==e
            assert actual['split']=='unassigned'
            assert actual['duplicate_count']==len(actual['source_refs'])
            assert actual['input_hash']==digest(actual['input'])
            embedded=actual['prompt'].split('\nInput JSON: ',1)[1].split('\nReturn only one numeric prediction',1)[0]
            assert json.loads(embedded)==actual['input']
            numbers=list(actual['input'].values())+[actual['label']]+actual.get('target_observations',[])
            for v in numbers:
                if type(v)==float:assert len(Decimal(str(v)).normalize().as_tuple().digits)<=12
            count+=1;source_links+=len(actual['source_refs'])
        assert not f.readline()
    assert count==ds['output_examples']-scan['new_duplicate_records']
    assert source_links==ds['candidate_task_examples']

def main():
    baseline=json.loads((DEST/'manifest.json').read_text(encoding='utf-8'));assert baseline['version']=='2.0.0','Apply once after original two-batch build.'
    scan=json.loads((ROOT/'work/precision_scan.json').read_text(encoding='utf-8'));assert scan['policy']==POLICY
    scans={s['uci_id']:s for s in scan['datasets']};assert all(s['new_cross_group_equal_inputs']==0 for s in scans.values())
    oldchecks=json.loads((DEST/'checksums.json').read_text(encoding='utf-8'))
    for ds in baseline['datasets']:assert sha(DEST/ds['path'])==oldchecks[ds['path']]
    # Preserve an exact pre-change data snapshot for modified files and all replaced documentation.
    for p in list(DEST.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(DEST)
        if rel.parts[0] in ['history','raw'] or '__pycache__' in rel.parts:continue
        if p.name=='data.jsonl' and not scans[int(p.parent.name.split('_')[1])]['changed_records']:continue
        target=HISTORY/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copy2(p,target)
    results=[];stats=[]
    for ds in baseline['datasets']:
        s,res=stage_dataset(ds,scans[ds['uci_id']]);stats.append(s);results.append(res)
        verify_staged(ds,scans[ds['uci_id']]);gc.collect()
        print('VERIFIED '+dumps(res),flush=True)
    combined=STAGE/'combined/all.jsonl.gz';combined.parent.mkdir(parents=True,exist_ok=True)
    with combined.open('wb') as f,gzip.GzipFile(fileobj=f,mode='wb',compresslevel=5,mtime=0) as out:
        for ds in stats:
            p=STAGE/ds['path'] if scans[ds['uci_id']]['changed_records'] else DEST/ds['path']
            with p.open('rb') as src:shutil.copyfileobj(src,out,1024*1024)
    total=0
    with gzip.open(combined,'rb') as f:
        for ds in stats:
            p=STAGE/ds['path'] if scans[ds['uci_id']]['changed_records'] else DEST/ds['path'];n=0
            with p.open('rb') as src:
                for line in src:assert line==f.readline();n+=1
            assert n==ds['output_examples'];total+=n
        assert not f.read(1)
    # Publish only after every staged record and combined line has passed.
    for p in list(STAGE.rglob('*')):
        if p.is_file():
            target=DEST/p.relative_to(STAGE);target.parent.mkdir(parents=True,exist_ok=True);p.replace(target)
    manifest=copy.deepcopy(baseline);manifest.update(version='2.1.0',updated_date=DATE,datasets=stats,total_examples=total,collapsed_duplicate_examples=sum(s['collapsed_duplicate_examples'] for s in stats),numeric_precision=POLICY)
    for batch in manifest['batches']:batch['examples']=sum(s['output_examples'] for s in stats if s['batch']==batch['batch'])
    save(DEST/'manifest.json',manifest)
    schema=json.loads((DEST/'schema.json').read_text(encoding='utf-8'));schema['numeric_precision']=POLICY;save(DEST/'schema.json',schema)
    import csv
    with (DEST/'reports/dataset_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(stats[0]));w.writeheader();w.writerows(stats)
    changed=sum(s['changed_records'] for s in scans.values());merged=baseline['total_examples']-total
    summary={'version':'2.1.0','date':DATE,'policy':POLICY,'before_examples':baseline['total_examples'],'after_examples':total,'changed_records_before_merge':changed,'affected_datasets':sum(bool(s['changed_records']) for s in scans.values()),'additional_duplicate_records_merged':merged,'datasets':list(scans.values())}
    save(DEST/'reports/numeric_precision_report.json',summary)
    oldvalidation=json.loads((HISTORY/'reports/validation.json').read_text(encoding='utf-8'))
    result={'version':'2.1.0','status':'passed','examples_verified':total,'source_label_links_verified':oldvalidation['source_label_links_verified'],'numeric_policy':POLICY,'datasets':results,'training_executed':False,'checks':['Every old record mapped to its normalized record; merged duplicates retain all source_refs and multiplicity','Every changed number independently checked within 5.01e-12 relative error using Decimal; nonzero values never rounded to zero','At most 12 significant digits for nonintegral prepared numbers','All prompts contain exactly the corresponding input JSON','Input hashes and content-derived sample IDs regenerated; uniqueness checked','Known groups, exclusions, text, units and unassigned splits preserved','Every combined gzip line equals its per-dataset source','Raw source files retain baseline SHA256 values'],'source_validation_basis':'Original release fully source-validated; v2.1.0 verified exhaustively against that release with the declared precision transformation. Exact equality to unrounded floating source values is no longer claimed.'}
    # Original source bytes are still independently checked against their recorded hashes.
    for rel,h in oldchecks.items():
        if rel.startswith('raw/'):assert sha(DEST/rel)==h
    save(DEST/'reports/validation.json',result);save(ROOT/'outputs/general_dataset_validation.json',result)
    batch2_ids={s['uci_id'] for s in stats if s['batch']==2}
    save(DEST/'reports/batch2_validation.json',dict(result,datasets=[r for r in results if r['uci_id'] in batch2_ids],examples_verified=sum(s['output_examples'] for s in stats if s['batch']==2),source_label_links_verified=sum(s['candidate_task_examples'] for s in stats if s['batch']==2)))
    prefix=f'''# 通用回归数据质量报告：数值精度更新 v2.1.0

更新日期：{DATE}。当前 **29 个来源、33 个任务、{total:,} 条记录**。未训练，未划分训练集/验证集，未上传外部实验平台。

## 本次处理

所有准备好的 input 数值、label 和 target_observations 统一为最多 **12 位有效数字**；整数保留整数，null、文本、单位和原始来源文件不变。这里不是固定保留 12 位小数，也不是所有测量都具有 12 位有效精度：这只是保守的存储上限。高精度原始小数也会受到上限约束，全部改动均有审计记录。极小非零值保留，不做裁剪、标准化或插补。

例如 34.400000000000006 → 34.4；35.692499999999995 → 35.6925。三轮均值等循环小数也遵循相同上限。

共涉及 {summary['affected_datasets']} 个数据集、{changed:,} 条清理前记录；按既有规则合并 {merged} 条精度统一后相同的超导记录，来源行和重复次数全部保留。样本由 {baseline['total_examples']:,} 条变为 {total:,} 条，来源标签链接数量不变。没有新增跨 group_id 的相同输入。第一批数据本次也按同一规则清理；“第一批保持原样”仅描述下面保存的更新前版本。

| UCI | 清理前受影响记录 | 最大绝对变化 | 最大相对变化 | 新合并重复 |
|---|---:|---:|---:|---:|
'''
    for s in scans.values():
        if s['changed_records']:prefix+=f'| {s["uci_id"]} | {s["changed_records"]:,} | {s["max_absolute_change"]:.6g} | {s["max_relative_change"]:.6g} | {s["new_duplicate_records"]} |\n'
    prefix+='''
最大绝对变化按各数据集的原有尺度记录，不能跨单位直接比较。所有修改的相对误差均不超过 5.01×10⁻¹²。

## 同步与验证

已更新 input、数值标签、prompt、内容散列和样本 ID、每任务预览、处理后质量概况、统计、清单、合并文件和校验和。原有模型任务和已知分组不变。修改样本的旧/新 ID 与字段前后值保存在各目录 numeric_precision_changes.jsonl.gz 中；旧版已替换文件保存在 history/v2.0.0_before_precision。

对全部当前记录核对规范化结果、来源追溯、重复合并、数字精度、prompt/input 一致性和合并文件逐行一致性；原始下载文件散列保持一致。原有精确来源标签验证针对 v2.0.0，本版在此基础上验证数值舍入界限，不把舍入后的值误称为与原始浮点数逐位相同。当前验证结果见 reports/validation.json；旧版报告归档只作为历史证据。

复现顺序：先使用原有两批构建流程生成 v2.0.0，再运行 scripts/numeric_precision.py 全量扫描，最后运行 scripts/clean_numeric_precision.py 完成本次更新和验证。不要在 v2.1.0 上直接运行旧版重建或验证程序，因为它们针对未舍入版本。

## 更新前 v2.0.0 报告（历史记录，数量和“未修改”说明以本页上文为准）

'''
    oldreport=(HISTORY/'reports/质量检查报告.md').read_text(encoding='utf-8')
    body=prefix+oldreport; (DEST/'reports/质量检查报告.md').write_text(body,encoding='utf-8');(ROOT/'outputs/general_dataset_quality_report.md').write_text(body,encoding='utf-8')
    readme=(HISTORY/'README.md').read_text(encoding='utf-8')
    readme=readme.replace('1,067,483',f'{total:,}').replace('v2.0.0','v2.1.0')
    readme+='\n\n数值精度更新日期：2026-11-13。所有准备好的非整数数值最多 12 位有效数字，raw 原件不变。旧版构建后须依次运行 scripts/numeric_precision.py、scripts/clean_numeric_precision.py；当前验证结果在 reports/validation.json。版本前后映射与旧文件已归档。\n'
    (DEST/'README.md').write_text(readme,encoding='utf-8')
    # Save current versions of auxiliary record examples, while retaining their audit findings.
    review=DEST/'reports/apartment_text_review.json'
    if review.exists():
        obj=json.loads(review.read_text(encoding='utf-8'));obj['samples']=[convert(r) for r in obj['samples']];save(review,obj)
    for name in ['numeric_precision.py','clean_numeric_precision.py']:shutil.copy2(ROOT/'work'/name,DEST/'scripts'/name)
    save(DEST/'checksums.json',{str(p.relative_to(DEST)).replace('\\','/'):sha(p) for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='checksums.json' and '__pycache__' not in p.parts})
    print(dumps({'status':'passed','version':'2.1.0','examples':total,'affected_records':changed,'additional_duplicates_merged':merged,'training_executed':False}),flush=True)

if __name__=='__main__':main()
