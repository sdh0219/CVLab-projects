# 地震灾后区域经济恢复趋势预测数据集说明

1. 项目目标

本项目目标是利用机器学习方法预测地震灾后区域经济恢复趋势，并分析影响恢复速度的关键因素。

研究对象限定为 **地震灾害**。可以将最终数据整理为“地区-年份”面板数据，例如美国县级 `county-year` 数据。模型可以预测灾后 1 年或 2 年 GDP 增长率，也可以预测某地区是否恢复到灾前 GDP 水平。

2. 数据集来源

本项目没有一张公开数据表能同时包含地震、GDP、产业结构、人口、基础设施损毁和政策投入，因此建议构建一个组合数据包。使用以下公开数据源。

| 数据内容 | 数据源 | 用途 |
| --- | --- | --- |
| 地震事件、震级、震源深度、经纬度 | USGS Earthquake Catalog | 构建地震强度、灾害暴露程度等核心特征 |
| 地震灾害声明、受灾县/地区 | FEMA Disaster Declarations Summaries | 确定美国境内被正式认定为地震灾区的区域 |
| 基础设施修复项目、公共援助资金 | FEMA Public Assistance Funded Projects Details | 表示政策投入、基础设施损毁与修复规模 |
| 地区 GDP、行业 GDP | BEA Regional Economic Accounts | 构建经济恢复目标变量和产业结构变量 |
| 人口规模、社会经济变量 | U.S. Census ACS 5-Year Data | 构建人口规模、收入、住房等控制变量 |
| 经济损失、伤亡、重建成本，全球备选 | EM-DAT / NOAA NCEI Significant Earthquake Database | 补充地震经济损失和人员影响数据 |

3. 主要地震数据源：USGS Earthquake Catalog

### 来源

- 数据库名称：USGS Earthquake Catalog
- 机构：United States Geological Survey，USGS
- API 文档：https://earthquake.usgs.gov/fdsnws/event/1/
- CSV 查询示例：

```text
https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&starttime=1990-01-01&endtime=2026-06-16&minmagnitude=5&eventtype=earthquake
```

### 原始字段结构

USGS CSV 常用字段如下：

| 字段名 | 含义 | 建模用途 |
| --- | --- | --- |
| `time` | 地震发生时间 | 提取年份、月份，匹配灾后经济数据 |
| `latitude` | 震中纬度 | 空间匹配地区 |
| `longitude` | 震中经度 | 空间匹配地区 |
| `depth` | 震源深度，单位 km | 地震强度特征 |
| `mag` | 震级 | 受灾程度核心特征 |
| `magType` | 震级类型 | 数据质量或分类辅助字段 |
| `id` | 地震事件编号 | 事件唯一标识 |
| `place` | 地震地点描述 | 辅助识别地区 |
| `type` | 事件类型 | 过滤 `earthquake` |
| `status` | 数据状态 | 数据质量判断 |
| `locationSource` | 位置数据来源 | 数据质量判断 |
| `magSource` | 震级数据来源 | 数据质量判断 |



从 USGS 数据中可以生成以下特征：

| 特征名 | 含义 |
| --- | --- |
| `earthquake_count` | 某地区某年地震次数 |
| `max_magnitude` | 某地区某年最大震级 |
| `avg_magnitude` | 某地区某年平均震级 |
| `min_depth_km` | 某地区某年最浅震源深度 |
| `avg_depth_km` | 某地区某年平均震源深度 |
| `major_earthquake_flag` | 是否发生过大于等于 6.0 级地震 |

4. 受灾区域与政策投入数据：FEMA OpenFEMA

4.1 Disaster Declarations Summaries

- 数据库名称：Disaster Declarations Summaries - v2
- 机构：Federal Emergency Management Agency，FEMA
- 数据页：https://www.fema.gov/openfema-data-page/disaster-declarations-summaries-v2

该数据用于确定哪些州、县被正式纳入灾害声明。筛选条件建议使用：

```text
incidentType = Earthquake
```

常用字段：

