"""Publish both batches and verify combined bytes; no model training."""
import csv,gzip,importlib.metadata,json,pathlib,shutil
from load_batch2 import ROOT,DEST,IDS,base
from batch2_contracts import CONTRACTS
from build_general import save
from build_batch2 import sha

def main():
    previous=json.loads((DEST/'history/batch1/manifest.json').read_text(encoding='utf-8'))
    oldchecks=json.loads((DEST/'history/batch1/checksums.json').read_text(encoding='utf-8'))
    for s in previous['datasets']:
        assert sha(DEST/s['path'])==oldchecks[s['path']],('First batch changed',s['uci_id'])
    metas=[json.loads((DEST/'datasets'/f'uci_{i}_{CONTRACTS[i]["key"]}'/'metadata.json').read_text(encoding='utf-8')) for i in IDS]
    stats=[dict(s,batch=1,excluded_source_rows=0) for s in previous['datasets']]+[m['stats'] for m in metas]
    validation=json.loads((DEST/'reports/batch2_validation.json').read_text(encoding='utf-8'))
    assert {x['uci_id'] for x in validation['datasets']}==set(IDS) and validation['status']=='passed'
    verified={x['uci_id']:x['data_sha256'] for x in validation['datasets']}
    for s in stats[18:]:assert sha(DEST/s['path'])==verified[s['uci_id']]
    # Check downloaded original infrared files against the publisher's checksum list.
    published=[]
    for line in (base(925)/'SHA256SUMS.txt').read_text().splitlines():
        h,name=line.split(maxsplit=1);p=base(925)/name
        if p.is_file():assert sha(p)==h,('Publisher checksum mismatch',name);published.append(name)
    assert len(published)==5
    print('First batch unchanged; publisher checksums passed',flush=True)
    combined=DEST/'combined/all.jsonl.gz';tmp=combined.with_suffix('.gz.tmp')
    with tmp.open('wb') as f,gzip.GzipFile(fileobj=f,mode='wb',compresslevel=5,mtime=0) as out:
        for s in stats:
            with (DEST/s['path']).open('rb') as src:shutil.copyfileobj(src,out,1024*1024)
            print('Combined',s['uci_id'],flush=True)
    tmp.replace(combined)
    # Exact combined-record correspondence without re-parsing copies.
    count=0
    with gzip.open(combined,'rb') as f:
        for s in stats:
            n=0
            with (DEST/s['path']).open('rb') as src:
                for line in src:assert f.readline()==line;n+=1
            assert n==s['output_examples'];count+=n
        assert not f.read(1)
    total=lambda key:sum(s.get(key,0) for s in stats)
    manifest=dict(previous,version='2.0.0',updated_date='2026-11-09',datasets=stats,dataset_count=len(stats),task_count=total('task_count'),total_selected_source_rows=total('raw_rows_selected'),total_examples=count,collapsed_duplicate_examples=total('collapsed_duplicate_examples'),invalid_label_examples=total('invalid_label_examples'),excluded_source_rows=total('excluded_source_rows'),record_schema_version='1.0.0',batches=[dict(batch=1,datasets=18,tasks=21,examples=previous['total_examples']),dict(batch=2,datasets=11,tasks=sum(s['task_count'] for s in stats[18:]),examples=sum(s['output_examples'] for s in stats[18:]))])
    assert manifest['dataset_count']==29 and manifest['task_count']==33
    save(DEST/'manifest.json',manifest)
    inventory_history=DEST/'history/batch1/download_inventory.json'
    if not inventory_history.exists():shutil.copy2(DEST/'download_inventory.json',inventory_history)
    save(DEST/'download_inventory.json',json.loads(inventory_history.read_text(encoding='utf-8'))+json.loads((DEST/'download_inventory_batch2.json').read_text(encoding='utf-8')))
    save(DEST/'reports/batch2_build_run.json',[s for s in stats if s['batch']==2])
    schema=json.loads((DEST/'schema.json').read_text(encoding='utf-8'))
    schema.update(target_transform='none_applied except SGEMM arithmetic_mean_of_four_source_runs; QSAR source labels already transformed',entity_id='optional known subject/station ID for grouping; never included in prompt unless explicitly a domain feature',target_observations='optional SGEMM four original runtime measurements; outcomes only, never input')
    save(DEST/'schema.json',schema)
    fields=list(stats[0])
    with (DEST/'reports/dataset_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(stats)
    oldvalidation=json.loads((DEST/'history/batch1/validation.json').read_text(encoding='utf-8'))
    result={'status':'passed','examples_verified':count,'source_label_links_verified':oldvalidation['source_label_links_verified']+sum(x['source_label_links_verified'] for x in validation['datasets']),'first_batch_verification':'All 18 data.jsonl SHA256 values unchanged from fully source-validated batch 1','second_batch_verification':'Full record/schema/prompt/input/label/lineage checks against source; SGEMM targets and thermal means independently recomputed; all source rows accounted for including exclusions','combined_verification':'Every line equals the corresponding individual dataset record, in manifest order','publisher_checksums_verified':published,'training_executed':False,'datasets':oldvalidation['datasets']+validation['datasets'],'checks':['29 sources / 33 tasks','finite numeric labels and JSON parsing','task/input/label deduplication and sample ID uniqueness within dataset; dataset-prefixed IDs','prohibited fields absent','prompt embedded JSON equals input','missing labels never imputed','semantic groups and identical inputs consistent','rent free text scanned for digits, number words and money tokens','first batch unchanged','combined file exact line correspondence','split unassigned for every record']}
    save(DEST/'reports/validation.json',result);save(ROOT/'outputs/general_dataset_validation.json',result)
    b=stats[18:];added=sum(s['output_examples'] for s in b)
    report=[f'# 通用回归数据构建与质量报告（第一、二批）\n\n更新日期：2026-11-09。共 **29 个来源、33 个任务、{count:,} 条记录**。第二批新增 **11 个来源、12 个任务、{added:,} 条记录**。第一批 126,224 条记录逐文件校验，内容未改变。未训练、未划分训练/验证集、未向外部实验平台上传数据。',f'\n## 数量与处理\n\n两批选定原始表共 {total("raw_rows_selected"):,} 行；按目标展开后，合并重复任务/输入/标签 {total("collapsed_duplicate_examples"):,} 条，排除无效/缺失标签 {total("invalid_label_examples"):,} 个；另有 {total("excluded_source_rows"):,} 个来源行不符合任务范围而排除。目标缺失与范围排除分别记账，不插补标签。', '\n| 批次 | UCI | 数据集 | 来源行 | 任务 | 最终样本 | 合并重复 | 无效标签 | 范围排除 | 含缺失输入 |\n|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in stats:report.append(f'| {s["batch"]} | {s["uci_id"]} | [{s["name"]}]({s["source_url"]}) | {s["raw_rows_selected"]:,} | {s["task_count"]} | {s["output_examples"]:,} | {s["collapsed_duplicate_examples"]:,} | {s["invalid_label_examples"]:,} | {s["excluded_source_rows"]:,} | {s["examples_with_null_input"]:,} |')
    report.append('''
## 第二批的重要处理与限制

- **北京空气质量**：12 站点；仅构造 PM2.5 回归，删除其他同期污染物输入，8,739 个缺失 PM2.5 标签排除。气象缺失保留 null；没有把未经证实的极值当缺失。同期估计不能解释为未来天气已知的预测。
- **租金**：只用实际 99,492 行的 100K 文件，不叠加 10K 文件；限定公寓、USD、明确月租、有效面积。删除 price_display 等价格字段；标题、正文和设施文本均去除金额语句、数字和英文数字词，规则不读取目标价格。这会损失部分文本信息，原文仍在 raw 中；不能把规则扫描通过当成已证明不存在任何语义泄漏。保留独立的结构化面积、卧室等信息。地址/位置及相同描述只能提供分组代理，不能证明精确楼栋身份。
- **GPU 运行时间**：四次测量均值作为单个数值标签，原四次观测保存在 target_observations，不出现在 prompt；不制造 uncertainty 标签。241,600 个配置来自固定硬件，不代表跨硬件泛化。
- **红外体温**：采用 UCI 指向的 PhysioNet 原始发布，FLIR 1,020 + ICI 1,009，共 2,029 条设备记录、1,026 人；不是 2,029 个独立受试者。27 个温度/校准特征按每人每设备可用轮次求均值，另一种口温标签不作输入；按 SubjectID 跨设备分组。原始发布为 CC0，保留其 LICENSE 与官方校验和。
- **燃气轮机**：CO、NOx 各一个任务，两个目标均从输入移除；单位按官方表格为 mg/m³。与第一批 CCPP 共享 turkish_power_plant 家族，不能分别放入训练集与“新领域”测试集。湿度略超 100 的原值保留并标记。
- **新闻分享量**：去掉依赖分享量的关键词/引用统计及拟合来源不明的 LDA 特征；3 个超出 [0,1] 的比例单元格置 null。标签是不同文章曝光时间下的累计快照，不是固定 7/30 天分享量。
- **蛋白结构**：归档没有蛋白 ID；只能按相同描述符合组，不能保证训练/测试蛋白独立，暂不用于声称“未见蛋白泛化”的主评测。
- **汽车价格**：去掉价格相关保险风险和保险损失字段，排除 4 个缺失价格。价格单位在所用归档中未明确，不擅自标注美元。
- **首尔单车、家电**：分别按日期解析和整日分组；保留停运小时的零租借。家电删去两列完全相同的随机控制变量；数据仅来自一栋住宅。
- **森林火灾**：保留零值、长尾和原始公顷标签，不做对数变换；按空间网格分组，但缺少完整事件身份与日期。

## 使用格式与验证

沿用第一批 schema 1.0.0：英文任务说明 + 字段解释 + Input JSON 为 prompt，label 为单个有限数值；每条记录还保留 input、单位、source_refs、重复次数、分组和质量标记。文件集合版本更新为 2.0.0。

逐条核对第二批来源标签、JSON、禁入字段、输入散列、prompt 嵌入数据、重复和分组；独立重算 GPU 四次均值和红外轮次均值。第一批文件散列保持不变，沿用已完成的原始标签全量验证；合并 gzip 与所有分文件逐行一致。范围排除与无效标签有独立清单。报告通过的是明确列出的检查，不能消除未观测混杂、数据来源偏差或未知关联。

所有 split 仍为 unassigned。训练前先确定数据集家族留出、时间/主体分组划分、各任务采样权重，避免北京与 GPU 大数据量主导训练；按实际 Jev tokenizer 检查 prompt 长度，再只用训练分区拟合需要的变换。提前配置本地日志或经授权的 W&B，固定验证集与指标定义，记录配置、step/epoch 和阶段 checkpoint。本次没有运行模型或安排训练。

每个 datasets 子目录含 data.jsonl、metadata.json、preview.jsonl、原始/处理后质量概况、变更与排除清单、prompt 模板；raw 保留下载原件和来源元数据。combined/all.jsonl.gz 汇总全部记录，manifest.json、schema.json、checksums.json 描述版本与格式。
''')
    report.append('\n租金文本采用固定随机种子抽查 8 条，保存于 reports/apartment_text_review.json。抽样发现个别标题城市与结构化城市不一致；未基于猜测重写地点。类别字段也不能保证每条都是整套出租而非合租广告。抽查不能量化总体错误率；后续地点或整租评测应单独核实范围。\n')
    report.append('\n## 第二批逐项可追溯记录\n')
    for m in metas:
        s=m['stats'];report.append(f'### {s["uci_id"]} — {s["name"]}\n\n建议划分：{m["contract"]["split"]}。')
        for q in m['quality_findings']:report.append(f'- `{q["code"]}`：{q["count"]}；{q["detail"]} 处理：{q["action"]}。')
    original=(DEST/'history/batch1/质量检查报告.md').read_text(encoding='utf-8')
    report.append('\n## 第一批原有处理说明（保留）\n'+original.split('## 关键处理和限制',1)[1])
    body='\n'.join(report)+'\n';(DEST/'reports/质量检查报告.md').write_text(body,encoding='utf-8');(ROOT/'outputs/general_dataset_quality_report.md').write_text(body,encoding='utf-8')
    (DEST/'README.md').write_text(f'# 构造 general 数据集\n\n29 个来源、33 个回归任务、{count:,} 条 prompt + 数值标签记录。两批原始文件、处理后文件及质量报告均在本目录。未训练；split 全部 unassigned。\n\n- 数据：datasets/*/data.jsonl\n- 合并：combined/all.jsonl.gz\n- 清单：manifest.json\n- 质量报告：reports/质量检查报告.md\n- 验证：reports/validation.json\n- 来源与许可：raw/*/source_manifest.json、datasets/*/metadata.json\n- 历史：history/batch1/\n\n记录格式 v1.0.0，文件集合 v2.0.0。使用前阅读质量报告和各任务 split 说明；分组是已知关联控制，不能保证独立。\n\n重建第二批：在项目目录运行 python work/download_batch2.py、python work/build_batch2.py、python work/validate_batch2.py、python work/finalize_batch2.py。第一批构建脚本是历史流程，会覆盖全局清单；已有两批时不要直接运行旧版全量构建/验证。scripts 中保存相应构建脚本副本。\n',encoding='utf-8')
    for name in ['download_batch2.py','load_batch2.py','batch2_contracts.py','prepare_batch2.py','build_batch2.py','validate_batch2.py','review_batch2_samples.py','finalize_batch2.py']:
        shutil.copy2(ROOT/'work'/name,DEST/'scripts'/name)
    packages=['pandas','numpy','openpyxl','xlrd','py7zr','pypdf']
    save(DEST/'build_environment_batch2.json',{'packages':{p:importlib.metadata.version(p) for p in packages},'python':__import__('sys').version,'training_executed':False})
    (DEST/'scripts/requirements_batch2.txt').write_text('\n'.join(f'{p}=={importlib.metadata.version(p)}' for p in packages)+'\n')
    checksums={str(p.relative_to(DEST)).replace('\\','/'):sha(p) for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='checksums.json' and '__pycache__' not in p.parts}
    save(DEST/'checksums.json',checksums)
    print(json.dumps({'datasets':29,'tasks':33,'total_examples':count,'batch2_examples':added,'status':'passed'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
