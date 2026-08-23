# 项目01：防灾减灾数据孤岛问题调研与 AI 解决方案设计——源码

## 一、源码作用

本源码用于完成项目1“五件套”中的第 2 项：源码。

它会自动完成：

1. 读取多源数据：NOAA 气象、FEMA 灾害声明、USGS 地震、TIGER 道路、SVI 人口脆弱性、消防站、医院、滑坡。
2. 清洗字段：统一日期、经纬度、灾害类型、数据来源等字段。
3. 处理缺失文件：如果某个真实数据文件缺失或下载失败，自动生成同格式模拟兜底数据，并标记 `SIMULATED_FALLBACK`。
4. 数据融合：生成监测数据表、灾害事件表、应急资源表、人口脆弱性表、道路统计表。
5. 可视化：生成项目技术方案和 PPT 可直接使用的结果图。

## 二、推荐目录结构

建议把本文件夹放到项目总目录中，与 `1_数据包` 同级：

```text
项目01_数据孤岛_第X组/
├── 1_数据包/
│   ├── raw_data/
│   ├── processed_data/
│   └── ...
└── 2_源码/
    ├── main.py
    ├── requirements.txt
    ├── README.md
    └── src/
```

如果你的数据不在 `1_数据包`，也可以手动指定数据目录。

## 三、运行方法

进入 `2_源码` 目录后运行：

```bash
pip install -r requirements.txt
python main.py --data_dir "../1_数据包" --output_dir "./outputs"
```

如果你把数据文件都放在当前项目根目录，也可以运行：

```bash
python main.py --data_dir ".." --output_dir "./outputs"
```

Windows 双击也可以使用：

```text
run_all.bat
```

## 四、输入数据文件名兼容

程序会自动递归查找以下文件名：

| 数据类型 | 优先读取文件 |
|---|---|
| 气象 | `weather_noaa_daily_summaries_clean.csv` 或 `daily-summaries-*.csv` |
| FEMA 灾害 | `disaster_fema_la_county_clean.csv` 或 `DisasterDeclarationsSummaries.csv` |
| 地震 | `earthquake_usgs_la_region_clean.csv` 或 `query.csv` |
| 道路 | `tiger_roads_la_county_shapefile.zip` 或 `tl_2024_06037_roads.shp` |
| 人口 SVI | `population_svi_la_county.geojson` 或 `population_svi_la_county_part1.geojson` + `part2.geojson` |
| 消防/EMS | `emergency_fire_ems_stations_la.geojson` |
| 医院 | `emergency_hospitals_la.geojson` |
| 滑坡 | `landslide_cgs_la_county.geojson` |

其中滑坡数据如果下载失败，会自动生成同格式模拟数据。

## 五、输出结果

运行后生成：

```text
outputs/
├── processed/
│   ├── weather_clean.csv
│   ├── fema_disaster_clean.csv
│   ├── earthquake_clean.csv
│   ├── population_svi_clean.csv
│   ├── emergency_resources_clean.csv
│   ├── landslide_clean.csv
│   ├── roads_summary.csv
│   ├── unified_monitoring_daily.csv
│   ├── unified_hazard_events.csv
│   ├── unified_resource_points.csv
│   ├── data_source_status.csv
│   └── data_fusion_summary.csv
│
├── geojson/
│   ├── population_svi_used.geojson
│   ├── emergency_resources_used.geojson
│   ├── landslide_used.geojson
│   └── roads_sample.geojson
│
└── figures/
    ├── weather_monthly_precipitation.png
    ├── earthquake_magnitude_histogram.png
    ├── resource_type_counts.png
    ├── hazard_event_counts.png
    └── data_source_records.png
```

## 六、关于“模拟兜底数据”的说明

本项目优先使用真实数据。只有在真实文件缺失、网页无法直接下载、SSL 报错或 API 不可用时，程序才会生成同格式模拟数据。

模拟数据会在以下字段中明确标记：

```text
source = SIMULATED_FALLBACK
is_simulated = 1
```

因此不会把模拟数据伪装成真实数据。这样做的目的是保证课程作业源码可以完整运行，并体现“跨部门数据孤岛导致接口不稳定、格式不统一、获取困难”的问题。
