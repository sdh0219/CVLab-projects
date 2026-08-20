# 救援物资分配优化 — Vue 可视化前端

基于 **Vue 3 + Vite + ECharts** 的应急物资分配优化结果可视化展示页面。

## 功能模块

| 组件 | 说明 |
|------|------|
| `DataSummary` | 数据概览卡片（受灾点、仓库、人口、满足率等） |
| `SatisfactionChart` | 各受灾点满足率优化前后对比柱状图 |
| `FitnessChart` | 遗传算法迭代适应度曲线 |
| `AllocationHeatmap` | 仓库→受灾点物资分配热力图 |
| `MetricsRadar` | 多目标指标雷达图对比 |

## 快速启动

**推荐：使用一键启动脚本（自动完成依赖检查、数据导出、前端启动）**

```bash
cd 源码
./start.sh
```

### 手动分步启动

#### 1. 安装依赖

```bash
cd 源码/frontend
npm install
```

### 2. 导出后端数据（可选，推荐）

在运行前端前，先由 Python 后端生成最新结果：

```bash
cd 源码/code
python export_for_frontend.py
```

该脚本会：
- 优先读取 `output/` 目录下已有的 `.npy` 结果
- 若无则重新运行遗传算法优化
- 导出 JSON 到 `frontend/public/data/results.json`

### 3. 启动开发服务器

```bash
cd 源码/frontend
npm run dev
```

浏览器访问 **http://127.0.0.1:5180**

### 4. 生产构建

```bash
npm run build
npm run preview
```

构建产物在 `dist/` 目录。

## 项目结构

```
frontend/
├── public/
│   └── data/
│       └── results.json      # 优化结果数据（由 Python 导出）
├── src/
│   ├── api/
│   │   └── dataService.js    # 数据加载工具
│   ├── components/
│   │   ├── DataSummary.vue
│   │   ├── SatisfactionChart.vue
│   │   ├── FitnessChart.vue
│   │   ├── AllocationHeatmap.vue
│   │   └── MetricsRadar.vue
│   ├── App.vue               # 主页面
│   ├── main.js
│   └── style.css
├── index.html
├── package.json
└── vite.config.js
```

## 完整使用流程

```bash
# 步骤1: 运行 Python 优化并导出数据
cd 源码/code
python main.py                        # 或 python export_for_frontend.py

# 步骤2: 启动 Vue 前端
cd ../frontend
npm install
npm run dev
```

## 数据格式

`public/data/results.json` 主要字段：

```json
{
  "generatedAt": "2026-06-15 12:00:00",
  "summary": { "disasterPointsCount": 6, ... },
  "pointNames": ["郑州", "巩义", ...],
  "warehouseNames": ["郑州储备库", ...],
  "initialMetrics": { "satisfaction_rate": 8.52, "detailed_satisfaction": [...] },
  "optimizedMetrics": { "satisfaction_rate": 12.35, ... },
  "fitnessHistory": [0.32, 0.35, ...],
  "allocationMatrix": [[...], [...], [...]]
}
```

## 技术栈

- Vue 3 (Composition API)
- Vite 6
- ECharts 5 + vue-echarts
- 深色主题 UI
