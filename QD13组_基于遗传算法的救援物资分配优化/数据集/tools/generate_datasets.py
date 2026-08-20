#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应急物资分配优化 - 模拟数据集生成器

生成两组独立数据集：
  1. dataset_01_large_scale      - 大规模（多受灾点、多仓库）
  2. dataset_02_complex_scenario - 复杂场景（多物资类型、异构约束、丰富描述）

用法:
  python generate_datasets.py
"""

import json
import math
import os
from datetime import datetime

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RNG = np.random.default_rng(20260615)


def haversine_km(lon1, lat1, lon2, lat2):
    """计算两点球面距离（公里）"""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_distance_matrix(warehouse_coords, point_coords):
    n_w, n_p = len(warehouse_coords), len(point_coords)
    matrix = np.zeros((n_w, n_p))
    for w in range(n_w):
        for p in range(n_p):
            matrix[w, p] = haversine_km(
                warehouse_coords[w][0], warehouse_coords[w][1],
                point_coords[p][0], point_coords[p][1],
            )
    return matrix


def build_road_and_time(distance_matrix, base_speed_kmh=60.0, noise_scale=0.15):
    """根据距离生成道路状况与运输时间"""
    n_w, n_p = distance_matrix.shape
    road = RNG.uniform(0.45, 1.0, size=(n_w, n_p))
    # 距离越远，道路状况略差
    dist_norm = distance_matrix / (distance_matrix.max() + 1e-10)
    road = np.clip(road - 0.25 * dist_norm, 0.2, 1.0)
    transport_time = distance_matrix / (base_speed_kmh * road + 1e-10)
    return road, transport_time


def compute_demand(population, urgency, material_names, multipliers):
    """按人口与紧急系数计算多物资需求"""
    demands = []
    for pop, urg in zip(population, urgency):
        base = pop * (1 + 0.15 * (urg - 1))
        row = [int(base * multipliers[name]) for name in material_names]
        demands.append(row)
    return np.array(demands, dtype=int)


def compute_urgency_weights(disaster_points):
    urgency = disaster_points[:, 7].astype(float)
    if urgency.sum() <= 0:
        return np.ones(len(urgency)) / len(urgency)
    return urgency / urgency.sum()


def _format_number(val):
    """将数值格式化为易读字符串，避免科学计数法"""
    if isinstance(val, (np.integer, int)):
        return str(int(val))
    v = float(val)
    if math.isfinite(v) and abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    if abs(v) >= 1:
        text = f'{v:.4f}'.rstrip('0').rstrip('.')
        return text if text else '0'
    return f'{v:.4f}'.rstrip('0').rstrip('.')


def format_array(name, arr, indent=0):
    """将 numpy 数组格式化为可读的 Python 代码"""
    sp = ' ' * indent
    arr = np.asarray(arr)
    if arr.ndim == 1:
        row_text = ', '.join(_format_number(v) for v in arr)
        return f"{sp}{name} = np.array([{row_text}])"
    rows = [' [' + ', '.join(_format_number(v) for v in row) + ']' for row in arr]
    body = ',\n'.join(rows)
    return f"{sp}{name} = np.array([\n{body}\n{sp}])"


def write_processed_py(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def generate_large_scale():
    """数据集1：大规模洪涝应急调度（80受灾点 × 12仓库 × 3物资）"""
    n_points, n_warehouses = 80, 12
    material_names = ['饮用水', '方便面', '帐篷']
    material_multipliers = {'饮用水': 2.0, '方便面': 0.5, '帐篷': 0.08}

    # 模拟黄淮流域大范围洪涝
    point_lons = RNG.uniform(112.2, 115.2, n_points)
    point_lats = RNG.uniform(33.8, 35.2, n_points)
    population = RNG.integers(8000, 120000, n_points)
    casualties = (population * RNG.uniform(0.01, 0.08, n_points)).astype(int)
    relocated = (population * RNG.uniform(0.05, 0.35, n_points)).astype(int)
    housing_damage = (population * RNG.uniform(0.02, 0.15, n_points)).astype(int)
    urgency = RNG.integers(1, 6, n_points)

    disaster_points = np.column_stack([
        np.arange(1, n_points + 1),
        point_lons, point_lats,
        population, casualties, relocated, housing_damage, urgency,
    ])

    warehouse_lons = RNG.uniform(112.0, 115.5, n_warehouses)
    warehouse_lats = RNG.uniform(33.7, 35.3, n_warehouses)
    wh_population_cover = RNG.integers(200000, 1500000, n_warehouses)

    demand = compute_demand(population, urgency, material_names, material_multipliers)
    total_demand = demand.sum(axis=0)

    # 库存满足总需求 55%~75%
    inventory = np.zeros((n_warehouses, len(material_names)), dtype=int)
    for m in range(len(material_names)):
        ratios = RNG.dirichlet(np.ones(n_warehouses))
        inventory[:, m] = (ratios * total_demand[m] * RNG.uniform(0.55, 0.75)).astype(int)

    vehicles = RNG.integers(25, 90, n_warehouses)
    vehicle_capacity = RNG.integers(80, 160, n_warehouses)

    warehouses = np.column_stack([
        np.arange(1, n_warehouses + 1),
        warehouse_lons, warehouse_lats,
        inventory,
        vehicles, vehicle_capacity,
    ])

    point_coords = list(zip(point_lons, point_lats))
    warehouse_coords = list(zip(warehouse_lons, warehouse_lats))
    distance_matrix = build_distance_matrix(warehouse_coords, point_coords)
    road_conditions, transport_time = build_road_and_time(distance_matrix)

    urgency_weights = compute_urgency_weights(disaster_points)
    material_weights = np.array([0.5, 0.35, 0.15])
    objective_weights = {
        'satisfaction': 0.35,
        'transport_cost': 0.15,
        'fairness': 0.2,
        'urgency': 0.2,
        'time_efficiency': 0.1,
    }

    disaster_points_info = {
        int(i + 1): {
            'name': f'受灾点{i + 1:03d}',
            'population': int(population[i]),
            'casualties': int(casualties[i]),
            'relocated': int(relocated[i]),
            'housing_damage': int(housing_damage[i]),
            'urgency_level': int(urgency[i]),
            'region': '黄淮流域洪涝模拟区',
        }
        for i in range(n_points)
    }

    warehouses_info = {
        f'区域储备库{w + 1:02d}': {
            'location': (float(warehouse_lons[w]), float(warehouse_lats[w])),
            'inventory': inventory[w].tolist(),
            'vehicles': int(vehicles[w]),
            'vehicle_capacity': int(vehicle_capacity[w]),
            'coverage_population': int(wh_population_cover[w]),
        }
        for w in range(n_warehouses)
    }

    metadata = {
        'dataset_id': 'dataset_01_large_scale',
        'dataset_name': '大规模洪涝应急物资调度模拟数据',
        'scenario': '多区域、多仓库、大规模洪涝灾害物资调运',
        'data_source': '基于河南洪灾案例规则扩展的模拟数据',
        'created_date': datetime.now().strftime('%Y-%m-%d'),
        'disaster_points_count': n_points,
        'warehouses_count': n_warehouses,
        'materials_count': len(material_names),
        'material_names': material_names,
        'total_population_affected': int(population.sum()),
        'total_demand': int(demand.sum()),
        'total_inventory': int(inventory.sum()),
        'max_transport_capacity': int((vehicles * vehicle_capacity).sum()),
        'characteristics': [
            '80个受灾点，覆盖黄淮流域模拟区域',
            '12个区域储备库，异构车辆与运力',
            '3类物资，需求与库存规模达十万级',
            '适用于验证算法在大规模场景下的可扩展性',
        ],
    }

    return {
        'disaster_points': disaster_points,
        'warehouses': warehouses,
        'distance_matrix': distance_matrix,
        'road_conditions': road_conditions,
        'transport_time': transport_time,
        'demand': demand,
        'inventory': inventory,
        'urgency_weights': urgency_weights,
        'material_weights': material_weights,
        'objective_weights': objective_weights,
        'disaster_points_info': disaster_points_info,
        'warehouses_info': warehouses_info,
        'metadata': metadata,
        'material_names': material_names,
    }


def generate_complex_scenario():
    """数据集2：复杂场景（多灾害类型、多物资、异构仓库与通行约束）"""
    material_names = ['饮用水', '食品', '帐篷', '药品', '发电设备']
    material_multipliers = {
        '饮用水': 1.8, '食品': 0.6, '帐篷': 0.1, '药品': 0.25, '发电设备': 0.03,
    }

    # 15个受灾点，含多种灾害类型与通行等级
    point_specs = [
        ('石门镇', 113.72, 34.41, 185000, 5, '洪水', '极差', 6),
        ('清河乡', 113.15, 34.55, 42000, 4, '洪水', '较差', 10),
        ('云台村', 112.88, 34.62, 9600, 3, '山体滑坡', '中断', 18),
        ('柳沟镇', 114.02, 34.78, 73000, 4, '洪水', '较差', 12),
        ('白河滩', 113.48, 34.22, 128000, 5, '堰塞湖', '极差', 8),
        ('凤凰岭', 112.65, 34.48, 31000, 3, '洪水', '一般', 16),
        ('龙泉寺', 113.95, 34.35, 56000, 4, '洪水+滑坡', '较差', 14),
        ('沙窝村', 112.42, 34.71, 15000, 2, '洪水', '一般', 20),
        ('铁炉镇', 114.28, 34.58, 89000, 4, '洪水', '较差', 12),
        ('高庙乡', 113.25, 34.88, 27000, 3, '内涝', '一般', 18),
        ('二郎庙', 112.78, 34.29, 64000, 4, '洪水', '较差', 14),
        ('槐树坪', 113.58, 34.12, 38000, 3, '山体滑坡', '中断', 24),
        ('马庄乡', 114.45, 34.42, 52000, 3, '洪水', '一般', 16),
        ('赵家湾', 112.95, 34.82, 22000, 2, '内涝', '良好', 22),
        ('田坝村', 113.82, 34.65, 47000, 3, '洪水', '一般', 16),
    ]

    n_points = len(point_specs)
    population = np.array([s[3] for s in point_specs])
    urgency = np.array([s[4] for s in point_specs])

    disaster_points = np.array([
        [i + 1, s[1], s[2], s[3],
         int(s[3] * 0.05), int(s[3] * 0.2), int(s[3] * 0.08), s[4]]
        for i, s in enumerate(point_specs)
    ])

    # 6个异构仓库：不同专长与运力
    warehouse_specs = [
        ('省级中心库', 113.62, 34.75, [120000, 95000, 18000, 42000, 8000], 80, 120, ['全部']),
        ('西部医疗库', 112.50, 34.60, [30000, 25000, 8000, 85000, 3000], 45, 90, ['药品', '食品']),
        ('东部综合库', 114.30, 34.70, [85000, 70000, 15000, 20000, 12000], 60, 110, ['全部']),
        ('山地应急库', 112.70, 34.35, [20000, 18000, 25000, 15000, 25000], 30, 70, ['帐篷', '发电设备']),
        ('北部前置库', 113.90, 34.85, [55000, 45000, 10000, 18000, 5000], 40, 100, ['饮用水', '食品']),
        ('南部机动库', 113.20, 34.15, [35000, 30000, 12000, 22000, 18000], 55, 95, ['全部']),
    ]

    n_warehouses = len(warehouse_specs)
    inventory = np.array([w[3] for w in warehouse_specs], dtype=int)
    vehicles = np.array([w[4] for w in warehouse_specs])
    vehicle_capacity = np.array([w[5] for w in warehouse_specs])

    warehouses = np.column_stack([
        np.arange(1, n_warehouses + 1),
        [w[1] for w in warehouse_specs],
        [w[2] for w in warehouse_specs],
        inventory,
        vehicles, vehicle_capacity,
    ])

    demand = compute_demand(population, urgency, material_names, material_multipliers)

    point_coords = [(s[1], s[2]) for s in point_specs]
    warehouse_coords = [(w[1], w[2]) for w in warehouse_specs]
    distance_matrix = build_distance_matrix(warehouse_coords, point_coords)

    # 复杂通行：灾害类型 + 通行等级影响道路状况
    access_penalty = {'良好': 0.0, '一般': 0.15, '较差': 0.35, '极差': 0.5, '中断': 0.65}
    disaster_penalty = {
        '洪水': 0.1, '内涝': 0.12, '山体滑坡': 0.35, '堰塞湖': 0.25, '洪水+滑坡': 0.3,
    }

    road_conditions = np.zeros((n_warehouses, n_points))
    transport_time = np.zeros((n_warehouses, n_points))
    for w in range(n_warehouses):
        for p in range(n_points):
            base_road = RNG.uniform(0.55, 1.0)
            spec = point_specs[p]
            penalty = access_penalty[spec[6]] + disaster_penalty[spec[5]]
            road = max(0.15, base_road - penalty)
            road_conditions[w, p] = road
            speed = 65.0 * road
            transport_time[w, p] = distance_matrix[w, p] / (speed + 1e-10)

    urgency_weights = compute_urgency_weights(disaster_points)
    material_weights = np.array([0.35, 0.25, 0.15, 0.15, 0.10])
    objective_weights = {
        'satisfaction': 0.35,
        'transport_cost': 0.15,
        'fairness': 0.2,
        'urgency': 0.2,
        'time_efficiency': 0.1,
    }

    disaster_points_info = {
        i + 1: {
            'name': point_specs[i][0],
            'population': int(point_specs[i][3]),
            'urgency_level': int(point_specs[i][4]),
            'disaster_type': point_specs[i][5],
            'access_level': point_specs[i][6],
            'delivery_time_window_hours': int(point_specs[i][7]),
            'priority_tier': '一级' if point_specs[i][4] >= 5 else ('二级' if point_specs[i][4] >= 3 else '三级'),
            'special_needs': (
                ['药品优先', '发电保障'] if point_specs[i][5] in ('堰塞湖', '山体滑坡', '洪水+滑坡')
                else ['饮用水优先']
            ),
        }
        for i in range(n_points)
    }

    warehouses_info = {
        warehouse_specs[w][0]: {
            'location': (warehouse_specs[w][1], warehouse_specs[w][2]),
            'inventory': inventory[w].tolist(),
            'vehicles': int(vehicles[w]),
            'vehicle_capacity': int(vehicle_capacity[w]),
            'specialties': warehouse_specs[w][6],
            'cold_chain': warehouse_specs[w][0] in ('省级中心库', '西部医疗库'),
            'all_terrain_vehicles': warehouse_specs[w][0] == '山地应急库',
        }
        for w in range(n_warehouses)
    }

    scenario_config = {
        'constraints': {
            'inventory_limit': True,
            'demand_limit': True,
            'vehicle_limit': True,
            'time_window_soft': True,
            'specialty_matching_soft': True,
        },
        'disaster_types': list({s[5] for s in point_specs}),
        'access_levels': list(access_penalty.keys()),
        'material_names': material_names,
        'notes': [
            '受灾点含洪水、内涝、山体滑坡、堰塞湖及复合灾害类型',
            '通行等级影响道路状况矩阵，进而影响运输成本与时间',
            '仓库具有物资专长标签，可用于扩展约束模型',
            '部分受灾点设置配送时间窗（小时），体现复杂调度描述',
        ],
    }

    metadata = {
        'dataset_id': 'dataset_02_complex_scenario',
        'dataset_name': '复杂场景多灾害应急物资调度模拟数据',
        'scenario': '多灾害类型、多物资、异构仓库与通行约束',
        'data_source': '基于应急管理复杂场景构建的模拟数据',
        'created_date': datetime.now().strftime('%Y-%m-%d'),
        'disaster_points_count': n_points,
        'warehouses_count': n_warehouses,
        'materials_count': len(material_names),
        'material_names': material_names,
        'total_population_affected': int(population.sum()),
        'total_demand': int(demand.sum()),
        'total_inventory': int(inventory.sum()),
        'max_transport_capacity': int((vehicles * vehicle_capacity).sum()),
        'characteristics': [
            '15个受灾点，5种灾害类型与5级通行条件',
            '6个异构仓库，5类物资，含专长与冷链描述',
            '道路状况由灾害类型与通行等级共同决定',
            '适用于验证复杂约束与多目标优化建模能力',
        ],
    }

    return {
        'disaster_points': disaster_points,
        'warehouses': warehouses,
        'distance_matrix': distance_matrix,
        'road_conditions': road_conditions,
        'transport_time': transport_time,
        'demand': demand,
        'inventory': inventory,
        'urgency_weights': urgency_weights,
        'material_weights': material_weights,
        'objective_weights': objective_weights,
        'disaster_points_info': disaster_points_info,
        'warehouses_info': warehouses_info,
        'metadata': metadata,
        'material_names': material_names,
        'scenario_config': scenario_config,
    }


def py_json(obj):
    """将对象格式化为 Python 字面量（兼容 True/False）"""
    text = json.dumps(obj, ensure_ascii=False, indent=4)
    return text.replace('true', 'True').replace('false', 'False').replace('null', 'None')


def render_processed_py(data, header_comment):
    """渲染为与现有模型兼容的 processed_data.py"""
    lines = [
        '# ==============================================================================',
        f'# {header_comment}',
        '# 格式: numpy数组，用于遗传算法模型输入',
        '# ==============================================================================\n',
        'import numpy as np\n',
        '# ==================== 受灾点数据 ====================',
        '# 格式: [ID, 经度, 纬度, 受灾人口, 死亡失踪, 转移安置, 房屋损坏, 紧急系数]',
        format_array('disaster_points', data['disaster_points']) + '\n',
        '# ==================== 仓库数据 ====================',
        '# 格式: [ID, 经度, 纬度, 物资库存..., 车辆数量, 车辆容量]',
        format_array('warehouses', data['warehouses']) + '\n',
        format_array('distance_matrix', np.round(data['distance_matrix'], 2)) + '\n',
        format_array('road_conditions', np.round(data['road_conditions'], 4)) + '\n',
        format_array('transport_time', np.round(data['transport_time'], 4)) + '\n',
        format_array('demand', data['demand']) + '\n',
        format_array('inventory', data['inventory']) + '\n',
        format_array('urgency_weights', np.round(data['urgency_weights'], 6)) + '\n',
        format_array('material_weights', data['material_weights']) + '\n',
        'objective_weights = ' + py_json(data['objective_weights']) + '\n',
        f"NUM_POINTS = {data['disaster_points'].shape[0]}",
        f"NUM_WAREHOUSES = {data['warehouses'].shape[0]}",
        f"NUM_MATERIALS = {data['demand'].shape[1]}\n",
        'metadata = ' + py_json(data['metadata']) + '\n',
        'disaster_points_info = ' + py_json(data['disaster_points_info']) + '\n',
        'warehouses_info = ' + py_json(data['warehouses_info']) + '\n',
        f"material_names = {json.dumps(data['material_names'], ensure_ascii=False)}\n",
    ]
    return '\n'.join(lines)


def write_dataset_folder(folder_name, data, readme_content, extra_json=None):
    folder = os.path.join(ROOT, folder_name)
    processed_path = os.path.join(folder, 'processed_data', 'processed_data.py')
    write_processed_py(
        processed_path,
        render_processed_py(data, data['metadata']['dataset_name']),
    )

    with open(os.path.join(folder, 'metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(data['metadata'], f, ensure_ascii=False, indent=2)

    with open(os.path.join(folder, 'README.md'), 'w', encoding='utf-8') as f:
        f.write(readme_content)

    if extra_json:
        for name, obj in extra_json.items():
            with open(os.path.join(folder, name), 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)

    print(f'  ✓ {folder_name}: {data["metadata"]["disaster_points_count"]}点 × '
          f'{data["metadata"]["warehouses_count"]}仓 × {data["metadata"]["materials_count"]}物资')


def main():
    print('生成模拟数据集...\n')

    large = generate_large_scale()
    write_dataset_folder(
        'dataset_01_large_scale',
        large,
        readme_large_scale(large),
    )

    complex_data = generate_complex_scenario()
    write_dataset_folder(
        'dataset_02_complex_scenario',
        complex_data,
        readme_complex(complex_data),
        extra_json={'scenario_config.json': complex_data['scenario_config']},
    )

    print('\n全部数据集生成完成。')


def readme_large_scale(data):
    m = data['metadata']
    return f"""# 数据集 01：大规模洪涝应急调度