| 字段名 | 含义 | 用途 |
| --- | --- | --- |
| `disasterNumber` | FEMA 灾害编号 | 与援助项目表连接 |
| `state` | 州缩写 | 地区匹配 |
| `declarationDate` | 灾害声明日期 | 确定灾后时间点 |
| `incidentType` | 灾害类型 | 筛选地震 |
| `declarationTitle` | 灾害名称 | 辅助说明 |
| `designatedArea` | 受灾县/地区 | 地区匹配 |
| `fipsStateCode` | 州 FIPS 编码 | 构造地区编码 |
| `fipsCountyCode` | 县 FIPS 编码 | 构造地区编码 |
| `incidentBeginDate` | 灾害开始日期 | 时间匹配 |
| `incidentEndDate` | 灾害结束日期 | 时间匹配 |
| `paProgramDeclared` | 是否开放公共援助 | 政策响应变量 |
| `iaProgramDeclared` | 是否开放个人援助 | 政策响应变量 |
| `hmProgramDeclared` | 是否开放减灾援助 | 政策响应变量 |

4.2 Public Assistance Funded Projects Details

- 数据库名称：Public Assistance Funded Projects Details - v1
- 机构：FEMA
- 数据页：https://www.fema.gov/openfema-data-page/public-assistance-funded-projects-details-v1

该数据用于表示灾后政策投入、基础设施修复投入和公共设施损毁程度。

常用字段：

| 字段名 | 含义 | 用途 |
| --- | --- | --- |
| `disasterNumber` | FEMA 灾害编号 | 与灾害声明表连接 |
| `state` | 州缩写 | 地区匹配 |
| `county` | 县名 | 地区匹配 |
| `applicantName` | 申请援助的机构 | 识别地方政府、公共机构 |
| `projectTitle` | 项目名称 | 判断修复内容 |
| `damageCategoryCode` | 损毁类别代码 | 区分道路、桥梁、公共设施等 |
| `damageCategory` | 损毁类别名称 | 基础设施损毁分类 |
| `federalShareObligated` | 联邦承担金额 | 政策投入变量 |
| `totalObligated` | 总批准金额 | 灾后修复规模变量 |

5. 经济与人口数据

5.1 BEA Regional Economic Accounts

- 数据源：Bureau of Economic Analysis，BEA
- 下载页：https://apps.bea.gov/regional/downloadzip.cfm

BEA 提供地区 GDP 和行业 GDP 数据，可用于构建经济恢复目标和产业结构变量。

常用字段：

| 字段名 | 含义 | 用途 |
| --- | --- | --- |
| `GeoFIPS` | 地区 FIPS 编码 | 与 FEMA 县级数据匹配 |
| `GeoName` | 地区名称 | 地区说明 |
| `LineCode` | 指标代码 | 区分总 GDP 和行业 GDP |
| `Description` | 指标名称 | 识别行业 |
| `Unit` | 单位 | 判断金额单位 |
| 年份列 | 各年份数值 | 构建时间序列 |

建议生成的变量：

| 变量名 | 含义 |
| --- | --- |
| `gdp_total` | 地区 GDP 总量 |
| `gdp_growth_next_1y` | 灾后 1 年 GDP 增长率 |
| `gdp_growth_next_2y` | 灾后 2 年 GDP 增长率 |
| `industry_agriculture_share` | 农业占 GDP 比重 |
| `industry_manufacturing_share` | 制造业占 GDP 比重 |
| `industry_construction_share` | 建筑业占 GDP 比重 |
| `industry_services_share` | 服务业占 GDP 比重 |

5.2 U.S. Census ACS 5-Year Data

- 数据源：U.S. Census Bureau
- 数据页：https://www.census.gov/data/developers/data-sets/acs-5year.html

ACS 数据提供县级人口、收入、住房、就业等社会经济变量。

常用变量：

| 字段名 | 含义 | 用途 |
| --- | --- | --- |
| `NAME` | 地区名称 | 地区说明 |
| `state` | 州 FIPS | 地区匹配 |
| `county` | 县 FIPS | 地区匹配 |
| `B01003_001E` | 总人口 | 人口规模 |
| `B19013_001E` | 家庭收入中位数 | 经济基础变量 |
| `B25001_001E` | 住房单元数量 | 居住与建筑暴露变量 |

6. 最终合并数据表设计

建议最终形成一张表：

```text
processed/earthquake_recovery_panel.csv
```

推荐字段结构：

