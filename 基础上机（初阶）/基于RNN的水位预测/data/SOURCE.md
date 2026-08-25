# 数据来源

- 机构：NOAA Center for Operational Oceanographic Products and Services (CO-OPS)
- 站点：The Battery, New York（站号 8518750）
- 时间：2024-01-01 00:00 至 2024-12-31 23:00，GMT
- 产品：`hourly_height`（已核验逐小时水位）
- 单位：米
- 高程基准：MLLW（平均低低潮）
- API 文档：https://api.tidesandcurrents.noaa.gov/api/dev
- 下载请求：`product=hourly_height&station=8518750&datum=MLLW&time_zone=gmt&units=metric`

原始 CSV 保留 NOAA 返回的 Sigma 及质量标记列。本项目的 RNN 仅使用 `Date Time` 和 `Water Level` 两列。

