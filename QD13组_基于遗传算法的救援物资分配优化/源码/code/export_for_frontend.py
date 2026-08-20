# ==============================================================================
# 导出优化结果供 Vue 前端可视化使用
# 运行: cd 源码/code && python export_for_frontend.py
# 输出: 源码/frontend/public/data/results.json
# ==============================================================================

import json
import os
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import DataLoader
from main_universal import UniversalAllocationModel

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CODE_DIR)
OUTPUT_DIR = os.path.join(ROOT_DIR, 'output')
OUTPUT_PATH = os.path.join(OUTPUT_DIR, 'results.json')
FRONTEND_OUTPUT_PATH = os.path.join(
    ROOT_DIR, 'frontend', 'public', 'data', 'results.json'
)

DATASET_CONFIGS = [
    {
        'id': 'henan_disaster',
        'name': '河南洪涝灾害（基准案例）',
        'config': os.path.join(CODE_DIR, '../../数据包/config_examples/config_henan.json'),
    },
    {
        'id': 'dataset_01_large_scale',
        'name': '大规模洪涝模拟',
        'config': os.path.join(CODE_DIR, '../../数据包/config_examples/config_large_scale.json'),
    },
    {
        'id': 'dataset_02_complex_scenario',
        'name': '复杂场景多灾害模拟',
        'config': os.path.join(CODE_DIR, '../../数据包/config_examples/config_complex_scenario.json'),
    },
]


def solution_to_allocation_matrix(solution):
    """将三维分配方案转为仓库×受灾点热力图矩阵（物资合计）"""
    return np.sum(solution, axis=2).tolist()


def road_condition_label(value):
    """道路状况文字描述"""
    if value >= 0.85:
        return '通畅'
    if value >= 0.6:
        return '一般'
    return '受阻'


def export_transport_plan(solution, data, warehouse_names, point_names, material_names):
    """导出运输方案：调运路线、分物资明细、车辆调度与路况时间"""
    solution = np.asarray(solution)
    n_wh = solution.shape[0]
    n_pt = solution.shape[1]
    warehouses = data['warehouses']
    distances = data['distance_matrix']
    roads = data['road_conditions']
    times = data['transport_time']

    routes = []
    for w in range(n_wh):
        for p in range(n_pt):
            materials = []
            total = 0.0
            for m in range(solution.shape[2]):
                amt = float(solution[w, p, m])
                if amt > 0.5:
                    materials.append({
                        'name': material_names[m],
                        'amount': int(round(amt)),
                    })
                    total += amt
            if total <= 0.5:
                continue

            road = float(roads[w, p])
            dist = float(distances[w, p])
            time_h = float(times[w, p])
            cost = total * dist / (road + 1e-10)
            cap = float(warehouses[w, 7]) if warehouses.shape[1] > 7 else 100.0
            trips = int(np.ceil(total / (cap + 1e-10)))

            routes.append({
                'warehouseIndex': w,
                'warehouseName': warehouse_names[w],
                'pointIndex': p,
                'pointName': point_names[p],
                'materials': materials,
                'totalAmount': int(round(total)),
                'distance': round(dist, 1),
                'roadCondition': round(road, 2),
                'roadLabel': road_condition_label(road),
                'transportTime': round(time_h, 1),
                'transportCost': int(round(cost)),
                'estimatedTrips': trips,
            })

    routes.sort(key=lambda r: r['totalAmount'], reverse=True)

    warehouse_summary = []
    for w in range(n_wh):
        total_shipped = float(np.sum(solution[w, :, :]))
        vehicles = int(warehouses[w, 6]) if warehouses.shape[1] > 6 else 0
        cap = int(warehouses[w, 7]) if warehouses.shape[1] > 7 else 100
        max_transport = vehicles * cap
        vehicles_used = int(np.ceil(total_shipped / (cap + 1e-10))) if cap > 0 else 0
        dest_count = int(np.sum(np.sum(solution[w, :, :], axis=1) > 0.5))

        warehouse_summary.append({
            'name': warehouse_names[w],
            'vehicles': vehicles,
            'vehicleCapacity': cap,
            'maxTransport': max_transport,
            'vehiclesUsed': min(vehicles_used, vehicles) if vehicles > 0 else vehicles_used,
            'utilization': round(vehicles_used / vehicles, 2) if vehicles > 0 else 0,
            'totalShipped': int(round(total_shipped)),
            'destinationCount': dest_count,
        })

    return {
        'routeCount': len(routes),
        'totalShipped': int(round(np.sum(solution))),
        'routes': routes,
        'warehouseSummary': warehouse_summary,
    }