| 字段名 | 类型 | 含义 |
| --- | --- | --- |
| `region_id` | string | 地区编码，建议使用县级 FIPS |
| `region_name` | string | 地区名称 |
| `state` | string | 州 |
| `year` | int | 年份 |
| `disaster_number` | string | FEMA 灾害编号 |
| `earthquake_count` | numeric | 当年地震次数 |
| `max_magnitude` | numeric | 当年最大震级 |
| `avg_magnitude` | numeric | 当年平均震级 |
| `avg_depth_km` | numeric | 平均震源深度 |
| `major_earthquake_flag` | int | 是否发生大地震 |
| `public_assistance_usd` | numeric | FEMA 公共援助金额 |
| `infrastructure_repair_usd` | numeric | 基础设施修复金额 |
| `gdp_total` | numeric | 地区 GDP |
| `gdp_pre_disaster` | numeric | 灾前 GDP |
| `gdp_post_1y` | numeric | 灾后 1 年 GDP |
| `gdp_post_2y` | numeric | 灾后 2 年 GDP |
| `gdp_growth_next_1y` | numeric | 灾后 1 年 GDP 增长率 |
| `gdp_growth_next_2y` | numeric | 灾后 2 年 GDP 增长率 |
| `recovered_2y` | int | 灾后 2 年是否恢复到灾前 GDP 水平 |
| `population` | numeric | 人口规模 |
| `median_household_income` | numeric | 家庭收入中位数 |
| `housing_units` | numeric | 住房数量 |
| `industry_agriculture_share` | numeric | 农业占比 |
| `industry_manufacturing_share` | numeric | 制造业占比 |
| `industry_construction_share` | numeric | 建筑业占比 |
| `industry_services_share` | numeric | 服务业占比 |

7. 预测目标定义

可以设置两类机器学习任务。

回归任务

预测灾后经济恢复趋势：

```text
target = gdp_growth_next_2y
```

含义：预测地震发生后 2 年内地区 GDP 的增长率。

分类任务

预测地区是否恢复：

```text
recovered_2y = 1, if gdp_post_2y >= gdp_pre_disaster
recovered_2y = 0, otherwise
```

含义：如果灾后 2 年 GDP 恢复到或超过灾前水平，则记为 1，否则记为 0。

8. 数据清洗与合并流程

推荐流程：

1. 从 USGS 下载地震事件数据，筛选 `eventtype=earthquake` 和 `mag >= 5`。
2. 根据地震经纬度和县级边界，将地震事件匹配到县。
3. 从 FEMA Disaster Declarations 中筛选 `incidentType = Earthquake`。
4. 使用 `disasterNumber` 将灾害声明和 FEMA 公共援助项目连接。
5. 将 FEMA 项目金额按县和年份汇总，生成政策投入与基础设施修复变量。
6. 从 BEA 获取县级 GDP 与行业 GDP，计算 GDP 增长率和产业结构占比。
7. 从 ACS 获取人口、收入、住房等变量。
8. 按 `region_id + year` 合并为最终面板数据。
9. 构建 `gdp_growth_next_2y` 或 `recovered_2y` 作为预测目标。

9. 数据来源引用

报告中可写为：

```text
地震事件数据来源于美国地质调查局 USGS Earthquake Catalog；
灾害声明和灾后公共援助资金数据来源于 FEMA OpenFEMA；
地区 GDP 和产业结构数据来源于美国经济分析局 BEA Regional Economic Accounts；
人口和社会经济数据来源于美国人口普查局 American Community Survey；
地震损失、伤亡和重建成本可补充参考 EM-DAT 或 NOAA/NCEI Significant Earthquake Database。
```

主要链接：

- USGS Earthquake Catalog：https://earthquake.usgs.gov/fdsnws/event/1/
- FEMA Disaster Declarations Summaries：https://www.fema.gov/openfema-data-page/disaster-declarations-summaries-v2
- FEMA Public Assistance Funded Projects：https://www.fema.gov/openfema-data-page/public-assistance-funded-projects-details-v1
- BEA Regional Data：https://apps.bea.gov/regional/downloadzip.cfm
- Census ACS 5-Year Data：https://www.census.gov/data/developers/data-sets/acs-5year.html
- EM-DAT Documentation：https://doc.emdat.be/
- NOAA/NCEI Significant Earthquake Database：https://www.ngdc.noaa.gov/hazel/view/hazards/earthquake/search

10. 当前已下载的数据文件

本目录已经通过 `download_data.py` 下载并生成了地震相关数据。当前下载范围为：

```text
时间范围：1990-01-01 至 2026-06-16
地震范围：美国及周边区域
USGS 震级阈值：M4.5+
```

本地文件结构如下：

