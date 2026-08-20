# 通用版配置文件说明

## 文件位置

`源码/code/config.json`

## 配置项说明

### 1. 数据配置 (data)

```json
"data": {
  "disaster_points_file": "../../数据包/processed_data/henan_disaster_processed_data.py",
  "use_simulation": false
}
```

| 配置项 | 说明 | 可选值 |
|-------|------|--------|
| `disaster_points_file` | 数据文件路径 | 相对于项目根目录的路径 |
| `use_simulation` | 是否使用模拟数据 | `true` / `false` |

### 2. 算法配置 (algorithm)

```json
"algorithm": {
  "pop_size": 100,
  "generations": 50,
  "mutation_rate": 0.1,
  "crossover_rate": 0.8,
  "elite_ratio": 0.1,
  "selection_pressure": 2
}
```

| 配置项 | 说明 | 推荐值 |
|-------|------|--------|
| `pop_size` | 种群大小 | 50-200 |
| `generations` | 迭代代数 | 30-100 |
| `mutation_rate` | 变异率 | 0.05-0.2 |
| `crossover_rate` | 交叉率 | 0.6-0.9 |
| `elite_ratio` | 精英保留比例 | 0.05-0.15 |
| `selection_pressure` | 选择压力 | 1.5-3.0 |

### 3. 目标函数配置 (objectives)

```json
"objectives": {
  "satisfaction": {
    "weight": 0.35,
    "enabled": true,
    "description": "物资满足率"
  },
  "transport_cost": {
    "weight": 0.15,
    "enabled": true,
    "description": "运输成本"
  },
  "fairness": {
    "weight": 0.2,
    "enabled": true,
    "description": "分配公平性"
  },
  "urgency": {
    "weight": 0.2,
    "enabled": true,
    "description": "紧急程度"
  },
  "time_efficiency": {
    "weight": 0.1,
    "enabled": true,
    "description": "时间效率"
  }
}
```

| 目标 | 说明 | 权重范围 |
|------|------|---------|
| `satisfaction` | 各受灾点物资需求满足程度 | 0.0-1.0 |
| `transport_cost` | 考虑道路状况的运输成本 | 0.0-1.0 |
| `fairness` | 各受灾点满足率的均衡程度 | 0.0-1.0 |
| `urgency` | 优先满足紧急程度高的点 | 0.0-1.0 |
| `time_efficiency` | 运输时间的倒数 | 0.0-1.0 |

**注意**: 所有启用(`enabled: true`)的目标权重之和应为 1.0

### 4. 约束配置 (constraints)

```json
"constraints": {
  "inventory_limit": {
    "enabled": true,
    "description": "库存约束"
  },
  "demand_limit": {
    "enabled": true,
    "description": "需求约束"
  },
  "vehicle_limit": {
    "enabled": true,
    "description": "车辆约束"
  },
  "repair_method": "ratio"
}
```

| 约束 | 说明 |
|------|------|
| `inventory_limit` | 分配量不超过仓库库存 |
| `demand_limit` | 分配量不超过受灾点需求 |
| `vehicle_limit` | 运输量不超过车辆运力 |
| `repair_method` | 修复方法 (`ratio` / `penalty`) |

### 5. 输出配置 (output)

```json
"output": {
  "save_plots": true,
  "save_data": true,
  "output_dir": "output_universal",
  "dpi": 300
}
```

| 配置项 | 说明 |
|-------|------|
| `save_plots` | 是否保存图表 |
| `save_data` | 是否保存数据 |
| `output_dir` | 输出目录 |
| `dpi` | 图表分辨率 |

### 6. 日志配置 (logging)

```json
"logging": {
  "verbose": true,
  "save_history": true
}
```

## 使用示例

### 示例1: 调整评价指标权重

修改 `config.json`:

```json
{
  "objectives": {
    "satisfaction": {"weight": 0.5, "enabled": true},
    "transport_cost": {"weight": 0.1, "enabled": true},
    "fairness": {"weight": 0.2, "enabled": true},
    "urgency": {"weight": 0.1, "enabled": true},
    "time_efficiency": {"weight": 0.1, "enabled": true}
  }
}
```

### 示例2: 使用不同的数据集

```json
{
  "data": {
    "disaster_points_file": "data/earthquake_disaster.py",
    "use_simulation": false
  }
}
```

### 示例3: 调整算法参数

```json
{
  "algorithm": {
    "pop_size": 150,
    "generations": 80,
    "mutation_rate": 0.15,
    "crossover_rate": 0.85,
    "elite_ratio": 0.12
  }
}
```

## 快速开始

```bash
cd 源码/code

# 运行通用版
python main_universal.py

# 运行专用版（河南洪灾）
python main.py
```

## 扩展自定义指标

如果需要添加新的评价指标，修改 `UniversalAllocationModel` 类：

```python
def calculate_custom_metric(self, individual):
    """计算自定义指标"""
    # 添加你的指标计算逻辑
    return metric_value

def fitness(self, individual):
    # 在适应度函数中添加
    if self.objective_weights.get('custom_metric', 0) > 0:
        custom_score = self.calculate_custom_metric(individual)
        fitness_value += self.objective_weights['custom_metric'] * custom_score
```

## 注意事项

1. **权重归一化**: 确保所有启用的目标权重之和为 1.0
2. **数据格式**: 确保数据文件返回的numpy数组维度正确
3. **约束处理**: 不可行解会被自动修复
4. **性能调优**: 
   - 问题规模大时增加 `pop_size`
   - 需要更好解时增加 `generations`
   - 避免局部最优时增加 `mutation_rate`