## 场景说明

本数据集模拟**大规模洪涝灾害**下的应急物资调运场景，重点体现**数据规模大、计算维度高**的特点，适用于验证遗传算法在大规模问题上的可扩展性。

## 数据规模

| 项目 | 数值 |
|------|------|
| 受灾点 | {m['disaster_points_count']} 个 |
| 储备仓库 | {m['warehouses_count']} 个 |
| 物资类型 | {m['materials_count']} 种（{', '.join(m['material_names'])}） |
| 受灾人口 | {m['total_population_affected']:,} 人 |
| 总需求量 | {m['total_demand']:,} 单位 |
| 总库存量 | {m['total_inventory']:,} 单位 |
| 最大运输能力 | {m['max_transport_capacity']:,} 单位 |

## 文件说明

```
dataset_01_large_scale/
├── README.md
├── metadata.json
└── processed_data/
    └── processed_data.py    # 模型可直接加载
```

## 使用方式

在 `源码/code/config.json` 中配置：

```json
{{
  "data": {{
    "disaster_points_file": "../../数据包/dataset_01_large_scale/processed_data/processed_data.py",
    "use_simulation": false
  }}
}}
```

然后运行：

```bash
cd 源码/code
python main_universal.py
```
"""


def readme_complex(data):
    m = data['metadata']
    return f"""# 数据集 02：复杂场景多灾害应急调度

