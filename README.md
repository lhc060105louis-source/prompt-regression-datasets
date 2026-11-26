# Prompt Regression Datasets

这个仓库把不同领域的回归任务整理成同一种问答格式，方便训练和评测模型预测数值的能力。每条样本包含一个英文问题（`prompt`）和一个数值答案（`label`）。例如，模型读到混凝土的配比和养护天数后，要预测以 MPa 为单位的抗压强度。同一来源也可以有多个任务，比如用同一栋住宅的建筑参数分别估计供暖负荷和制冷负荷。

English prompts paired with numeric targets for regression research. The full collection contains 61 tasks from 52 sources. [English loading guide and field reference](https://github.com/lhc060105louis-source/prompt-regression-datasets/blob/62c33afd4b6df1638af87b0a62ed33781501657d/README.md#load-the-data)

| GitHub 分支 | 数据源 | 回归任务 | 样本数 |
|---|---:|---:|---:|
| [`main` · v2.3.0](https://github.com/lhc060105louis-source/prompt-regression-datasets/tree/main) | 45 | 52 | 1,787,591 |
| [`data/next-domain-expansion` · v2.4.0](https://github.com/lhc060105louis-source/prompt-regression-datasets/tree/data/next-domain-expansion) | 52 | 61 | 2,256,193 |

扩展分支包含主分支的全部数据，另加 7 个来源、9 个任务。以上是已整理和校验的数据量，目前尚未进行模型训练。

[查找任务](#任务目录) · [读取样本](#读取样本) · [训练与评测划分](#训练与评测划分) · [校验与复现](#校验与复现)

## 读取样本

要使用全部 61 个任务，下载扩展分支。数据已按 UTF-8 JSONL 分片并用 gzip 压缩，读取只需要 Python 标准库。

```sh
git clone --branch data/next-domain-expansion https://github.com/lhc060105louis-source/prompt-regression-datasets.git
cd prompt-regression-datasets
```

下面从住宅能耗数据中读取一条供暖负荷样本。同一数据源有多个预测目标时，用完整的 `task_id` 选择任务。

```python
from scripts.read_dataset import iter_records

sample = next(
    row for row in iter_records(dataset_id="uci_242")
    if row["task_id"] == "uci_242/heating_load"
)
print(sample["prompt"])  # 给模型的英文问题，含字段说明和输入数据
print(sample["label"])   # 用于监督或评测的数值答案
```

省略 `dataset_id` 可以按清单顺序读取当前分支的全部样本。每个数据目录的 `preview.jsonl` 都可以直接打开，`metadata.json` 记录了各任务的字段、单位和处理方法。[样本格式](schema.json) · [完整提问示例](docs/examples.md)

## 任务目录

下表每行对应一个实际发布的 `task_id`。点击数据源名称可查看样本和分片。标有 **扩展** 的 9 行仅在 v2.4.0 提供。样本数按任务统计，同一建筑、英文词或受试者可以对应多条样本。

[工程与材料](#工程与材料) · [能源与环境](#能源与环境) · [交通与城市](#交通与城市) · [生命科学与健康](#生命科学与健康) · [经济与农业](#经济与农业) · [语言与社会](#语言与社会) · [计算与定位](#计算与定位) · [天文与物理](#天文与物理)

### 工程与材料

| 数据源与任务 ID | 输入 | 预测目标 | 单位或量表 | 样本数 |
|---|---|---|---|---:|
| [混凝土抗压强度](datasets/uci_165_concrete_strength)<br>`uci_165/compressive_strength` | 水泥、矿渣、水、外加剂和骨料等配比，养护龄期 | 指定龄期的抗压强度 | MPa | 1,005 |
| [翼型风洞噪声](datasets/uci_291_airfoil_noise)<br>`uci_291/sound_pressure_level` | 频率、迎角、翼弦长度、来流速度和边界层位移厚度 | 风洞测得的标度声压级 | dB | 1,503 |
| [帆船水动力](datasets/uci_243_yacht_resistance)<br>`uci_243/residuary_resistance_per_displacement_weight` | 浮心纵向位置、船体几何系数和弗劳德数 | 单位排水重量的剩余阻力 | 无量纲，原始尺度 | 308 |
| [伺服系统模拟](datasets/uci_87_servo_response)<br>`uci_87/servo_response` | 电机和丝杠类别、两项增益设置（pgain、vgain） | 伺服系统的响应值（上升时间） | 原始响应单位未注明 | 167 |
| [超导材料](datasets/uci_464_superconductivity)<br>`uci_464/critical_temperature` | 元素种数及组成元素的原子质量、电离能、热导率等统计量 | 已知超导材料的临界温度 | K | 21,193 |
| [FreeSolv 水合自由能](datasets/freesolv_freesolv)<br>`freesolv/experimental_hydration_free_energy` | 分子的规范化异构 SMILES 表示 | 实验测得的水合自由能 | kcal/mol | 642 |
| [JARVIS / Matbench 二维晶体](datasets/jdft2d_jdft2d)<br>`jdft2d/dft_exfoliation_energy` | 晶格向量、各原子的元素与分数坐标、周期边界 | 密度泛函理论计算的每原子剥离能 | meV/原子 | 636 |
| [NASA C-MAPSS 涡扇发动机](datasets/cmapss_cmapss)<br>`cmapss/remaining_useful_life` | 模拟场景及最近 30 个运行周期的工况和传感器数据 | 从观测窗口末端到故障的剩余寿命 | 运行周期 | 15,627 |
| [FDM 3D 打印实验](datasets/fdm_aktepe_fdm) · **扩展**<br>`fdm_aktepe/mean_peak_tensile_load` | 打印舱类型、材料、层厚、填充率、填充图案和打印速度 | 同一配置下三个试件的平均峰值拉伸载荷 | N | 500 |
| [UCI 同步电机](datasets/uci_607_motor) · **扩展**<br>`uci_607/excitation_current` | 负载电流和功率因数 | 同一工况下的励磁电流 | A | 557 |

### 能源与环境

| 数据源与任务 ID | 输入 | 预测目标 | 单位或量表 | 样本数 |
|---|---|---|---|---:|
| [住宅能耗模拟](datasets/uci_242_energy_efficiency)<br>`uci_242/heating_load` | 建筑几何尺寸、朝向、玻璃面积及其分布 | 模拟住宅的供暖负荷 | 原始负荷单位，UCI 未注明 | 768 |
| [住宅能耗模拟](datasets/uci_242_energy_efficiency)<br>`uci_242/cooling_load` | 建筑几何尺寸、朝向、玻璃面积及其分布 | 模拟住宅的制冷负荷 | 原始负荷单位，UCI 未注明 | 768 |
| [联合循环电厂](datasets/uci_294_combined_cycle_power)<br>`uci_294/net_electrical_power` | 同一时段的环境温度、排气真空度、大气压和相对湿度 | 机组满负荷时的小时平均净发电功率 | MW | 9,527 |
| [住宅家电能耗](datasets/uci_374_appliances_energy)<br>`uci_374/appliance_energy` | 时间、各处温湿度、照明能耗及室外天气 | 同一 10 分钟内家电耗电量 | Wh（每条记录覆盖 10 分钟） | 19,735 |
| [北京多站点空气质量](datasets/uci_501_beijing_pm25)<br>`uci_501/pm25_concentration` | 站点、时间及同小时的温度、气压、降水、风况等 | 该站点当小时的 PM2.5 浓度 | µg/m³ | 412,029 |
| [燃气轮机排放](datasets/uci_551_gas_turbine_emissions)<br>`uci_551/carbon_monoxide` | 同一时段的环境温湿度、气压、轮机工况及能量产出 | 烟气中一氧化碳（CO）浓度 | mg/m³ | 36,726 |
| [燃气轮机排放](datasets/uci_551_gas_turbine_emissions)<br>`uci_551/nitrogen_oxides` | 同一时段的环境温湿度、气压、轮机工况及能量产出 | 烟气中氮氧化物（NOx）浓度 | mg/m³ | 36,726 |
| [葡萄牙 Montesinho 森林火灾](datasets/uci_162_forest_fires)<br>`uci_162/burned_forest_area` | 位置、月份、星期、气象和火险指数 | 记录的过火面积（含零值） | 公顷 | 513 |
| [CAMELS-GB 英国流域](datasets/camels_gb_camels_gb)<br>`camels_gb/next_day_specific_discharge` | 流域属性及连续 7 天的气象和径流记录，历史截至月末预测起点的前一天 | 月末预测起点次日的单位面积流量（径流深） | mm/日 | 324,656 |
| [UCI 温度调制气体传感器](datasets/uci_487_gas)<br>`uci_487/mean_co_concentration` | 五分钟内 14 个传感器的电阻统计值和平均温湿度 | 同期实验室气室中一氧化碳的平均浓度 | ppm | 1,300 |

### 交通与城市

| 数据源与任务 ID | 输入 | 预测目标 | 单位或量表 | 样本数 |
|---|---|---|---|---:|
| [Auto MPG 汽车油耗](datasets/uci_9_auto_mpg)<br>`uci_9/city_cycle_fuel_economy` | 气缸数、排量、马力、车重、加速特性、车型年份和产地 | 城市工况下每加仑燃料的行驶里程 | 英里/加仑 | 398 |
| [新北市新店区房产估值](datasets/uci_477_real_estate)<br>`uci_477/house_price_per_unit_area` | 交易日期、屋龄、距捷运站距离、附近便利店数和经纬度 | 房屋单位面积成交价 | 万新台币/坪 | 414 |
| [Capital Bikeshare 共享单车](datasets/uci_275_bike_sharing)<br>`uci_275/hourly_bike_rentals` | 日期、小时、工作日及同时段的天气记录 | 该小时总租借次数 | 次/小时 | 17,379 |
| [I-94 州际高速车流](datasets/uci_492_metro_traffic)<br>`uci_492/hourly_traffic_volume` | 当地时间、节假日、同期气温、降雨、降雪和云量 | 明尼阿波利斯－圣保罗监测点西向车流量 | 辆/小时 | 48,187 |
| [1985 年汽车规格](datasets/uci_10_automobile_price)<br>`uci_10/automobile_price` | 车型、尺寸、发动机、油耗等规格 | 车辆价格 | 原始价格单位（币种未注明） | 201 |
| [首尔共享单车](datasets/uci_560_seoul_bike)<br>`uci_560/hourly_seoul_bike_rentals` | 日期与小时、当时天气、节假日和运营状态 | 该小时的租借次数 | 次/小时 | 8,760 |
| [美国公寓租房广告](datasets/uci_555_apartment_rent)<br>`uci_555/monthly_apartment_rent` | 去除金额的房源文本、面积、房间数、设施和位置 | 挂牌月租 | 美元/月 | 99,277 |

### 生命科学与健康

| 数据源与任务 ID | 输入 | 预测目标 | 单位或量表 | 样本数 |
|---|---|---|---|---:|
| [鲍鱼形态测量](datasets/uci_1_abalone_rings)<br>`uci_1/shell_ring_count` | 性别或幼体类别、壳尺寸及身体各部分重量 | 贝壳上的生长环数 | 环 | 4,177 |
| [QSAR 鱼类急性毒性](datasets/uci_504_fish_toxicity)<br>`uci_504/acute_fish_toxicity` | 六项分子描述符，包括原子类型计数和亲脂性 | 化合物对胖头鱥的 96 小时急性毒性 | LC₅₀ 的负对数，浓度以 mol/L 计 | 907 |
| [帕金森病远程监测](datasets/uci_189_parkinsons)<br>`uci_189/motor_updrs` | 嗓音频率与振幅抖动、噪声比等声学特征 | UPDRS 运动分量表评分，按测量时间插值 | UPDRS 分 | 5,875 |
| [帕金森病远程监测](datasets/uci_189_parkinsons)<br>`uci_189/total_updrs` | 嗓音频率与振幅抖动、噪声比等声学特征 | UPDRS 总评分，按测量时间插值 | UPDRS 分 | 5,875 |
| [蛋白质三级结构](datasets/uci_265_protein_structure)<br>`uci_265/protein_structure_rmsd` | 候选结构的 9 项描述量，包括表面积、残基暴露和空间分布 | 候选结构的均方根偏差（RMSD） | 原始 RMSD 单位（未注明） | 44,019 |
| [面部红外测温](datasets/uci_925_infrared_temperature)<br>`uci_925/oral_monitor_temperature` | 面部各区域红外温度、仪器型号、环境和受试者特征 | 口腔温度计在监测模式下的读数 | °C | 2,029 |
| [GB1 四位点结合实验](datasets/gb1_gb1)<br>`gb1/relative_igg_fc_binding_fitness` | 同一 GB1 蛋白背景下 4 个实验位点的氨基酸 | 相对参考序列的 IgG-Fc 结合适应度 | 无量纲 | 149,361 |
| [OpenIPF 力量举](datasets/openipf_openipf) · **扩展**<br>`openipf/best_deadlift` | 成年选手的年龄、称重体重、参赛性别组别及赛事信息 | 成年 Raw 组三项赛中，前三次硬拉尝试的最佳有效重量 | kg | 312,215 |
| [Fukuchi 跑步生物力学](datasets/fukuchi_running_fukuchi) · **扩展**<br>`fukuchi_running/vertical_force_p95` | 跑台速度、身高、体重、跑步水平及每周训练次数 | 本次试验中垂直地面反作用力的第 95 百分位数 | N | 101 |
| [BIDMC 脉搏波与呼吸](datasets/bidmc_ppg_bidmc) · **扩展**<br>`bidmc_ppg/manual_respiratory_rate` | 一分钟脉搏波的 300 个连续分段均值 | 该分钟内两名标注者记录的平均呼吸次数 | 次/分钟 | 424 |

### 经济与农业

| 数据源与任务 ID | 输入 | 预测目标 | 单位或量表 | 样本数 |
|---|---|---|---|---:|
| [葡萄酒感官质量](datasets/uci_186_wine_quality)<br>`uci_186/wine_quality_score` | 红白葡萄酒类别及酸度、残糖、密度、酒精度等理化指标 | 葡萄牙绿酒的感官质量评分 | 0 至 10 分 | 5,320 |
| [制衣班组生产率](datasets/uci_597_garment_productivity)<br>`uci_597/actual_productivity` | 日期、部门、班组目标、在制品、加班和人员配置 | 班组实际生产率 | 原始比值，可大于 1 | 1,197 |
| [UCI 稻作调查](datasets/uci_1186_paddy)<br>`uci_1186/paddy_output_kg` | 种植面积、品种、田间管理和生长期天气 | 本次种植的稻谷总产量 | kg | 2,338 |
| [FRED-MD 美国宏观经济](datasets/fred_md_fred)<br>`fred_md/cpiaucsl` | 起始月份及连续 24 个月的 CPI 和失业率 | 下月经季节调整的美国综合消费价格指数 | 指数（1982 至 1984 年均值为 100） | 788 |
| [FRED-MD 美国宏观经济](datasets/fred_md_fred)<br>`fred_md/unrate` | 起始月份及连续 24 个月的 CPI 和失业率 | 下月经季节调整的美国失业率 | % | 788 |
| [FAOSTAT 谷物单产](datasets/faostat_qcl_faostat)<br>`faostat_qcl/next_annual_crop_yield` | 国家或地区、作物、目标年份及前三年单产 | 该作物下一年的单位收获面积产量 | kg/ha | 21,311 |
| [UCI 每周零售数据](datasets/uci_396_retail) · **扩展**<br>`uci_396/next_week_purchased_quantity` | 商品代码、待预测周序号和前八周购买量 | 该商品下一周的购买量 | 件/周 | 35,684 |

### 语言与社会

| 数据源与任务 ID | 输入 | 预测目标 | 单位或量表 | 样本数 |
|---|---|---|---|---:|
| [葡萄牙中学生成绩](datasets/uci_320_student_performance)<br>`uci_320/final_grade/mat` | 学生、家庭、学校和学习情况，不含前两期成绩 | 数学期末成绩 | 0 至 20 分 | 395 |
| [葡萄牙中学生成绩](datasets/uci_320_student_performance)<br>`uci_320/final_grade/por` | 学生、家庭、学校和学习情况，不含前两期成绩 | 葡萄牙语期末成绩 | 0 至 20 分 | 648 |
| [在线新闻传播](datasets/uci_332_news_popularity)<br>`uci_332/article_share_count` | 发布日期及星期、频道，以及文章的篇幅、链接和情感统计 | 采集时文章已累计的分享次数 | 次 | 39,644 |
| [CompLex 2.0 词汇复杂度](datasets/complex_complex)<br>`complex/lexical_complexity` | 英语句子、待评词或短语、词项类型及语料来源 | 该词或短语在句中的复杂度评分 | 0 至 1 分 | 10,800 |
| [Empathic Reactions 新闻读后感](datasets/empathy_empathy)<br>`empathy/empathy` | 读者读完新闻后写的英文短文 | 作者自评的共情关切程度 | 1 至 7 分 | 1,860 |
| [Empathic Reactions 新闻读后感](datasets/empathy_empathy)<br>`empathy/distress` | 读者读完新闻后写的英文短文 | 作者自评的个人痛苦程度 | 1 至 7 分 | 1,860 |
| [ASAP 2.0 作文评分](datasets/asap2_asap2)<br>`asap2/holistic_essay_score` | 学生的英文议论文、写作主题及可用的题目要求 | 人工整体评分 | 1 至 6 分（有序等级） | 24,728 |
| [Lancaster 词汇感知](datasets/lancaster_sensorimotor_lancaster) · **扩展**<br>`lancaster_sensorimotor/auditory_strength` | 无上下文的英文单词或短语 | 词义与听觉关联强度的人工平均评分 | 0 至 5 分 | 39,707 |
| [Lancaster 词汇感知](datasets/lancaster_sensorimotor_lancaster) · **扩展**<br>`lancaster_sensorimotor/visual_strength` | 无上下文的英文单词或短语 | 词义与视觉关联强度的人工平均评分 | 0 至 5 分 | 39,707 |
| [Lancaster 词汇感知](datasets/lancaster_sensorimotor_lancaster) · **扩展**<br>`lancaster_sensorimotor/haptic_strength` | 无上下文的英文单词或短语 | 词义与触觉关联强度的人工平均评分 | 0 至 5 分 | 39,707 |

### 计算与定位

| 数据源与任务 ID | 输入 | 预测目标 | 单位或量表 | 样本数 |
|---|---|---|---|---:|
| [计算机硬件性能](datasets/uci_29_computer_hardware)<br>`uci_29/published_relative_performance` | 时钟周期、内存容量范围、缓存和通道数 | 公布的计算机相对性能分数 | 相对性能分 | 209 |
| [SGEMM GPU 性能](datasets/uci_440_sgemm_runtime)<br>`uci_440/mean_kernel_runtime` | 固定 GTX 680 上矩阵乘法内核的 14 个配置参数 | 相同配置运行 4 次的平均耗时 | ms | 241,600 |
| [拍卖模型验证](datasets/uci_713_auction)<br>`uci_713/mean_verification_time` | 4 名竞买人的限购数，以及待验证的商品、价格或赢家条件 | 验证该拍卖模型属性的平均运行时间 | ms | 2,043 |
| [视频转码耗时](datasets/uci_335_transcoding)<br>`uci_335/transcoding_time` | 源视频的编码、尺寸、帧与码率统计及目标编码设置 | 源实验平台记录的转码耗时（utime） | s | 68,784 |
| [UJIIndoorLoc 室内定位](datasets/uci_310_uji)<br>`uci_310/map_x` | 一次 Wi-Fi 扫描中各接入点的信号强度 | 扫描位置在校园地图上的 x 坐标 | m | 20,261 |
| [UJIIndoorLoc 室内定位](datasets/uci_310_uji)<br>`uci_310/map_y` | 一次 Wi-Fi 扫描中各接入点的信号强度 | 扫描位置在校园地图上的 y 坐标 | m | 20,261 |

### 天文与物理

| 数据源与任务 ID | 输入 | 预测目标 | 单位或量表 | 样本数 |
|---|---|---|---|---:|
| [SDSS DR17 星系](datasets/sdss_dr17_sdss)<br>`sdss_dr17/galaxy_spectroscopic_redshift` | 五个波段的消光校正星等及其测量误差 | 星系的光谱红移 | 无量纲 | 52,068 |

## 训练与评测划分

| 来源 | 可用的划分 |
|---|---|
| CompLex、ASAP 2.0、NASA C-MAPSS、UJIIndoorLoc（4 个来源） | `split` 保留原发布方提供的分区。各来源提供的分区种类可能不同。 |
| v2.4.0 新增的 7 个来源 | 样本中的 `split` 为 `unassigned`。可按 `sample_id` 关联[建议划分表](splits/batch5/assignments.csv.gz)。例如，同一个词的三个评分放在同一分区，零售数据按预测周先后划分。[各分区样本数](splits/batch5/summary.json) |
| 其余 41 个来源 | `split` 为 `unassigned`。各来源的 `metadata.json` 说明了可用的分组或时间信息，供实验时选择划分。 |

比较未见受试者或新时间段的表现时，应在相应的人群或时间段上留出数据。CompLex 的官方分区仍有部分关联样本跨区，相关标记保存在 `quality_flags`。比较跨领域表现时，各任务应使用各自的量纲报告误差。

## 字段与数据质量

| 字段 | 含义 |
|---|---|
| `prompt`、`input`、`label` | 完整的英文问题、问题中的结构化输入，以及单个数值目标。 |
| `dataset_id`、`task_id`、`dataset_family` | 标识来源、具体预测任务，以及已知的相关数据源家族。 |
| `target_name`、`target_transform` | 目标名称和变换方法。早期记录的单位字段是 `target_unit`，后续批次使用 `unit`。类型字段分别为 `target_type` 和 `type`。 |
| `source_refs`、`duplicate_count` | 原始文件或行号，以及该样本代表的原始出现次数（含首次）。 |
| `group_id`、`split` | 依赖分组和原始分区。部分来源另有 `entity_id`、`time_key` 可用于按实体或时间划分。 |
| `sample_id`、`input_hash`、`quality_flags` | 样本标识、输入哈希及质量标记。 |

缺失的输入保留为 `null`，缺失目标的记录不纳入。小数最多保留 12 位有效数字。英文 `prompt` 已经指明要预测什么。如果使用结构化 `input` 训练多任务模型，请同时提供 `task_id` 或目标说明。SGEMM 的四次运行读数（`target_observations`）和 BIDMC 的两位标注者计数（`annotator_breath_counts`）用于计算标签，应留作核验。

有些目标需要结合同期观测来理解。北京 PM2.5 用当小时天气估计当小时浓度。FRED-MD 的下月预测使用固定版本的历史修订数据。蛋白质结构数据缺少蛋白质 ID，按描述量分组无法验证是否泛化到了新蛋白。燃气轮机排放和联合循环电厂共享 `turkish_power_plant` 数据家族。各来源的限制见对应目录的 `metadata.json`。[v2.3.0 质量报告](reports/quality_report_v2.3.0_zh.md) · [v2.4.0 质量报告](reports/quality_report_v2.4.0_zh.md)

## 校验与复现

在仓库根目录运行以下命令，核对当前分支的文件校验和、解压后的数据哈希及样本数。

```sh
python3 scripts/verify_release.py
```

各分片路径、数量和 SHA-256 见[发布清单](manifest.json)。从原始数据重建时，前 29 个来源使用 [v2.1.0 预处理入口](preprocessing/rebuild.py) 和[依赖清单](preprocessing/requirements.txt)，后续批次各有复现说明。[v2.2.0](preprocessing/batch3/README.md) · [v2.3.0](preprocessing/batch4/README.md) · [v2.4.0](preprocessing/batch5/README.md)

使用数据时，请按来源引用原作者和 DOI，并注明使用的仓库版本或提交号。各来源独立授权，署名和许可见[数据许可清单](DATA_LICENSES.md)。