```text
17/
├── README.md
├── requirements.txt
├── download_data.py
├── process_data.py
└── data/
    ├── dataset_summary.json
    ├── raw/
    │   ├── usgs_earthquakes_usa_m45_1990_2026.csv
    │   └── noaa_ncei_significant_earthquakes_usa_1990_2026.csv
    └── processed/
        ├── earthquake_integrated_dataset_2000.csv
        ├── earthquake_integrated_dataset_2000_metadata.json
        ├── usgs_earthquake_yearly_features_usa_m45_1990_2026.csv
        └── significant_earthquake_losses_usa_1990_2026.csv
```

10.1 原始数据文件

| 文件 | 来源 | 行数 | 内容 |
| --- | --- | ---: | --- |
| `data/raw/usgs_earthquakes_usa_m45_1990_2026.csv` | USGS Earthquake Catalog | 8210 | 美国及周边区域 M4.5+ 地震事件 |
| `data/raw/noaa_ncei_significant_earthquakes_usa_1990_2026.csv` | NOAA/NCEI Significant Earthquake Database | 81 | 美国重大地震损失、伤亡、房屋损毁等记录 |

USGS 原始数据主要字段：

| 字段 | 含义 |
| --- | --- |
| `time` | 地震发生时间 |
| `latitude` | 震中纬度 |
| `longitude` | 震中经度 |
| `depth` | 震源深度，单位 km |
| `mag` | 震级 |
| `magType` | 震级类型 |
| `id` | USGS 事件编号 |
| `place` | 地点描述 |
| `type` | 事件类型 |
| `status` | 数据审核状态 |
| `year` | 年份 |
| `month` | 月份 |
| `event_date` | 日期 |

NOAA/NCEI 原始数据主要字段：

| 字段 | 含义 |
| --- | --- |
| `id` | NOAA/NCEI 事件编号 |
| `year` | 年份 |
| `month` | 月份 |
| `day` | 日期 |
| `locationName` | 地震地点 |
| `latitude` | 纬度 |
| `longitude` | 经度 |
| `eqDepth` | 震源深度 |
| `eqMagnitude` | 震级 |
| `intensity` | 烈度 |
| `deaths` | 死亡人数 |
| `injuries` | 受伤人数 |
| `damageMillionsDollars` | 经济损失，单位为百万美元 |
| `housesDestroyed` | 房屋毁坏数量 |
| `housesDamaged` | 房屋受损数量 |

10.2 处理后数据文件

| 文件 | 行数 | 内容 |
| --- | ---: | --- |
| `data/processed/usgs_earthquake_yearly_features_usa_m45_1990_2026.csv` | 37 | 按年份汇总的地震次数、最大震级、平均震级、平均深度等特征 |
| `data/processed/significant_earthquake_losses_usa_1990_2026.csv` | 81 | 清洗后的重大地震损失数据 |
| `data/processed/earthquake_integrated_dataset_2000.csv` | 2000 | 整合后的 2000 行建模数据 |

年度地震特征表字段：

| 字段 | 含义 |
| --- | --- |
| `year` | 年份 |
| `earthquake_count` | 当年地震次数 |
| `max_magnitude` | 当年最大震级 |
| `avg_magnitude` | 当年平均震级 |
| `min_depth_km` | 当年最浅震源深度 |
| `avg_depth_km` | 当年平均震源深度 |
| `major_earthquake_flag` | 当年是否出现 6.0 级及以上地震 |

重大地震损失表字段：

| 字段 | 含义 |
| --- | --- |
| `noaa_event_id` | NOAA/NCEI 事件编号 |
| `year` | 年份 |
| `location_name` | 地点 |
| `area` | 州或区域缩写 |
| `latitude` | 纬度 |
| `longitude` | 经度 |
| `depth_km` | 震源深度 |
| `magnitude` | 震级 |
| `intensity` | 烈度 |
| `deaths` | 死亡人数 |
| `injuries` | 受伤人数 |
| `damage_million_usd` | 经济损失，单位为百万美元 |
| `houses_destroyed` | 房屋毁坏数量 |
| `houses_damaged` | 房屋受损数量 |

10.3 重新下载方法

安装依赖：

```powershell
pip install -r requirements.txt
```

重新下载数据：

```powershell
python download_data.py
```

调整 USGS 震级阈值，例如下载 M5.0+：

```powershell
python download_data.py --min-magnitude 5.0
```

## 11. 2000 行整合数据集

已经生成的整合数据文件为：

```text
data/processed/earthquake_integrated_dataset_2000.csv
```

