# 基于遗传算法的救援物资分配优化

## 项目简介

本项目基于遗传算法实现救援物资分配优化，以2021年河南极端暴雨灾害为案例，建立多目标优化模型，综合考虑物资满足率、运输成本、公平性、紧急程度和时间效率等指标。

## 版本说明

本项目提供**两个版本**，分别适用于不同场景：

### 📌 版本1: 专用版 (main.py)

**适用场景**: 固定使用河南洪灾数据，快速运行

**特点**:
- 数据硬编码在代码中
- 适合提交大作业演示
- 无需配置文件

**运行方式**:
```bash
cd 源码/code
python main.py
```

### 📌 版本2: 通用版 (main_universal.py)

**适用场景**: 需要灵活调整参数、自定义数据、扩展功能

**特点**:
- 支持配置文件 (`config.json`)
- 自动适应任意规模数据
- 可扩展评价指标
- 方便更换数据集

**运行方式**:
```bash
cd 源码/code
python main_universal.py
```

## 数据来源

- **真实数据**: 2021年河南极端暴雨灾害统计数据
- **论文引用**: Zhang L, Wang J, et al. PLoS ONE 2024
- **GitHub**: https://github.com/jinyu2429/Major-Natural-Disasters

## 项目结构

```
源码/
├── code/                          # Python 后端源代码
│   ├── main.py                    # 专用版主程序（河南洪灾）
│   ├── main_universal.py          # 通用版主程序
│   ├── export_for_frontend.py     # 导出数据供前端使用
│   ├── data_loader.py             # 数据加载器
│   ├── config.json                # 配置文件（通用版）
│   └── ...
├── frontend/                      # Vue 可视化前端
│   ├── src/components/            # 图表组件
│   ├── public/data/results.json   # 优化结果数据
│   └── README.md                  # 前端使用说明
├── requirements.txt               # Python 依赖列表
└── README.md                      # 项目说明
```

## Vue 可视化前端

项目提供基于 **Vue 3 + ECharts** 的可视化展示页面，展示优化结果图表。

```bash
# 1. 导出优化结果数据
cd 源码/code
python export_for_frontend.py

# 2. 启动前端
cd ../frontend
npm install
npm run dev
```

浏览器访问 http://127.0.0.1:5180 查看可视化大屏。详见 `frontend/README.md`。

## 一键启动（推荐）

在 `源码` 目录下执行以下任一命令，自动完成：**检查依赖 → 导出优化数据 → 启动 Vue 可视化前端**。

```bash
cd 源码

# macOS / Linux
./start.sh

# 或使用 Python（跨平台）
python3 start.py

# Windows 双击或命令行
start.bat
```

启动成功后浏览器访问 **http://127.0.0.1:5180**。

可选参数：

```bash
python3 start.py --skip-export    # 跳过数据导出，直接启动前端（更快）
python3 start.py --export-only    # 仅导出数据，不启动前端
```

## 安装依赖

```bash
cd 源码
pip install -r requirements.txt
```

## 使用方式

### 方式一：运行专用版（推荐用于大作业提交）

```bash
cd 源码/code
python main.py
```

**特点**: 
- 快速运行，无需配置
- 数据固定为河南洪灾数据
- 输出图表到 `源码/output/` 目录

### 方式二：运行通用版（推荐用于自定义场景）

```bash
cd 源码/code
python main_universal.py
```

**特点**:
- 支持配置文件调整参数
- 可更换数据集
- 自动适应数据规模

## 配置参数（通用版）

配置文件: `源码/code/config.json`

### 算法参数

```json
{
  "algorithm": {
    "pop_size": 100,        // 种群大小
    "generations": 50,      // 迭代次数
    "mutation_rate": 0.1,   // 变异率
    "crossover_rate": 0.8,  // 交叉率
    "elite_ratio": 0.1      // 精英保留比例
  }
}
```

### 目标权重

```json
{
  "objectives": {
    "satisfaction": {"weight": 0.35, "enabled": true},
    "transport_cost": {"weight": 0.15, "enabled": true},
    "fairness": {"weight": 0.2, "enabled": true},
    "urgency": {"weight": 0.2, "enabled": true},
    "time_efficiency": {"weight": 0.1, "enabled": true}
  }
}
```

### 数据配置

```json
{
  "data": {
    "disaster_points_file": "../../数据包/processed_data/henan_disaster_processed_data.py",
    "use_simulation": false
  }
}
```

## 核心功能

1. **数据读取模块**: 支持从数据包加载真实灾害数据
2. **遗传算法模块**: 
   - 编码方式: 三维数组 (仓库×受灾点×物资)
   - 适应度函数: 多目标加权综合评价
   - 选择操作: 轮盘赌选择
   - 交叉操作: 单点交叉
   - 变异操作: 随机扰动
   - 约束处理: 库存约束、车辆约束、需求约束
3. **可视化模块**: 
   - 优化前后满足率对比图
   - 遗传算法迭代过程曲线
   - 物资分配热力图

## 评价指标

| 指标 | 权重 | 说明 |
|-----|------|------|
| 物资满足率 | 35% | 各受灾点物资需求满足程度 |
| 运输成本 | 15% | 考虑道路状况的运输总成本 |
| 公平性 | 20% | 各受灾点满足率的均衡程度 |
| 紧急程度 | 20% | 优先满足紧急程度高的受灾点 |
| 时间效率 | 10% | 运输时间的倒数 |

## 约束条件

1. **库存约束**: 分配量 ≤ 仓库库存量
2. **需求约束**: 分配量 ≤ 受灾点需求量
3. **车辆约束**: 运输量 ≤ 车辆容量 × 车辆数量
4. **道路约束**: 考虑道路状况对运输的影响

## 输出结果

程序运行后会在 `源码/output/` 目录生成：

1. `satisfaction_comparison.png` - 优化前后满足率对比图
2. `fitness_history.png` - 遗传算法迭代过程曲线
3. `allocation_heatmap.png` - 物资分配热力图
4. `initial_solution.npy` - 初始方案数据
5. `optimized_solution.npy` - 优化后方案数据
6. `fitness_history.npy` - 适应度变化数据

## 配置参数

在 `main.py` 中可调整以下参数：

```python
# 遗传算法参数
pop_size = 100          # 种群大小
generations = 50        # 迭代代数
mutation_rate = 0.1     # 变异率

# 目标权重
objective_weights = {
    'satisfaction': 0.35,
    'transport_cost': 0.15,
    'fairness': 0.2,
    'urgency': 0.2,
    'time_efficiency': 0.1
}
```

## 运行环境

- Python 3.8+
- numpy 1.24+
- matplotlib 3.7+
- pandas 2.0+

## 参考文献

1. 河南省应急管理厅. (2021). 2021年河南省洪涝灾害灾情统计公报.
2. Zhang L, Wang J, Li Y, et al. (2024). Emergency Material Allocation Optimization Based on Genetic Algorithm. PLoS ONE.
3. 高德地图API. (2021). 地理编码服务文档.