## 场景说明

本数据集模拟**多灾害类型、多物资品类、异构仓库与复杂通行条件**下的应急调度场景，重点体现**数据描述复杂、约束维度丰富**的特点。

## 复杂特征

- **5种灾害类型**：洪水、内涝、山体滑坡、堰塞湖、复合灾害
- **5级通行条件**：良好 / 一般 / 较差 / 极差 / 中断
- **5类物资**：饮用水、食品、帐篷、药品、发电设备
- **异构仓库**：省级中心库、医疗专长库、山地应急库等
- **配送时间窗**：各受灾点设置不同配送时限（小时）
- **优先级分级**：一级 / 二级 / 三级紧急响应

## 数据规模

| 项目 | 数值 |
|------|------|
| 受灾点 | {m['disaster_points_count']} 个 |
| 储备仓库 | {m['warehouses_count']} 个 |
| 物资类型 | {m['materials_count']} 种 |
| 受灾人口 | {m['total_population_affected']:,} 人 |
| 总需求量 | {m['total_demand']:,} 单位 |
| 总库存量 | {m['total_inventory']:,} 单位 |

## 文件说明

```
dataset_02_complex_scenario/
├── README.md
├── metadata.json
├── scenario_config.json     # 复杂场景约束与描述配置
└── processed_data/
    └── processed_data.py
```

## 使用方式

```json
{{
  "data": {{
    "disaster_points_file": "../../数据包/dataset_02_complex_scenario/processed_data/processed_data.py",
    "use_simulation": false
  }}
}}
```
"""


if __name__ == '__main__':
    main()
