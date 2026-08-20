# ==============================================================================
# 快速验证脚本 - 测试通用版代码核心功能
# ==============================================================================

import numpy as np
import sys
sys.path.insert(0, '源码/code')

from data_loader import DataLoader, create_sample_data
from main_universal import UniversalAllocationModel

print("=" * 60)
print("通用版代码快速验证")
print("=" * 60)

# 测试1: 数据加载器
print("\n1. 测试数据加载器...")
loader = DataLoader('源码/code/config.json')
data = loader.load()

valid, errors = loader.validate_data(data)
if valid:
    print("   OK: 数据验证通过")
else:
    print("   ERROR: 数据验证失败")
    for error in errors:
        print(f"      - {error}")
    sys.exit(1)

# 测试2: 模型初始化
print("\n2. 测试模型初始化...")
try:
    model = UniversalAllocationModel(data)
    print("   OK: 模型初始化成功")
    print(f"   - 受灾点数量: {model.num_points}")
    print(f"   - 仓库数量: {model.num_warehouses}")
    print(f"   - 物资类型: {model.num_materials}")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# 测试3: 生成个体
print("\n3. 测试生成个体...")
try:
    individual = model.generate_individual()
    print(f"   OK: 个体维度 = {individual.shape}")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# 测试4: 计算适应度
print("\n4. 测试适应度计算...")
try:
    fitness = model.fitness(individual)
    print(f"   OK: 适应度 = {fitness:.4f}")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# 测试5: 测试自定义数据生成
print("\n5. 测试自定义数据生成...")
try:
    # 生成不同规模的数据
    custom_data = create_sample_data(num_points=10, num_warehouses=4, num_materials=5)
    custom_model = UniversalAllocationModel(custom_data)
    print("   OK: 自定义数据生成成功")
    print(f"   - 新受灾点数量: {custom_model.num_points}")
    print(f"   - 新仓库数量: {custom_model.num_warehouses}")
    print(f"   - 新物资类型: {custom_model.num_materials}")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# 测试6: 测试权重设置
print("\n6. 测试目标权重设置...")
try:
    new_weights = {
        'satisfaction': 0.5,
        'transport_cost': 0.1,
        'fairness': 0.2,
        'urgency': 0.1,
        'time_efficiency': 0.1
    }
    model.set_objective_weights(new_weights)
    print("   OK: 权重设置成功")
    print(f"   新权重: {model.objective_weights}")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# 测试7: 快速优化（少量迭代）
print("\n7. 测试优化过程（3次迭代）...")
try:
    best_solution, history = model.optimize(pop_size=10, generations=3)
    print(f"   OK: 优化完成")
    print(f"   - 最终适应度: {model.fitness(best_solution):.4f}")
    print(f"   - 迭代历史长度: {len(history)}")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("所有测试通过！通用版代码工作正常")
print("=" * 60)

# 显示使用说明
print("\n使用说明:")
print("  - 运行完整优化: python 源码/code/main_universal.py")
print("  - 调整参数: 修改 源码/code/config.json")
print("  - 查看配置说明: 查看 源码/code/config_README.md")
