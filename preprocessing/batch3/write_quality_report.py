"""Generate reviewable release notes from validated manifest and source metadata."""
import json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parent;PUB=ROOT/'publish';OUTPUT=ROOT.parents[1]/'outputs'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 m=load(PUB/'manifest.json');new=[d for d in m['datasets'] if d['batch']==3];old=load(PUB/'reports/old_source_integrity.json');rows=[]
 lines=['# Jev 回归数据集 v2.2.0 质量报告','',f'处理日期：2026-11-15。总计 **{m["dataset_count"]} 个来源、{m["task_count"]} 个任务、{m["total_examples"]:,} 条样本**；本次新增 **{sum(d["output_examples"] for d in new):,} 条**。','',
 '范围：仅 T1–T3、S1–S2、S4、H1–H2、O1–O2。T3 排除第三方阅读材料全文。其余 16 项仍待审批。本次没有训练、拟合预处理或启用外部实验追踪。','',
 f'基线为提交 `{old["baseline_commit"]}` 的 v2.1.0。隔离发布副本中，旧 29 个来源的 {len(old["checked_files"])} 个数据/来源文件逐文件 SHA256 一致；旧 1,067,479 条有效记录保持不变。旧来源的详细问题仍见[历史质量报告](../history/v2.1.0/quality_report_zh.md)。','',
 '## 新增规模与划分','', '| 审批 | 来源 | 原始读取行数 | 发布样本 | 任务 | 分组数 | 划分 |','|---|---|---:|---:|---:|---:|---|']
 for d in new:
  counts=' / '.join(f'{k}: {v:,}' for k,v in d['split_counts'].items());lines.append(f'| {d["candidate_id"]} | {d["name"]} | {d["raw_rows_selected"]:,} | {d["output_examples"]:,} | {d["task_count"]} | {d["split_groups"]:,} | {counts} |')
  folder=PUB/pathlib.Path(d['files'][0]['path']).parent;meta=load(folder/'metadata.json');rows.append((d,meta,folder))
 lines+=['','原始行数的粒度依来源而异：文本是文章/表达式，科学数据是分子/变体/结构，时序数据是日或周期记录。发布窗口数量不可当作独立实体数量。Empathy 两个目标共用同一批文本与分组。','',
 '## 关键质量结论','',
 '- **T1 CompLex**：10,800 条；保留官方 train/trial/test（trial 映射 validation）。按词项与句子依赖连接后有 176 个组跨官方划分；没有完全相同输入跨官方划分。5 组相同输入存在不同标签，全部保留并标记。官方评测与严格分组泛化是不同实验设置。',
 '- **T2 Empathic Reactions**：1,860 篇文本生成 3,720 条 empathy/distress 样本；372 个反应会话/文本组。标签是 1–7 自我报告量表；另一标签、文章标识和会话标识不进入输入。没有下载或发布新闻全文。',
 '- **T3 ASAP2**：实测 24,728 篇，17,307 train / 7,421 test；README 中的总数与实际文件不一致，采用文件实数。7 个题目；28 条短题目说明缺失，保留 null。输入仅作文、题名和可用短说明，不下载或发布第三方阅读材料全文；缺少阅读上下文限制了评分任务。序数 1–6 标签明确标为 ordinal。',
 '- **S1 FreeSolv**：642 个不同规范化分子，目标为实验水合自由能 kcal/mol，负值和零值均保留。计算自由能与误差不进入输入；实验误差出处留在元数据。RDKit scaffold 得到 63 组，其中 320 个无环分子共用一个大组，不能宣称分组均衡。',
 '- **S2 GB1**：从 191,157 原始行保留 149,361 个标准四位氨基酸且有有限观测衍生 I20fit 的变体；排除 41,796 行，其中无效标签统计是排除集合的一部分，不重复相加。保留 29,477 个零值，不使用缺失变体预测文件。标签为相对 IgG-Fc 结合适应度，非绝对亲和力；仅单一蛋白背景。按变体标识分组仍不能阻止相近突变泄漏，应另按突变深度或序列距离设计划分。',
 '- **S4 JDFT2D**：636 个结构/DFT 剥离能对，与原始 Figshare v1 逐行核对。输入只含晶格、元素、分数坐标和周期条件；无目标相关能量分量。568 个组成组是保守近似，不宣称完成了晶体等价判定；超出 [0,1) 的合法周期坐标原样保留。',
 '- **H1 C-MAPSS**：实际 709 台训练、707 台测试发动机，来源 README 的 FD004 数量与文件不一致。30 周期历史，训练按 10 周期步长并加末端；测试仅末端。15,627 个窗口中 train 14,937 / test 690；17 台测试发动机历史不足 30 周期而排除，不补齐。训练标签为失效周期减预测周期；测试使用官方 RUL；均不截顶。发动机组包含子集与原始 split，避免编号碰撞。',
 '- **H2 CAMELS-GB**：全部 671 流域、1970-10-01 至 2015-09-30，11,028,556 原始日记录。362,340 个月末机会中得到 324,656 个样本；36,040 个缺失次日标签、973 个历史不完整、671 个目标超出数据期而排除。预测起点为月末 d，输入历史为 d−7 至 d−1 的 7 条日记录，目标为 d+1 流量 mm/day。额外一天滞后避免降雨/流量日界不一致带来的亚日重叠；不等价于实时可用性承诺，因为公开档案可能事后修订。仅加入静态地理属性，不使用全期水文汇总或未来天气。',
 '- **O1 Auction**：2,043 条输入配置，预测来源已聚合的平均验证时间 ms。另一验证结果列排除；24 个容量组合组。原始重复运行数量与方差无法恢复，不伪造不确定性标签。',
 '- **O2 Transcoding**：仅使用 68,784 条有标签测量，不把百万级无标签视频元数据算成训练样本。运行后内存 umem 与视频 ID 排除于输入；按 1,099 个视频/相同输入连接组分组。81 组相同输入不同耗时保留；固定硬件与短片段实验，不宣称跨硬件或完整视频耗时预测。','',
 '## 清洗、验证与可复现性','',
 '1. 下载清单保留冻结提交/版本、官方 URL、SHA256 与字节数；原始文件保留本地，不改写。来源许可和归属按源分别记录：CAMELS-GB 为 OGL v3，其余新增源按来源证据标注 CC BY 4.0。这些许可不扩展到排除的第三方阅读材料或视频媒体。',
 '2. 每条记录是固定英语任务说明与输入 JSON，配一个有限数值标签。按来源白名单选择输入；标签、另一测量结果、失效未来信息、来源行号及实体标识不作为答案线索加入 prompt。来源元数据本身也不能作为模型输入。',
 '3. 标签不插补、不平滑、不截顶。浮点存储最多 12 位有效数字，逐值检查相对误差不超过 5.01e-12；整数、布尔、字符串与缺失 null 保持类型。',
 '4. 去重键为 task、规范化 input、规范化 label 和官方 split。不同标签保留；跨 split 的相同样本保留其官方出现并标记；相同输入的分组做连接闭包。来源出现与 source_refs 全部保留。本批没有需要合并的同键重复记录。',
 '5. 源构建器逐行核对原始标签/输入；独立统一验证遍历全部新增记录，检查输入与 prompt 一致、数值精度、内容哈希、sample_id 唯一、来源引用、划分、分组与原始文件哈希。分片解压后再核对完整数据哈希与记录数。',
 '6. 旧数据及来源文件做逐文件完整性比较；仓库读取器增加非 UCI dataset_id 支持。发布数据使用普通 gzip JSONL，无 Git LFS；新增分片最多 20,000 行，并控制未压缩块大小；所有分片低于 50 MiB。',
 '7. 执行源码、依赖版本、验证结果、异常/窗口排除日志随发布保存。大体积原始档案及依赖 vendor 不上传。','',
 '## 后续实验使用限制','',
 '本次是数据准备发布，不是模型性能证明。仅词汇、作文和发动机数据保留可用官方划分；其余仍 unassigned。未来实验应先确定跨来源/任务留出、同实体及时间划分；相邻窗口及同视频配置不得随机拆散。不要把不同任务原始损失数值直接比较，也不要让大来源以样本数量自然主导训练。训练开始前另行配置本地日志或获授权的实验追踪，记录固定样本上的训练/验证指标、配置和 checkpoint。本次没有训练。','',
 '## 逐来源证据入口','']
 for d,meta,folder in rows:
  rel=folder.relative_to(PUB).as_posix();lines.append(f'- {d["candidate_id"]}: [{d["name"]}]({d["source_url"]})；[元数据](../{rel}/metadata.json)；[逐条验证](../{rel}/record_validation.json)。')
 lines+=['','验证清单：[新增记录验证](extension_validation.json)、[旧数据完整性](old_source_integrity.json)、[来源详细汇总](extension_metadata_summary.json)。全库清单与 SHA256 位于仓库根目录。','']
 report='\n'.join(lines);(PUB/'reports/quality_report_v2.2.0_zh.md').write_text(report,encoding='utf-8')
 if not (PUB/'history/v2.1.0/quality_report_zh.md').exists():shutil.copy2(PUB/'reports/quality_report_zh.md',PUB/'history/v2.1.0/quality_report_zh.md')
 (PUB/'reports/quality_report_zh.md').write_text(report,encoding='utf-8')
 # User-facing copy uses GitHub links rather than relative repository paths.
 public=report.replace('](../datasets/','](https://github.com/lhc060105louis-source/prompt-regression-datasets/blob/main/datasets/').replace('](../history/','](https://github.com/lhc060105louis-source/prompt-regression-datasets/blob/main/history/')
 for name in ['extension_validation.json','old_source_integrity.json','extension_metadata_summary.json']:public=public.replace(']('+name+')','](https://github.com/lhc060105louis-source/prompt-regression-datasets/blob/main/reports/'+name+')')
 (OUTPUT/'Jev_v2.2.0_质量报告.md').write_text(public,encoding='utf-8')
 shutil.copy2(PUB/'manifest.json',OUTPUT/'Jev_v2.2.0_manifest.json');shutil.copy2(PUB/'docs/candidate_approval.csv',OUTPUT/'Jev_26候选_审批清单.csv')
 print('QUALITY_REPORT',len(report),m['total_examples'])
if __name__=='__main__':main()