def build_transport_plan_from_matrix(matrix, data, warehouse_names, point_names, material_names):
    """从二维合计矩阵近似生成运输方案（按受灾点需求比例拆分物资）"""
    matrix = np.asarray(matrix)
    demand = data['demand']
    n_wh, n_pt = matrix.shape
    n_mat = len(material_names)

    solution = np.zeros((n_wh, n_pt, n_mat))
    for w in range(n_wh):
        for p in range(n_pt):
            total = matrix[w, p]
            if total <= 0.5:
                continue
            demand_p = demand[p].astype(float)
            demand_sum = demand_p.sum()
            if demand_sum > 0:
                solution[w, p, :] = total * demand_p / demand_sum
            else:
                solution[w, p, :] = total / n_mat

    return export_transport_plan(solution, data, warehouse_names, point_names, material_names)


def get_point_names(data):
    info = data.get('disaster_points_info') or {}
    if info:
        keys = sorted(info.keys(), key=lambda k: int(k) if str(k).isdigit() else str(k))
        return [info[k].get('name', f'受灾点{k}') for k in keys]
    n = data['disaster_points'].shape[0]
    return [f'受灾点{i + 1:03d}' for i in range(n)]


def get_material_names(data):
    if data.get('material_names'):
        return list(data['material_names'])
    meta = data.get('metadata') or {}
    if meta.get('material_names'):
        return list(meta['material_names'])
    n = data['demand'].shape[1]
    defaults = ['饮用水', '方便面', '帐篷', '医疗包', '发电机']
    return defaults[:n]


def metrics_to_dict(metrics):
    return {
        'satisfaction_rate': float(metrics['satisfaction_rate']),
        'fairness': float(metrics['fairness']),
        'urgency_score': float(metrics['urgency_score']),
        'time_efficiency': float(metrics['time_efficiency']),
        'transport_cost': float(metrics['transport_cost']),
        'detailed_satisfaction': [float(x) for x in metrics['detailed_satisfaction']],
        'vehicle_usage': [float(x) for x in metrics['vehicle_usage']],
    }


def export_input_data(data, point_names, warehouse_names, material_names):
    """导出模型输入的初始数据，供前端「初始数据」板块展示"""
    disaster_info = data.get('disaster_points_info') or {}
    n_points = data['disaster_points'].shape[0]
    n_warehouses = data['warehouses'].shape[0]

    disaster_points = []
    for i, name in enumerate(point_names):
        info = disaster_info.get(i + 1, disaster_info.get(str(i + 1), {}))
        row = data['disaster_points'][i]
        disaster_points.append({
            'name': name,
            'population': int(row[3]) if row.shape[0] > 3 else 0,
            'casualties': int(info.get('casualties', row[4] if row.shape[0] > 4 else 0)),
            'urgency': float(info.get('urgency', row[7] if row.shape[0] > 7 else 1)),
            'demand': [int(x) for x in data['demand'][i]],
        })

    warehouses = []
    for i, name in enumerate(warehouse_names):
        row = data['warehouses'][i]
        warehouses.append({
            'name': name,
            'vehicles': int(row[6]) if row.shape[0] > 6 else 0,
            'vehicleCapacity': int(row[7]) if row.shape[0] > 7 else 0,
            'maxTransport': int(row[6] * row[7]) if row.shape[0] > 7 else 0,
            'inventory': [int(x) for x in data['inventory'][i]],
        })

    return {
        'materialNames': material_names,
        'demandMatrix': [[int(x) for x in row] for row in data['demand']],
        'inventoryMatrix': [[int(x) for x in row] for row in data['inventory']],
        'disasterPoints': disaster_points,
        'warehouses': warehouses,
        'transportNetwork': {
            'distanceMatrix': [[round(float(x), 1) for x in row] for row in data['distance_matrix']],
            'roadConditions': [[round(float(x), 2) for x in row] for row in data['road_conditions']],
            'transportTime': [[round(float(x), 1) for x in row] for row in data['transport_time']],
        },
        'totals': {
            'population': int(data['disaster_points'][:, 3].sum()),
            'demand': int(data['demand'].sum()),
            'inventory': int(data['inventory'].sum()),
            'disasterPointsCount': n_points,
            'warehousesCount': n_warehouses,
            'materialsCount': len(material_names),
        },
    }