该文件由 `process_data.py` 生成，共 **2000 行、34 列**。其中：

- 1000 行匹配到 NOAA/NCEI 同州同年重大地震损失记录；
- 1000 行作为未匹配重大损失记录的对照样本；
- 每一行对应一个真实 USGS 地震事件；
- 损失、伤亡、房屋损毁字段来自 NOAA/NCEI 按 `area + year` 聚合后的结果。

### 11.1 数据处理代码

处理代码文件：

```text
process_data.py
```

运行方式：

```powershell
python process_data.py
```

重新生成 2000 行数据：

```powershell
python process_data.py --limit 2000
```

如果需要生成其他数量，例如 3000 行：

```powershell
python process_data.py --limit 3000
```

### 11.2 整合逻辑

整合流程如下：

1. 读取 `data/raw/usgs_earthquakes_usa_m45_1990_2026.csv`。
2. 从 USGS 的 `place` 字段中提取州或地区缩写，例如 `California` 转为 `CA`。
3. 读取 `data/processed/significant_earthquake_losses_usa_1990_2026.csv`。
4. 将 NOAA/NCEI 损失数据按 `area + year` 聚合。
5. 读取 `data/processed/usgs_earthquake_yearly_features_usa_m45_1990_2026.csv`。
6. 按 `year` 合并年度地震强度特征。
7. 按 `area + year` 合并重大地震损失、伤亡和房屋损毁特征。
8. 使用固定随机种子 `42` 抽样生成 2000 行数据，保证结果可复现。

### 11.3 整合后主要字段

| 字段 | 含义 |
| --- | --- |
| `sample_id` | 样本编号 |
| `usgs_event_id` | USGS 地震事件编号 |
| `event_date` | 地震日期 |
| `year` | 年份 |
| `month` | 月份 |
| `area` | 州或地区缩写 |
| `place_name` | 地震地点描述 |
| `latitude` | 震中纬度 |
| `longitude` | 震中经度 |
| `depth_km` | 震源深度，单位 km |
| `magnitude` | 震级 |
| `magnitude_type` | 震级类型 |
| `year_earthquake_count` | 当年地震次数 |
| `year_max_magnitude` | 当年最大震级 |
| `year_avg_magnitude` | 当年平均震级 |
| `year_avg_depth_km` | 当年平均震源深度 |
| `year_major_earthquake_flag` | 当年是否出现 6.0 级及以上地震 |
| `noaa_significant_event_count` | 同州同年 NOAA/NCEI 重大地震记录数 |
| `noaa_deaths_sum` | 同州同年地震死亡人数合计 |
| `noaa_injuries_sum` | 同州同年地震受伤人数合计 |
| `noaa_damage_million_usd_sum` | 同州同年地震经济损失合计，单位为百万美元 |
| `noaa_houses_destroyed_sum` | 同州同年房屋毁坏数量 |
| `noaa_houses_damaged_sum` | 同州同年房屋受损数量 |
| `noaa_max_intensity` | 同州同年最大烈度 |
| `noaa_max_magnitude` | 同州同年 NOAA/NCEI 最大震级 |
| `has_noaa_loss_record` | 是否匹配到重大地震损失记录 |
| `major_event_flag` | 当前事件是否为 6.0 级及以上地震 |
| `shallow_event_flag` | 当前事件是否为 70 km 以内浅源地震 |
| `very_shallow_event_flag` | 当前事件是否为 20 km 以内极浅源地震 |
| `event_severity_score` | 基于震级、深度、损失记录构造的简易严重度评分 |

11.4 元数据

整合数据的元数据文件：

```text
data/processed/earthquake_integrated_dataset_2000_metadata.json
```

其中记录了输出文件名、行数、列数、随机种子、数据来源、年份范围和字段清单。

## 12. 梯度提升树建模数据准备

为了后续使用梯度提升树预测灾后经济恢复周期，已经进一步生成了一个可靠性筛选后的建模数据集：

```text
data/processed/earthquake_rf_recovery_dataset_1500.csv
```

对应元数据文件：

```text
data/processed/earthquake_rf_recovery_dataset_1500.metadata.json
```

推荐输入特征清单：

```text
data/processed/earthquake_recovery_feature_columns.txt
```

### 12.1 筛选原则

该数据集不是简单从 8210 条 USGS 原始地震数据中随意抽样，而是按以下规则筛选：

