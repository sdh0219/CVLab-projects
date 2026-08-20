# 项目14：避开危险路段的救援路径规划

本项目面向灾害应急响应场景，使用真实地图道路数据和公开历史灾害资料，构建道路网络并识别危险路段。项目继续只使用 Dijkstra 算法，分别计算普通最短路径和考虑灾害风险后的安全路径。

## 数据来源

1. 真实地图数据：来自高德 Web 服务路径规划接口和静态地图接口。路径规划接口提供道路名称、路线坐标、道路距离、导航指令和交通状态等基础道路信息；静态地图接口提供最终展示使用的真实地图底图。
2. 历史灾害数据：位于 `data/historical_disasters/disaster_events.csv`。地震场景采用 1679 年三河-平谷地震的公开历史资料；洪水场景采用 2012 年 7 月 21 日北京特大暴雨及中国气象数据服务相关资料。
3. 道路受灾映射：项目将历史灾害点或灾害影响区转为缓冲区，再与高德道路线段做空间叠加。道路线段进入缓冲区后，被标记为塌方或积水风险。

补充说明：`data/amap_request.json` 中包含若干 `context_` 开头的路线请求，并额外设置了 `context_routes` 背景采样路线，用于向高德获取更多周边真实道路轨迹，增强二维抽象图的地图语境。这些道路只作为淡色背景路网显示，不参与 Dijkstra 最短路径和安全路径计算。

说明：公开历史灾害资料通常不会精确到“某一条道路官方封闭”。本项目采用课程作业常用的空间映射方法，把真实灾害事件影响区映射到真实道路网络上，得到可用于 Dijkstra 计算的危险路段。

## 项目结构

```text
data/
  amap/                    高德真实道路数据
  amap_earthquake/          地震场景数据
  amap_flood/               洪水场景数据
  historical_disasters/     历史灾害事件数据
src/
  amap_fetcher.py           高德 Web 服务数据获取
  rescue_planner.py         图构建、Dijkstra、权重计算、可视化
tools/
  create_disaster_scenarios.py  历史灾害影响区与道路叠加
  create_amap_static_visuals.py  高德静态地图底图叠加可视化
  create_abstract_route_maps.py  真实道路二维抽象路网图
outputs/
  amap_earthquake/          地震场景输出
  amap_flood/               洪水场景输出
docs/
  technical_solution.md
  项目14_避开危险路段的救援路径规划_汇报文档.md
  demo_script.md
```

## 运行方式

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe tools\create_disaster_scenarios.py
.\.venv\Scripts\python.exe src\rescue_planner.py --data-dir data\amap_earthquake --output-dir outputs\amap_earthquake
.\.venv\Scripts\python.exe src\rescue_planner.py --data-dir data\amap_flood --output-dir outputs\amap_flood
.\.venv\Scripts\python.exe tools\create_amap_static_visuals.py
.\.venv\Scripts\python.exe tools\create_abstract_route_maps.py
```

如果需要重新抓取高德路线数据，先设置高德 Web 服务 Key：

```powershell
$env:AMAP_KEY="你的高德Web服务Key"
powershell -ExecutionPolicy Bypass -File .\run_amap_project.ps1
```

## 算法说明

普通最短路径只使用道路距离作为边权重：

```text
distance_weight = distance
```

安全路径使用综合权重：

```text
safe_weight = distance * risk_factor * (1 + congestion_weight * congestion)
```

默认风险系数：

| 类型 | 含义 | 系数 |
| --- | --- | ---: |
| normal | 正常通行 | 1.0 |
| congestion | 拥堵 | 1.4 |
| flood | 积水 | 2.2 |
| collapse | 塌方 | 4.0 |

## 当前结果

| 场景 | 路径类型 | 距离 | 危险类型 | 说明 |
| --- | --- | ---: | --- | --- |
| 地震 | 普通最短路径 | 19.973 km | collapse, congestion | 距离短，但经过历史地震影响区 |
| 地震 | 安全路径 | 26.816 km | congestion | 绕开主要塌方风险 |
| 洪水 | 普通最短路径 | 19.973 km | congestion, flood | 距离短，但经过历史洪水影响区 |
| 洪水 | 安全路径 | 26.816 km | congestion | 绕开主要积水风险 |

主要输出文件：

- `outputs/amap_earthquake/path_comparison.csv`
- `outputs/amap_earthquake/route_map_amap_static.png`
- `outputs/amap_earthquake/route_map_abstract.png`
- `outputs/amap_flood/path_comparison.csv`
- `outputs/amap_flood/route_map_amap_static.png`
- `outputs/amap_flood/route_map_abstract.png`
- `data/amap_earthquake/road_disaster_mapping.csv`
- `data/amap_flood/road_disaster_mapping.csv`