def export_dataset(dataset_cfg):
    """对单个数据集运行遗传算法并导出结果"""
    config_path = os.path.normpath(dataset_cfg['config'])
    print(f"\n{'=' * 60}")
    print(f"处理数据集: {dataset_cfg['name']}")
    print(f"配置文件: {config_path}")
    print('=' * 60)

    loader = DataLoader(config_path)
    data = loader.load()
    valid, errors = loader.validate_data(data)
    if not valid:
        raise RuntimeError(f"数据验证失败 ({dataset_cfg['id']}): " + '; '.join(errors))

    config = loader.get_config()
    algo = config.get('algorithm', {})
    print(f"算法参数: pop_size={algo.get('pop_size')}, generations={algo.get('generations')}")

    model = UniversalAllocationModel(data, config)

    print('生成初始方案...')
    initial_solution = model.generate_individual()
    initial_metrics = model.analyze_solution(initial_solution)

    print('运行遗传算法优化...')
    best_solution, fitness_history = model.optimize()
    optimized_metrics = model.analyze_solution(best_solution)

    material_names = get_material_names(data)
    metadata = data.get('metadata') or {}
    point_names = get_point_names(data)
    warehouse_names = list(data.get('warehouses_info', {}).keys()) or [
        f'仓库{i + 1}' for i in range(data['warehouses'].shape[0])
    ]

    result = {
        'id': dataset_cfg['id'],
        'name': dataset_cfg['name'],
        'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'algorithm': {
            'pop_size': algo.get('pop_size'),
            'generations': algo.get('generations'),
            'mutation_rate': algo.get('mutation_rate'),
        },
        'summary': {
            'disasterPointsCount': int(data['disaster_points'].shape[0]),
            'warehousesCount': int(data['warehouses'].shape[0]),
            'materialsCount': int(data['demand'].shape[1]),
            'materialNames': material_names,
            'totalPopulation': int(data['disaster_points'][:, 3].sum()),
            'totalDemand': int(data['demand'].sum()),
            'totalInventory': int(data['inventory'].sum()),
            'scenario': (metadata or {}).get('scenario')
                or (metadata or {}).get('data_source', ''),
        },
        'pointNames': point_names,
        'warehouseNames': warehouse_names,
        'materialNames': material_names,
        'inputData': export_input_data(data, point_names, warehouse_names, material_names),
        'initialMetrics': metrics_to_dict(initial_metrics),
        'optimizedMetrics': metrics_to_dict(optimized_metrics),
        'fitnessHistory': [float(x) if not np.isnan(x) else 0.0 for x in fitness_history],
        'initialFitness': float(fitness_history[0]) if fitness_history else 0.0,
        'finalFitness': float(fitness_history[-1]) if fitness_history else 0.0,
        'allocationMatrix': solution_to_allocation_matrix(best_solution),
        'initialAllocationMatrix': solution_to_allocation_matrix(initial_solution),
        'initialTransportPlan': export_transport_plan(
            initial_solution, data, warehouse_names, point_names, material_names
        ),
        'optimizedTransportPlan': export_transport_plan(
            best_solution, data, warehouse_names, point_names, material_names
        ),
    }

    print(f"  优化后满足率: {optimized_metrics['satisfaction_rate']:.2f}%")
    print(f"  适应度历史: {len(fitness_history)} 代")
    return result


def build_payload(datasets):
    """组装多数据集结果 JSON 结构"""
    return {
        'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'datasets': datasets,
        # 兼容旧版前端：默认展示第一个数据集
        **datasets[0],
    }


def save_results(payload):
    """保存到 output 目录并同步到前端 public/data"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(FRONTEND_OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(FRONTEND_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n导出成功: {OUTPUT_PATH}")
    print(f"  已同步至前端: {FRONTEND_OUTPUT_PATH}")
    print(f"  共 {len(payload['datasets'])} 组数据集结果")
    return payload


def export_all_datasets(dataset_ids=None):
    """运行遗传算法并导出结果；dataset_ids 为 None 时处理全部数据集"""
    configs = DATASET_CONFIGS
    if dataset_ids:
        id_set = set(dataset_ids)
        configs = [c for c in DATASET_CONFIGS if c['id'] in id_set]
        if not configs:
            raise ValueError(f'未知数据集: {dataset_ids}')

    datasets = []
    for cfg in configs:
        datasets.append(export_dataset(cfg))

    # 仅更新部分数据集时，合并已有缓存
    if dataset_ids and os.path.isfile(OUTPUT_PATH):
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        merged = {d['id']: d for d in existing.get('datasets', [])}
        for d in datasets:
            merged[d['id']] = d
        order = [c['id'] for c in DATASET_CONFIGS]
        datasets = [merged[i] for i in order if i in merged]

    payload = build_payload(datasets)
    return save_results(payload)


def load_cached_results():
    """读取 output 目录中已保存的结果"""
    if not os.path.isfile(OUTPUT_PATH):
        return None
    with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def sync_to_frontend():
    """将 output 缓存同步到前端静态目录"""
    if not os.path.isfile(OUTPUT_PATH):
        return False
    os.makedirs(os.path.dirname(FRONTEND_OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    with open(FRONTEND_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return True


if __name__ == '__main__':
    export_all_datasets()
