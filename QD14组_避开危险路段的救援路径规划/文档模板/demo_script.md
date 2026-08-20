# 项目演示录像脚本

## 1. 展示项目目录

打开项目根目录 `D:\lihao\作业`，说明项目包含数据、源码、输出结果、技术文档和汇报材料。

重点展示：

- `data/amap/`：高德真实道路数据。
- `data/historical_disasters/`：历史灾害事件数据。
- `data/amap_earthquake/`：地震场景数据。
- `data/amap_flood/`：洪水场景数据。
- `outputs/amap_earthquake/` 和 `outputs/amap_flood/`：路径结果和图片。

## 2. 展示真实地图数据

打开 `data/amap/nodes.csv` 和 `data/amap/edges.csv`。

讲解：

“这里的道路节点和道路边不是随便手画的，而是由高德 Web 服务返回的真实驾车路线转换而来。边数据中包含道路名称、距离、导航指令和拥堵程度。”

## 3. 展示历史灾害数据

打开 `data/historical_disasters/disaster_events.csv`。

讲解：

“这里记录了两个历史灾害场景。地震场景采用 1679 年三河-平谷地震公开历史资料，洪水场景采用 2012 年北京 7·21 特大暴雨资料。由于公开数据一般不会精确到每条道路是否损坏，所以项目使用影响区缓冲和道路叠加的方法识别危险路段。”

## 4. 展示道路受灾映射

打开：

- `data/amap_earthquake/road_disaster_mapping.csv`
- `data/amap_flood/road_disaster_mapping.csv`

讲解：

“这个表是关键。程序计算每条道路与历史灾害影响区之间的距离。如果道路进入影响半径，就标记为塌方或积水风险。这样危险路段不是凭空指定，而是由真实灾害影响区和真实道路位置叠加得到。”

## 5. 运行路径规划

在 PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe tools\create_disaster_scenarios.py
.\.venv\Scripts\python.exe src\rescue_planner.py --data-dir data\amap_earthquake --output-dir outputs\amap_earthquake
.\.venv\Scripts\python.exe src\rescue_planner.py --data-dir data\amap_flood --output-dir outputs\amap_flood
```

讲解：

“程序会先生成地震和洪水两个灾害场景，再分别运行 Dijkstra。Dijkstra 在 distance 模式下得到普通最短路径，在 safe 模式下得到考虑灾害风险的安全路径。”

## 6. 展示结果表

打开：

- `outputs/amap_earthquake/path_comparison.csv`
- `outputs/amap_flood/path_comparison.csv`

讲解：

“地震场景中，普通最短路径距离为 19.973 公里，但经过 collapse 和 congestion 风险。安全路径距离为 26.816 公里，绕开了主要塌方影响区，只剩拥堵风险。洪水场景中，普通最短路径经过 flood 风险，安全路径绕开主要积水影响区。”

## 7. 展示路线图

打开：

- `outputs/amap_earthquake/route_map_context.png`
- `outputs/amap_flood/route_map_context.png`

讲解：

“图中浅色道路是高德返回的全部候选道路背景，蓝色粗线是普通最短路径，绿色粗线是安全路径。半透明区域是历史灾害影响区，红色或浅蓝细线是受影响道路。可以看到安全路径主动绕开了灾害影响区，虽然距离更长，但更适合救援通行。”

## 8. 总结

结束语：

“本项目的核心不是简单找最短路，而是把真实道路数据和历史灾害影响区结合起来，把灾害风险转成道路权重，再用 Dijkstra 算法规划更安全的救援路线。实验说明，在应急救援中，安全路径比距离最短路径更有实际意义。”
