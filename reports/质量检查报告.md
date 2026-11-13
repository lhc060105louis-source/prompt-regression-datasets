# 通用回归数据质量报告：数值精度更新 v2.1.0

更新日期：2026-11-13。当前 **29 个来源、33 个任务、1,067,479 条记录**。未训练，未划分训练集/验证集，未上传外部实验平台。

## 本次处理

所有准备好的 input 数值、label 和 target_observations 统一为最多 **12 位有效数字**；整数保留整数，null、文本、单位和原始来源文件不变。这里不是固定保留 12 位小数，也不是所有测量都具有 12 位有效精度：这只是保守的存储上限。高精度原始小数也会受到上限约束，全部改动均有审计记录。极小非零值保留，不做裁剪、标准化或插补。

例如 34.400000000000006 → 34.4；35.692499999999995 → 35.6925。三轮均值等循环小数也遵循相同上限。

共涉及 9 个数据集、111,166 条清理前记录；按既有规则合并 4 条精度统一后相同的超导记录，来源行和重复次数全部保留。样本由 1,067,483 条变为 1,067,479 条，来源标签链接数量不变。没有新增跨 group_id 的相同输入。第一批数据本次也按同一规则清理；“第一批保持原样”仅描述下面保存的更新前版本。

| UCI | 清理前受影响记录 | 最大绝对变化 | 最大相对变化 | 新合并重复 |
|---|---:|---:|---:|---:|
| 165 | 249 | 4.13678e-11 | 2.74446e-12 | 0 |
| 464 | 20,916 | 5.00004e-08 | 4.99578e-12 | 4 |
| 186 | 32 | 3.33014e-11 | 3.3189e-12 | 0 |
| 492 | 71 | 1.13687e-13 | 4.03075e-16 | 0 |
| 374 | 19,718 | 4.7612e-10 | 4.43702e-12 | 0 |
| 501 | 758 | 3.33011e-09 | 3.3189e-12 | 0 |
| 440 | 67,399 | 4.54747e-13 | 3.32875e-16 | 0 |
| 332 | 4 | 1.2326e-32 | 2.22045e-16 | 0 |
| 925 | 2,019 | 3.33458e-11 | 3.22591e-12 | 0 |

最大绝对变化按各数据集的原有尺度记录，不能跨单位直接比较。所有修改的相对误差均不超过 5.01×10⁻¹²。

## 同步与验证

已更新 input、数值标签、prompt、内容散列和样本 ID、每任务预览、处理后质量概况、统计、清单、合并文件和校验和。原有模型任务和已知分组不变。修改样本的旧/新 ID 与字段前后值保存在各目录 numeric_precision_changes.jsonl.gz 中；旧版已替换文件保存在 history/v2.0.0_before_precision。

对全部当前记录核对规范化结果、来源追溯、重复合并、数字精度、prompt/input 一致性和合并文件逐行一致性；原始下载文件散列保持一致。原有精确来源标签验证针对 v2.0.0，本版在此基础上验证数值舍入界限，不把舍入后的值误称为与原始浮点数逐位相同。当前验证结果见 reports/validation.json；旧版报告归档只作为历史证据。

复现顺序：先使用原有两批构建流程生成 v2.0.0，再运行 scripts/numeric_precision.py 全量扫描，最后运行 scripts/clean_numeric_precision.py 完成本次更新和验证。不要在 v2.1.0 上直接运行旧版重建或验证程序，因为它们针对未舍入版本。

## 更新前 v2.0.0 报告（历史记录，数量和“未修改”说明以本页上文为准）

# 通用回归数据构建与质量报告（第一、二批）

更新日期：2026-11-09。共 **29 个来源、33 个任务、1,067,483 条记录**。第二批新增 **11 个来源、12 个任务、941,259 条记录**。第一批 126,224 条记录逐文件校验，内容未改变。未训练、未划分训练/验证集、未向外部实验平台上传数据。

## 数量与处理

两批选定原始表共 1,036,122 行；按目标展开后，合并重复任务/输入/标签 3,206 条，排除无效/缺失标签 8,744 个；另有 65 个来源行不符合任务范围而排除。目标缺失与范围排除分别记账，不插补标签。