1. 只保留 USGS 审核状态为 `reviewed` 的地震记录。
2. 只保留震级在 `4.5 <= magnitude <= 10` 范围内的记录。
3. 只保留震源深度 `depth_km >= 0` 的记录。
4. 只保留能从 `place` 字段识别出美国州或地区 `area` 的记录。
5. 只保留能匹配 BEA 州级 GDP 的记录。
6. 为了构造恢复周期标签，必须同时具备：
   - 灾前 1 年 GDP；
   - 灾害当年 GDP；
   - 灾后第 1 年 GDP；
   - 灾后第 2 年 GDP；
   - 灾后第 3 年 GDP。
7. 去除重复的 USGS 地震事件编号。
8. 最后使用固定随机种子 `42` 从合格样本中抽取 1500 条。
9. 为避免单一地区过度主导，限制单一区域最大占比为 60%。

### 12.2 输出变量

梯度提升树预测目标列为：

```text
recovery_cycle_years
```

定义方式：

```text
baseline = 灾前 1 年实际 GDP

如果灾害当年实际 GDP >= baseline，recovery_cycle_years = 0
如果灾后第 1 年实际 GDP >= baseline，recovery_cycle_years = 1
如果灾后第 2 年实际 GDP >= baseline，recovery_cycle_years = 2
如果灾后第 3 年实际 GDP >= baseline，recovery_cycle_years = 3
如果灾后 3 年内仍未恢复，recovery_cycle_years = 4
```

因此，`recovery_cycle_years` 可以理解为灾后经济恢复周期。数值越大，表示恢复越慢。

当前目标分布：

| `recovery_cycle_years` | 含义 | 样本数 |
| ---: | --- | ---: |
| 0 | 当年未低于灾前水平或当年已恢复 | 962 |
| 1 | 1 年内恢复 | 174 |
| 2 | 2 年内恢复 | 103 |
| 3 | 3 年内恢复 | 61 |
| 4 | 3 年内未恢复 | 200 |

### 12.3 输入特征

推荐作为梯度提升树输入 `X` 的字段已经保存到：

```text
data/processed/earthquake_recovery_feature_columns.txt
```

主要包括：

| 特征类型 | 字段示例 |
| --- | --- |
| 地震强度 | `magnitude`, `depth_km`, `major_event_flag`, `shallow_event_flag` |
| 年度地震背景 | `year_earthquake_count`, `year_max_magnitude`, `year_avg_magnitude` |
| 灾害损失 | `noaa_deaths_sum`, `noaa_injuries_sum`, `noaa_damage_million_usd_sum` |
| 房屋损毁 | `noaa_houses_destroyed_sum`, `noaa_houses_damaged_sum` |
| 经济基础 | `gdp_pre_1y`, `gdp_event_year`, `gdp_current_million_usd` |
| 经济趋势 | `gdp_growth_pre_1y`, `gdp_growth_pre_2y`, `gdp_growth_pre_3y`, `gdp_decline_from_pre_pct` |
| 损失比例 | `damage_to_gdp_ratio`, `casualties_sum`, `houses_affected_sum` |
| 产业结构 | `industry_agriculture_share`, `industry_construction_share`, `industry_manufacturing_share`, `industry_private_services_share` |
| 区域与时间 | `area`, `year`, `month` |

### 12.4 不作为输入的字段

以下字段不建议作为随机森林输入：

| 字段 | 原因 |
| --- | --- |
| `sample_id` | 样本编号，没有预测意义 |
| `usgs_event_id` | 事件编号，没有泛化意义 |
| `event_date` | 原始日期，可由 `year` 和 `month` 表示 |
| `place_name` | 自然语言地点文本，暂不直接建模 |
| `gdp_post_1y`, `gdp_post_2y`, `gdp_post_3y` | 未来 GDP，用于构造标签，不能作为输入，否则会数据泄漏 |
| `recovery_cycle_years` | 预测目标，不能作为输入 |

### 12.5 重新生成方法

运行：

```powershell
python prepare_rf_recovery_dataset.py
```

如果需要修改样本数：

```powershell
python prepare_rf_recovery_dataset.py --limit 1500 --output earthquake_rf_recovery_dataset_1500.csv
```

如果需要修改恢复周期窗口，例如改成 5 年：

```powershell
python prepare_rf_recovery_dataset.py --max-horizon 5
```

注意：如果将恢复窗口改成 5 年，样本年份会进一步收窄，因为必须保证灾后 5 年 GDP 都存在。
