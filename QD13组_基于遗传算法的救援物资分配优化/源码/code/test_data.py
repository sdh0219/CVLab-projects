# ==============================================================================
# 测试脚本 - 验证数据加载和基础功能
# ==============================================================================

import numpy as np

print("=" * 60)
print("数据验证测试")
print("=" * 60)

# 测试1: 加载数据包
print("\n1. 测试数据加载...")
try:
    from data.henan_disaster_processed_data import (
        disaster_points, warehouses, distance_matrix, 
        road_conditions, transport_time, demand, inventory,
        urgency_weights, material_weights, objective_weights,
        disaster_points_info, warehouses_info, metadata
    )
    print("   OK: 成功加载处理后数据")
    
    # 打印数据摘要
    print("\n   数据摘要:")
    print(f"   - 受灾点数量: {disaster_points.shape[0]}")
    print(f"   - 仓库数量: {warehouses.shape[0]}")
    print(f"   - 物资类型: {demand.shape[1]}")
    print(f"   - 总受灾人口: {int(disaster_points[:, 3].sum()):,}")
    print(f"   - 数据来源: {metadata['data_source']}")
    
except ImportError:
    print("   Warning: 无法加载外部数据，使用模拟数据")
    
    # 使用模拟数据
    disaster_points = np.array([
        [1, 113.65, 34.76, 1150100, 2300200, 575050, 23002, 4],
        [2, 112.98, 34.76, 63000, 126000, 31500, 1260, 3],
        [3, 113.42, 34.51, 293500, 587000, 146750, 5870, 3],
        [4, 113.72, 34.38, 80000, 160000, 40000, 1600, 2],
        [5, 113.38, 34.79, 210300, 420600, 105150, 4206, 3],
        [6, 113.03, 34.45, 151000, 302000, 75500, 3020, 2]
    ])
    
    warehouses = np.array([
        [1, 113.62, 34.75, 49903, 128546, 19102, 50, 100],
        [2, 112.45, 34.62, 35645, 91818, 13644, 35, 100],
        [3, 114.35, 34.78, 28516, 73455, 10915, 30, 100]
    ])
    
    distance_matrix = np.array([
        [0, 68, 35, 42, 25, 55],
        [125, 75, 110, 175, 95, 90],
        [78, 145, 110, 65, 130, 145]
    ])
    
    road_conditions = np.array([
        [1.0, 0.8, 0.9, 0.95, 0.85, 0.7],
        [0.7, 0.9, 0.75, 0.6, 0.8, 0.85],
        [0.85, 0.65, 0.7, 0.8, 0.6, 0.55]
    ])
    
    transport_time = np.array([
        [0.5, 1.5, 1.0, 1.0, 0.8, 1.5],
        [3.0, 2.0, 2.5, 4.0, 2.5, 2.5],
        [2.0, 3.5, 3.0, 1.5, 3.0, 3.5]
    ])
    
    demand = disaster_points[:, 4:7]
    inventory = warehouses[:, 3:6]
    
    print("\n   模拟数据摘要:")
    print(f"   - 受灾点数量: {disaster_points.shape[0]}")
    print(f"   - 仓库数量: {warehouses.shape[0]}")
    print(f"   - 物资类型: {demand.shape[1]}")

# 测试2: 验证矩阵维度
print("\n2. 验证矩阵维度...")
print(f"   - 受灾点矩阵: {disaster_points.shape}")
print(f"   - 仓库矩阵: {warehouses.shape}")
print(f"   - 距离矩阵: {distance_matrix.shape}")
print(f"   - 道路状况矩阵: {road_conditions.shape}")
print(f"   - 运输时间矩阵: {transport_time.shape}")
print(f"   - 需求矩阵: {demand.shape}")
print(f"   - 库存矩阵: {inventory.shape}")

# 测试3: 验证数据合理性
print("\n3. 验证数据合理性...")

# 检查非负约束
has_negative = np.any(demand < 0) or np.any(inventory < 0) or np.any(distance_matrix < 0)
if not has_negative:
    print("   OK: 所有数值均为非负数")
else:
    print("   ERROR: 存在负数数据")

# 检查距离矩阵对角线为0
diag_sum = np.sum(np.diag(distance_matrix))
if diag_sum == 0:
    print("   OK: 距离矩阵对角线为0")
else:
    print("   ERROR: 距离矩阵对角线不为0")

# 检查道路状况范围
road_valid = np.all(road_conditions >= 0) and np.all(road_conditions <= 1)
if road_valid:
    print("   OK: 道路状况值在合理范围内 [0, 1]")
else:
    print("   ERROR: 道路状况值超出范围")

# 测试4: 计算统计指标
print("\n4. 计算统计指标...")

total_demand = np.sum(demand)
total_inventory = np.sum(inventory)
inventory_rate = total_inventory / total_demand * 100

print(f"   - 总需求量: {int(total_demand):,}")
print(f"   - 总库存量: {int(total_inventory):,}")
print(f"   - 库存满足率: {inventory_rate:.2f}%")

print("\n" + "=" * 60)
print("数据验证完成!")
print("=" * 60)