| 批次 | UCI | 数据集 | 来源行 | 任务 | 最终样本 | 合并重复 | 无效标签 | 范围排除 | 含缺失输入 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 165 | [Concrete Compressive Strength](https://archive.ics.uci.edu/dataset/165/concrete+compressive+strength) | 1,030 | 1 | 1,005 | 25 | 0 | 0 | 0 |
| 1 | 242 | [Energy Efficiency](https://archive.ics.uci.edu/dataset/242/energy+efficiency) | 768 | 2 | 1,536 | 0 | 0 | 0 | 0 |
| 1 | 294 | [Combined Cycle Power Plant](https://archive.ics.uci.edu/dataset/294/combined+cycle+power+plant) | 9,568 | 1 | 9,527 | 41 | 0 | 0 | 0 |
| 1 | 291 | [Airfoil Self-Noise](https://archive.ics.uci.edu/dataset/291/airfoil+self+noise) | 1,503 | 1 | 1,503 | 0 | 0 | 0 | 0 |
| 1 | 243 | [Yacht Hydrodynamics](https://archive.ics.uci.edu/dataset/243/yacht+hydrodynamics) | 308 | 1 | 308 | 0 | 0 | 0 | 0 |
| 1 | 1 | [Abalone](https://archive.ics.uci.edu/dataset/1/abalone) | 4,177 | 1 | 4,177 | 0 | 0 | 0 | 2 |
| 1 | 9 | [Auto MPG](https://archive.ics.uci.edu/dataset/9/auto+mpg) | 398 | 1 | 398 | 0 | 0 | 0 | 6 |
| 1 | 477 | [Real Estate Valuation](https://archive.ics.uci.edu/dataset/477/real+estate+valuation+data+set) | 414 | 1 | 414 | 0 | 0 | 0 | 0 |
| 1 | 29 | [Computer Hardware](https://archive.ics.uci.edu/dataset/29/computer+hardware) | 209 | 1 | 209 | 0 | 0 | 0 | 0 |
| 1 | 87 | [Servo](https://archive.ics.uci.edu/dataset/87/servo) | 167 | 1 | 167 | 0 | 0 | 0 | 0 |
| 1 | 464 | [Superconductivty Data](https://archive.ics.uci.edu/dataset/464/superconductivty+data) | 21,263 | 1 | 21,197 | 66 | 0 | 0 | 0 |
| 1 | 504 | [QSAR fish toxicity](https://archive.ics.uci.edu/dataset/504/qsar+fish+toxicity) | 908 | 1 | 907 | 1 | 0 | 0 | 0 |
| 1 | 186 | [Wine Quality](https://archive.ics.uci.edu/dataset/186/wine+quality) | 6,497 | 1 | 5,320 | 1,177 | 0 | 0 | 0 |
| 1 | 320 | [Student Performance](https://archive.ics.uci.edu/dataset/320/student+performance) | 1,044 | 2 | 1,043 | 1 | 0 | 0 | 0 |
| 1 | 189 | [Parkinsons Telemonitoring](https://archive.ics.uci.edu/dataset/189/parkinsons+telemonitoring) | 5,875 | 2 | 11,750 | 0 | 0 | 0 | 0 |
| 1 | 597 | [Productivity Prediction of Garment Employees](https://archive.ics.uci.edu/dataset/597/productivity+prediction+of+garment+employees) | 1,197 | 1 | 1,197 | 0 | 0 | 0 | 506 |
| 1 | 275 | [Bike Sharing](https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset) | 17,379 | 1 | 17,379 | 0 | 0 | 0 | 0 |
| 1 | 492 | [Metro Interstate Traffic Volume](https://archive.ics.uci.edu/dataset/492/metro+interstate+traffic+volume) | 48,204 | 1 | 48,187 | 17 | 0 | 0 | 10 |
| 2 | 10 | [Automobile](https://archive.ics.uci.edu/dataset/10/automobile) | 205 | 1 | 201 | 0 | 4 | 0 | 8 |
| 2 | 265 | [Physicochemical Properties of Protein Tertiary Structure](https://archive.ics.uci.edu/dataset/265/physicochemical+properties+of+protein+tertiary+structure) | 45,730 | 1 | 44,019 | 1,711 | 0 | 0 | 0 |
| 2 | 560 | [Seoul Bike Sharing Demand](https://archive.ics.uci.edu/dataset/560/seoul+bike+sharing+demand) | 8,760 | 1 | 8,760 | 0 | 0 | 0 | 0 |
| 2 | 374 | [Appliances Energy Prediction](https://archive.ics.uci.edu/dataset/374/appliances+energy+prediction) | 19,735 | 1 | 19,735 | 0 | 0 | 0 | 0 |
| 2 | 501 | [Beijing Multi-Site Air Quality](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data) | 420,768 | 1 | 412,029 | 0 | 8,739 | 0 | 1,885 |
| 2 | 551 | [Gas Turbine CO and NOx Emission Data Set](https://archive.ics.uci.edu/dataset/551/gas+turbine+co+and+nox+emission+data+set) | 36,733 | 2 | 73,452 | 14 | 0 | 0 | 0 |
| 2 | 440 | [SGEMM GPU kernel performance](https://archive.ics.uci.edu/dataset/440/sgemm+gpu+kernel+performance) | 241,600 | 1 | 241,600 | 0 | 0 | 0 | 0 |
| 2 | 332 | [Online News Popularity](https://archive.ics.uci.edu/dataset/332/online+news+popularity) | 39,644 | 1 | 39,644 | 0 | 0 | 0 | 1 |
| 2 | 555 | [Apartment for Rent Classified](https://archive.ics.uci.edu/dataset/555/apartment+for+rent+classified) | 99,492 | 1 | 99,277 | 149 | 1 | 65 | 68,994 |
| 2 | 162 | [Forest Fires](https://archive.ics.uci.edu/dataset/162/forest+fires) | 517 | 1 | 513 | 4 | 0 | 0 | 0 |
| 2 | 925 | [Infrared Thermography Temperature](https://archive.ics.uci.edu/dataset/925/infrared+thermography+temperature+dataset) | 2,029 | 1 | 2,029 | 0 | 0 | 0 | 5 |

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


租金文本采用固定随机种子抽查 8 条，保存于 reports/apartment_text_review.json。抽样发现个别标题城市与结构化城市不一致；未基于猜测重写地点。类别字段也不能保证每条都是整套出租而非合租广告。抽查不能量化总体错误率；后续地点或整租评测应单独核实范围。


## 第二批逐项可追溯记录

### 10 — Automobile

建议划分：group_by_recorded_vehicle_configuration; exact model IDs unavailable。
- `insurance_features_removed`：2；symboling is explicitly price-related in the source; insurance-loss summary also excluded. 处理：remove。
- `identical_input_different_labels`：8；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：0；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 265 — Physicochemical Properties of Protein Tertiary Structure

建议划分：identical_descriptor_groups_only; protein identity unavailable; do not claim unseen-protein generalization。
- `protein_identity_unavailable`：45730；CASP.csv only has RMSD and F1-F9. No protein IDs can be recovered from these supplied files; exact-input grouping does not establish new-protein generalization. 处理：limit_claim。
- `identical_input_different_labels`：38；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：1711；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 560 — Seoul Bike Sharing Demand

建议划分：chronological_by_date; whole days grouped。
- `closed_hours_zero_demand`：295；Closed hours are not missing labels; keep functioning_day to distinguish them. 处理：retain_operating_status。
- `source_date_format`：8760；Actual CSV is DD/MM/YYYY, contrary to generic web wording. Converted to ISO date. 处理：parse_day_first。
- `identical_input_different_labels`：0；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：0；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 374 — Appliances Energy Prediction

建议划分：chronological_by_date; one house only。
- `random_columns`：2；rv1 and rv2 are exactly equal random controls, not domain predictors. 处理：remove。
- `single_house`：1；No claim of generalization to new houses; source weather interpolation prevents an unqualified online-forecast claim. 处理：limit_claim。
- `identical_input_different_labels`：0；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：0；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 501 — Beijing Multi-Site Air Quality

建议划分：chronological blocks across all stations; station holdout separately supported by entity_id。
- `missing_pm25_labels`：8739；Do not impute PM2.5 outcomes; retain rows with missing meteorological inputs as null. 处理：exclude_label_missing。
- `pollutant_targets_removed`：5；Only meteorology, time and station are inputs; other same-hour pollutant concentrations excluded. 处理：remove。
- `station_time_grain`：12；12 stations x 35064 hours; same timestamp grouped across stations, and station saved as entity_id for separate station-held-out protocols. 处理：preserve。
- `identical_input_different_labels`：0；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：0；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 551 — Gas Turbine CO and NOx Emission Data Set

建议划分：years 2011-2013 train/development, 2014-2015 test; use source order within year; same family as UCI294。
- `source_family_overlap`：1；Same power plant as first-batch CCPP; both datasets share dataset_family=turkish_power_plant. No exact cross-source timestamps available. 处理：same_family_as_uci294。
- `emissions_units`：2；Official variable table lists both CO and NOx in mg/m^3, not ppm. 处理：use_mg_per_m3。
- `identical_input_different_labels`：0；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：14；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 440 — SGEMM GPU kernel performance

建议划分：group_by_kernel_configuration; repeated run values remain together。
- `four_repeat_measurements`：241600；One mean-runtime target per configuration. Original four times saved in target_observations, never included in prompt. No fabricated variance label. 处理：arithmetic_mean_target。
- `readme_internal_count_conflict`：241600；Actual CSV has 241600 configurations; a paragraph of original Readme incorrectly says 261400. 处理：use_file_count。
- `identical_input_different_labels`：0；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：0；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 332 — Online News Popularity

建议划分：chronological_by_publication_date; variable exposure horizon remains a limitation。
- `potential_future_share_features`：12；Nine kw_* and three self_reference_* share-derived features excluded because their as-of-time provenance is not verifiable. 处理：remove。
- `full_corpus_topic_features`：5；LDA scores omitted because fitted-corpus provenance is not established. 处理：remove。
- `variable_exposure_horizon`：39644；Shares measured at collection with varying article ages. This is not a fixed 7-day/30-day future popularity label. 处理：limit_claim。
- `identical_input_different_labels`：0；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：0；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 555 — Apartment for Rent Classified

建议划分：group_by_listing_id and available property-location proxy, plus identical cleaned descriptions; city/time holdout recommended。
- `source_100k_actual_count`：99492；100K release contains 99492 rows. 10K file is archived but not concatenated. 处理：use_larger_file_only。
- `numeric_text_redaction`：168848；Removed financial clauses plus all digit sequences and spelled-out number words from title/body, using no target labels. Numeric property details remain in structured fields. Raw text preserved in archive. 处理：conservative_label_independent_redaction。
- `price_and_identifiers_removed`：1；price_display, address, listing ID, source and pricing/currency fields do not enter input; category/currency/period enforced by selection. 处理：allowlist_features。
- `listing_identity_limit`：91549；Exact listing IDs, available address/geographic proxies and identical cleaned descriptions are unioned; this is not verified building identity and may over-group. 处理：preserve_proxy_grouping。
- `identical_input_different_labels`：186；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：149；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 162 — Forest Fires

建议划分：spatial_grid_groups; event identities/full dates unavailable。
- `zero_and_skewed_target`：247；Zero burned areas retained. No log1p is applied, and large legitimate fires are not removed as outliers. 处理：retain_original_hectares。
- `identical_input_different_labels`：8；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：4；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。
### 925 — Infrared Thermography Temperature

建议划分：group_by_SubjectID across both devices; demographic range limited。
- `original_release_scope`：2029；Original release: FLIR 1020 + ICI 1009 device records from 1026 subjects, not 2029 independent people. This extends the UCI 1020-row subset. 处理：use_both_devices。
- `facial_round_aggregation`：27；26 facial temperature descriptors plus blackbody offset averaged over available rounds. All-round-missing remains null. Both oral thermometer readings, ID, Time, Date and Cosmetics excluded. 处理：within_record_available_mean。
- `oral_targets_no_disagreement`：1026；Monitor-mode labels match for every subject measured on both devices. Other oral target never enters input. 处理：patient_grouping。
- `identical_input_different_labels`：0；Different labels for identical prepared inputs are retained, not averaged (except the explicitly defined SGEMM mean target). 处理：retain_and_group。
- `duplicate_task_examples`：0；Store one identical task/input/label and retain every source occurrence in source_refs/duplicate_count. 处理：collapse_preserve_source_refs。

## 第一批原有处理说明（保留）


- 保留官方压缩包、解压文件、API元数据和SHA-256校验和；CCPP只读取第一个工作表，已验证其余4个是相同记录的不同排序。
- 葡萄酒合并红白子集并加入类型；学生保留两门课程；供暖/制冷和两种UPDRS分别展开为标量回归任务。
- 无任何目标插补、裁剪、标准化或对数再变换。QSAR目标保留原始负对数尺度。缺失特征以null表达。
- 合并完全相同的任务/输入/标签；同输入不同标签保留，分在同一个group_id。重复样本可能是真实重复测量，因此保留来源和multiplicity以便恢复权重。
- Metro的字符串None表示非节日，不能当缺失；10条0K温度转为null；1条9831.3毫米降雨保留但标记，使用严格质量子集时可排除带quality_flags的记录。
- Abalone的2条零高度转为null；存储值按原尺度保留。没有把缩放数值误标为原始毫米/克。
- 服装生产率37条标签超过1，保留并标记；506条WIP缺失集中在finishing部门，没有填成0。
- Parkinsons标签是线性插值评分；所有声音记录按42名患者分组。学生使用官方13字段匹配代理，同一代理可能对应多个记录，不能声称已恢复精确学生ID。
- 时间任务定义为给定同期观测条件的估计；没有宣称使用当时未知的实测天气进行未来预测。学生去掉G1/G2和累计缺勤，但调查时间未充分记录，不能宣称严格学年初预测。
- group_id只控制已知关联；未来还需先做dataset_family级留出，再对训练池采用时间/分组划分。当前split均为unassigned；不要直接随机拆开合并文件。
- Superconductivity prompt较长，未截断。记录字符长度而非未经测量的token数；训练前应使用实际Jev tokenizer核查上下文长度。

## 逐数据集检查结果

### 165 — Concrete Compressive Strength

[官方来源](https://archive.ics.uci.edu/dataset/165/concrete+compressive+strength)；建议划分：group_by_mixture。

- `identical_input_different_labels`：9；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：25；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 242 — Energy Efficiency

[官方来源](https://archive.ics.uci.edu/dataset/242/energy+efficiency)；建议划分：group_by_building_geometry。

- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 294 — Combined Cycle Power Plant

[官方来源](https://archive.ics.uci.edu/dataset/294/combined+cycle+power+plant)；建议划分：group_by_identical_input; not a temporal benchmark。

- `reshuffled_workbook_copies`：4；5 sheets each contain the same 9568 records in different orders. 处理：use_only_first_sheet。
- `relative_humidity_above_100`：55；Small exceedance may reflect measurement/rounding; not automatically clipped. 处理：retain_and_flag。
- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：41；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 291 — Airfoil Self-Noise

[官方来源](https://archive.ics.uci.edu/dataset/291/airfoil+self+noise)；建议划分：group_by_experiment_condition。

- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 243 — Yacht Hydrodynamics

[官方来源](https://archive.ics.uci.edu/dataset/243/yacht+hydrodynamics)；建议划分：group_by_hull。

- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 1 — Abalone

[官方来源](https://archive.ics.uci.edu/dataset/1/abalone)；建议划分：group_by_identical_input。

- `source_scaled_features`：4177；Original documentation states continuous features were scaled; prompts do not label them as unscaled mm/g. 处理：retain_source_scale。
- `nonpositive_height`：2；Physical height zero is invalid; preserve label and raw source. 处理：replace_feature_with_null。
- `height_exceeds_length`：1；Potential outliers are not silently clipped or deleted. 处理：retain_and_flag。
- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 9 — Auto MPG

[官方来源](https://archive.ics.uci.edu/dataset/9/auto+mpg)；建议划分：group_by_exact_car_name; model-family matches not guaranteed。

- `missing_horsepower`：6；Six missing horsepower values; no all-data mean imputation. 处理：retain_as_null。
- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 477 — Real Estate Valuation

[官方来源](https://archive.ics.uci.edu/dataset/477/real+estate+valuation+data+set)；建议划分：chronological_by_transaction_date plus property proxy groups。

- `identical_input_different_labels`：20；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 29 — Computer Hardware

[官方来源](https://archive.ics.uci.edu/dataset/29/computer+hardware)；建议划分：group_by_identical_configuration。

- `identical_input_different_labels`：15；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 87 — Servo

[官方来源](https://archive.ics.uci.edu/dataset/87/servo)；建议划分：group_by_configuration。

- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 464 — Superconductivty Data

[官方来源](https://archive.ics.uci.edu/dataset/464/superconductivty+data)；建议划分：group_by_composition。

- `aligned_composition_table`：21263；Verified exact rowwise target alignment; unique_m.csv is not appended as independent samples. Composition fractions rounded to 12 decimals for grouping. 处理：use_for_grouping_only。
- `identical_input_different_labels`：2374；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：66；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 504 — QSAR fish toxicity

[官方来源](https://archive.ics.uci.edu/dataset/504/qsar+fish+toxicity)；建议划分：group_by_identical_descriptors; not scaffold holdout。

- `identical_input_different_labels`：84；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：1；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 186 — Wine Quality

[官方来源](https://archive.ics.uci.edu/dataset/186/wine+quality)；建议划分：group_by_identical_inputs; red and white are one dataset family。

- `red_white_subsets`：6497；Red=1599; white=4898. Treat as one source family. 处理：combine_with_wine_type。
- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：1177；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 320 — Student Performance

[官方来源](https://archive.ics.uci.edu/dataset/320/student+performance)；建议划分：group_by_official_student_proxy across both courses。

- `student_identity_proxy_collision`：16；Official 13-field matching key is not unique within a course. It is a leakage-control proxy, not an exact student identity. 处理：conservatively_group。
- `previous_grades_and_absences`：1044；G1/G2 and cumulative absences removed. Survey timing is not known, so this is not advertised as a verified start-of-year forecast. 处理：remove_features。
- `identical_input_different_labels`：1；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：1；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 189 — Parkinsons Telemonitoring

[官方来源](https://archive.ics.uci.edu/dataset/189/parkinsons+telemonitoring)；建议划分：group_by_patient。

- `repeated_patients`：42；All recordings and both outcomes for a patient share a split group. 处理：group_by_patient。
- `interpolated_labels`：5875；Original names file explicitly describes both UPDRS scores as linearly interpolated, not independently observed at every voice recording. 处理：retain_and_disclose。
- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 597 — Productivity Prediction of Garment Employees

[官方来源](https://archive.ics.uci.edu/dataset/597/productivity+prediction+of+garment+employees)；建议划分：chronological_by_date。

- `target_exceeds_documented_0_1_range`：37；Observed productivity can exceed 1; do not clip labels or constrain output to [0,1]. 处理：retain_and_flag。
- `missing_wip`：506；Missing WIP is confined to finishing department; do not replace with zero. 处理：retain_as_null。
- `ambiguous_feature_timing`：1197；Remove incentive and idle variables. Remaining production measures are used for conditional estimation, not claimed available pre-shift. 处理：define_retrospective_task。
- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 275 — Bike Sharing

[官方来源](https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset)；建议划分：chronological_by_date。

- `direct_target_components`：17379；Verified casual + registered == cnt on every row. 处理：remove_casual_and_registered。
- `website_row_count_mismatch`：17379；Actual hour.csv has 17379 rows; API reports 17389. Daily aggregates are excluded. 处理：use_actual_file_count。
- `normalization_and_season_documentation_conflict`：17379；Website and archive disagree on temperature normalization and season code descriptions. No inverse conversion is performed; season is dropped as redundant to date. 处理：retain_normalized_values_and_drop_season。
- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：0；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

### 492 — Metro Interstate Traffic Volume

[官方来源](https://archive.ics.uci.edu/dataset/492/metro+interstate+traffic+volume)；建议划分：chronological_by_timestamp; same timestamp never crosses splits。

- `literal_None_is_not_missing`：48143；Read CSV with keep_default_na=False; None is a valid no-holiday category. 处理：decode_as_no_holiday。
- `invalid_kelvin`：10；Zero Kelvin is invalid ambient temperature, not a missing target. 处理：replace_feature_with_null。
- `extreme_rainfall`：1；One reported hourly rainfall is 9831.3 mm; flagged for review, not silently winsorized. 处理：retain_and_flag。
- `multiple_rows_per_timestamp`：7629；Traffic labels agree within each timestamp, but some weather values differ; no arbitrary weather aggregation. 处理：retain_distinct_weather_rows_and_group。
- `identical_input_different_labels`：0；Different targets for the same input can represent noise or unobserved variables; they are not averaged or deleted. 处理：retain_labels_and_group。
- `duplicate_task_examples`：17；Identical task/input/label examples are stored once with duplicate_count. This is a deduplication policy, not proof that all originals are erroneous. 处理：collapse_preserve_source_refs。

## 训练前实验追踪预留

本次不启动训练。后续训练前应固定数据版本、分组/时间划分、prompt版本、采样比例与随机种子；记录每任务training/validation同定义指标及step/epoch。优先本地CSV/JSONL或TensorBoard；W&B上传须单独授权。小验证集可全量，大数据集可先固定抽样并记录样本范围与评估成本，在关键checkpoint做全量评估。未执行的指标不会因日志工具自动补算。

