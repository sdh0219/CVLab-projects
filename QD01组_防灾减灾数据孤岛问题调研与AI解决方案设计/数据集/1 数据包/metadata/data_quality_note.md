# 数据质量说明

本数据包采用“真实数据优先，失败源自动补充模拟数据”的策略。

## 已有真实数据
- NOAA Daily Summaries 气象数据：真实下载数据。
- FEMA Disaster Declarations 洛杉矶县灾害声明：真实下载数据。
- USGS Earthquake Catalog 洛杉矶区域地震目录：真实下载数据。
- U.S. Census TIGER/Line Roads 洛杉矶县道路 Shapefile：真实下载数据。

## 自动补充数据
以下文件是为了避免下载失败导致项目无法运行而生成的同格式 GeoJSON 替代数据：
- population_svi_la_county.geojson
- emergency_fire_ems_stations_la.geojson
- emergency_hospitals_la.geojson
- landslide_cgs_la_county.geojson

其中，SVI、消防站和医院如果你本地已经通过脚本成功下载了真实 GeoJSON，可以直接覆盖本包中的同名文件。
CGS landslide ZIP 因 SSL EOF 错误下载失败，本包提供 landslide_cgs_la_county.geojson 作为课程作业复现用替代数据。

重要说明：fallback simulated 文件不能写成官方真实原始数据。技术方案中建议表述为：
“除气象、地震、灾害声明、道路等真实公开数据外，因 CGS 滑坡清单下载接口 SSL 异常，项目保留下载日志，并构造字段一致的 GeoJSON 替代样例用于平台流程验证。”
