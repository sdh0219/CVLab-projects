# 数据说明

## 数据来源

本系统使用的真实地震事件数据来源于 **USGS（美国地质调查局）官方地震目录**。

- **数据源名称**：USGS Earthquake Catalog
- **数据源网址**：https://earthquake.usgs.gov/fdsnws/event/1/query
- **数据格式**：GeoJSON（通过 FDSN Event Web Service 获取）
- **采集方式**：HTTP GET 请求，使用 Python requests 库，低频自动采集
- **查询参数**：最近 6 个月，中国及周边区域（纬度 35°N，经度 105°E，半径 2000km），震级 ≥ 2.5，最多 200 条
- **采集脚本**：`2_源码/crawler/fetch_usgs.py` 和 `2_源码/crawler/update_earthquake_data.py`

> **免责声明**：本数据仅用于课程教学演示，不代表官方地震预警或地震预测结果。

## 采集参数说明

| 参数 | 值 |
|------|-----|
| 数据源 | USGS FDSN Event Web Service |
| 接口 URL | https://earthquake.usgs.gov/fdsnws/event/1/query |
| 格式 | geojson |
| 时间范围 | 最近 180 天 |
| 震级下限 | 2.5 |
| 中心点 | 纬度 35°，经度 105°（中国中部） |
| 搜索半径 | 2000 km |
| 排序方式 | 时间倒序 |
| 单次最大条数 | 200 |
| 请求超时 | 30 秒 |
| 重试次数 | 3 次 |

## 原始数据文件

原始采集数据保存在 `raw_data/` 目录，命名格式为：`earthquake_usgs_raw_YYYYMMDD_HHMMSS.csv`

### 字段说明

| 字段名 | 中文含义 | 说明 |
|--------|----------|------|
| `event_id` | 事件编号 | USGS 唯一事件标识 |
| `event_time_utc` | 发震时间（UTC） | 协调世界时 |
| `event_time_beijing` | 发震时间（北京时间） | UTC+8 |
| `latitude` | 纬度 | 震中纬度 |
| `longitude` | 经度 | 震中经度 |
| `depth_km` | 震源深度 | 单位：公里 |
| `magnitude` | 震级 | 地震震级 |
| `magnitude_type` | 震级类型 | 如 mww、mb 等 |
| `place` | 参考位置 | 地震参考位置描述 |
| `event_type` | 事件类型 | earthquake |
| `source` | 数据来源 | USGS |
| `detail_url` | 详情链接 | USGS 事件详情页 |
| `status` | 状态 | reviewed / automatic |

## 处理后数据文件

处理后数据保存在 `processed_data/earthquake_events_processed.csv`。

### 数据处理过程

1. **读取原始数据**：从原始采集 CSV 文件读取地震事件记录。
2. **数据清洗**：
   - 时间格式统一（UTC 和北京时间）
   - 经纬度、深度、震级转数值类型
   - 去除缺失震级、经纬度的记录
   - 去除负震级的无效记录
   - 重复事件删除（按时间+经纬度+震级去重）
3. **字段标准化**：字符串字段去空格，数值字段规范化。
4. **保存处理后数据**：输出到 `earthquake_events_processed.csv`。

### 去重规则

去重键为 `(event_time_utc, latitude, longitude, magnitude)`，相同地震事件只保留一条。

### 缺失值处理

- `magnitude`、`latitude`、`longitude` 缺失：删除该记录
- 其他字段缺失：保留，标注为空字符串

### 数据溯源

每条数据的 `source` 字段标识数据来源，`detail_url` 字段提供 USGS 官方事件详情页面链接，`event_id` 可用于交叉验证。

## 原始文件校验

原始采集文件的 SHA256 校验值记录在 `source_metadata.json` 中，可用于验证数据完整性。

## 免责声明

1. 本数据来源于 USGS 官方公开地震目录，仅用于课程教学演示。
2. 数据中的地震事件均为已发生地震的公开记录，不代表地震预测。
3. 数据采集过程中严格遵守低频请求、合理超时、设置 User-Agent 等要求。
4. 数据不用于任何商业用途或专业地震安全决策。
