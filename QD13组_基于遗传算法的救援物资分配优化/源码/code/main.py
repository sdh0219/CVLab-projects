# ==============================================================================
# 河南洪灾应急物资分配优化 - 主程序
# 基于遗传算法的救援物资分配优化模型
# ==============================================================================

import numpy as np
import matplotlib.pyplot as plt
import os

from ga_enhanced import GAEnhancedMixin

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ==================== 数据读取模块 ====================
def load_data():
    """
    加载处理后的河南洪灾数据
    返回: 受灾点数据、仓库数据、距离矩阵、道路状况、运输时间
    """
    # 从数据包加载数据
    try:
        from data.henan_disaster_processed_data import (
            disaster_points, warehouses, distance_matrix, 
            road_conditions, transport_time, demand, inventory,
            urgency_weights, material_weights, objective_weights,
            disaster_points_info, warehouses_info
        )
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
            'warehouses_info': warehouses_info
        }
    except ImportError:
        print("警告: 无法加载外部数据，使用内置模拟数据")
        return generate_simulation_data()

def generate_simulation_data():
    """生成模拟数据（备用）"""
    # 受灾点数据
    disaster_points = np.array([
        [1, 113.65, 34.76, 1150100, 2300200, 575050, 23002, 4],
        [2, 112.98, 34.76, 63000, 126000, 31500, 1260, 3],
        [3, 113.42, 34.51, 293500, 587000, 146750, 5870, 3],
        [4, 113.72, 34.38, 80000, 160000, 40000, 1600, 2],
        [5, 113.38, 34.79, 210300, 420600, 105150, 4206, 3],
        [6, 113.03, 34.45, 151000, 302000, 75500, 3020, 2]
    ])
    
    # 仓库数据
    warehouses = np.array([
        [1, 113.62, 34.75, 49903, 128546, 19102, 50, 100],
        [2, 112.45, 34.62, 35645, 91818, 13644, 35, 100],
        [3, 114.35, 34.78, 28516, 73455, 10915, 30, 100]
    ])
    
    # 距离矩阵
    distance_matrix = np.array([
        [0, 68, 35, 42, 25, 55],
        [125, 75, 110, 175, 95, 90],
        [78, 145, 110, 65, 130, 145]
    ])
    
    # 道路状况
    road_conditions = np.array([
        [1.0, 0.8, 0.9, 0.95, 0.85, 0.7],
        [0.7, 0.9, 0.75, 0.6, 0.8, 0.85],
        [0.85, 0.65, 0.7, 0.8, 0.6, 0.55]
    ])
    
    # 运输时间
    transport_time = np.array([
        [0.5, 1.5, 1.0, 1.0, 0.8, 1.5],
        [3.0, 2.0, 2.5, 4.0, 2.5, 2.5],
        [2.0, 3.5, 3.0, 1.5, 3.0, 3.5]
    ])
    
    # 需求矩阵
    demand = disaster_points[:, 4:7]
    
    # 库存矩阵
    inventory = warehouses[:, 3:6]
    
    # 权重设置
    urgency_weights = np.array([0.4, 0.25, 0.2, 0.05, 0.07, 0.03])
    material_weights = np.array([0.5, 0.35, 0.15])
    objective_weights = {
        'satisfaction': 0.35,
        'transport_cost': 0.15,
        'fairness': 0.2,
        'urgency': 0.2,
        'time_efficiency': 0.1
    }
    
    # 详细信息
    disaster_points_info = {
        1: {'name': '郑州', 'population': 1150100, 'casualties': 112132, 'urgency': 21.6},
        2: {'name': '巩义', 'population': 63000, 'casualties': 84203, 'urgency': 2.02},
        3: {'name': '新密', 'population': 293500, 'casualties': 58265, 'urgency': 3.36},
        4: {'name': '新郑', 'population': 80000, 'casualties': 17865, 'urgency': 1.0},
        5: {'name': '荥阳', 'population': 210300, 'casualties': 96742, 'urgency': 2.86},
        6: {'name': '登封', 'population': 151000, 'casualties': 13856, 'urgency': 1.28}
    }
    
    warehouses_info = {
        '郑州储备库': {'location': (113.62, 34.75), 'inventory': [49903, 128546, 19102]},
        '洛阳储备库': {'location': (112.45, 34.62), 'inventory': [35645, 91818, 13644]},
        '开封储备库': {'location': (114.35, 34.78), 'inventory': [28516, 73455, 10915]}
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
        'warehouses_info': warehouses_info
    }

# ==================== 遗传算法模型 ====================
class AllocationModel(GAEnhancedMixin):
    def __init__(self, data):
        """
        初始化物资分配模型
        参数: data - 包含所有数据的字典
        """
        self.disaster_points = data['disaster_points']
        self.warehouses = data['warehouses']
        self.distances = data['distance_matrix']
        self.road_conditions = data['road_conditions']
        self.transport_time = data['transport_time']
        self.demand = data['demand']
        self.inventory = data['inventory']
        self.urgency_weights = data['urgency_weights']
        self.material_weights = data['material_weights']
        self.objective_weights = data['objective_weights']
        # 兼容旧数据文件中 'cost' 键名
        if 'cost' in self.objective_weights and 'transport_cost' not in self.objective_weights:
            self.objective_weights['transport_cost'] = self.objective_weights.pop('cost')
        
        # 计算维度
        self.num_points = self.disaster_points.shape[0]
        self.num_warehouses = self.warehouses.shape[0]
        self.num_materials = self.demand.shape[1]
        
        # 提取车辆信息
        self.vehicles = self.warehouses[:, 6]
        self.vehicle_capacity = self.warehouses[:, 7]
    
    def max_transport_capacity(self, w):
        """仓库最大运输量（车辆数 × 单车容量）"""
        return self.vehicles[w] * self.vehicle_capacity[w]

    def _enforce_inventory_limit(self, individual):
        """修复库存约束：按仓库×物资等比缩放"""
        repaired = individual.copy()
        for w in range(self.num_warehouses):
            for m in range(self.num_materials):
                total_allocated = np.sum(repaired[w, :, m])
                if total_allocated > self.inventory[w, m]:
                    ratio = self.inventory[w, m] / (total_allocated + 1e-10)
                    repaired[w, :, m] *= ratio
        return repaired

    def _enforce_demand_limit(self, individual):
        """修复需求约束：按受灾点×物资等比缩放"""
        repaired = individual.copy()
        for p in range(self.num_points):
            for m in range(self.num_materials):
                total_received = np.sum(repaired[:, p, m])
                if total_received > self.demand[p, m]:
                    ratio = self.demand[p, m] / (total_received + 1e-10)
                    repaired[:, p, m] *= ratio
        return repaired

    def _enforce_vehicle_limit(self, individual):
        """修复车辆约束：按仓库等比缩放总运输量"""
        repaired = individual.copy()
        for w in range(self.num_warehouses):
            total_from_warehouse = np.sum(repaired[w, :, :])
            max_transport = self.max_transport_capacity(w)
            if total_from_warehouse > max_transport:
                ratio = max_transport / (total_from_warehouse + 1e-10)
                repaired[w, :, :] *= ratio
        return repaired

    def _generate_individual_road_based(self):
        """旧版启发式：按道路状况分配（用于保持多样性）"""
        individual = np.zeros((self.num_warehouses, self.num_points, self.num_materials))

        for w in range(self.num_warehouses):
            for m in range(self.num_materials):
                max_from_warehouse = self.inventory[w, m]
                if max_from_warehouse <= 0:
                    continue

                road_factor = self.road_conditions[w, :]
                if road_factor.sum() > 0:
                    ratios = road_factor / road_factor.sum()
                else:
                    ratios = np.ones(self.num_points) / self.num_points

                allocations = ratios * max_from_warehouse
                allocations = np.minimum(allocations, self.demand[:, m])

                for p in range(self.num_points):
                    allocations[p] = min(
                        allocations[p],
                        self.demand[p, m] - np.sum(individual[:, p, m])
                    )

                individual[w, :, m] = allocations

        return individual

    def _generate_individual_urgency_first(self):
        """
        改进初始化：紧急程度优先 + 路况/距离修正 + 车辆运力预算
        目标：生成更贴近救援逻辑的可行初始解
        """
        individual = np.zeros((self.num_warehouses, self.num_points, self.num_materials))

        remaining_inventory = self.inventory.copy().astype(float)
        remaining_demand = self.demand.copy().astype(float)

        # 为每个仓库分配“总可运量预算”
        for w in range(self.num_warehouses):
            budget = float(self.max_transport_capacity(w))
            if budget <= 0:
                continue

            # 点权重：紧急程度 × 路况 ÷ (距离+1) ÷ sqrt(需求总量)
            # 说明：直接按紧急度会把运力“灌”到需求极大的点，平均满足率会被大分母拉低；
            # 用 sqrt 归一化可在“紧急优先”和“提升满足率”之间取得更稳的平衡。
            urgency = self.urgency_weights.astype(float)
            road = self.road_conditions[w, :].astype(float)
            dist = self.distances[w, :].astype(float)
            demand_total = self.demand.sum(axis=1).astype(float)
            demand_norm = np.sqrt(demand_total + 1e-10)
            point_weight = urgency * np.clip(road, 0.0, None) / (dist + 1.0) / demand_norm

            if np.all(point_weight <= 0):
                point_weight = np.ones(self.num_points, dtype=float)

            point_weight = point_weight / (point_weight.sum() + 1e-10)

            # 先按权重给每个受灾点一个“可运量配额”
            point_quota = budget * point_weight

            for p in np.argsort(-urgency):  # 紧急点优先分配
                if point_quota[p] <= 0:
                    continue

                demand_p = remaining_demand[p, :]
                if demand_p.sum() <= 0:
                    continue

                # 在该点的总配额内按“剩余需求占比”分摊到各物资
                total_quota = float(point_quota[p])
                share = demand_p / (demand_p.sum() + 1e-10)

                for m in range(self.num_materials):
                    if total_quota <= 0:
                        break
                    if remaining_inventory[w, m] <= 0 or remaining_demand[p, m] <= 0:
                        continue

                    alloc = total_quota * float(share[m])
                    alloc = min(alloc, remaining_inventory[w, m], remaining_demand[p, m])

                    individual[w, p, m] += alloc
                    remaining_inventory[w, m] -= alloc
                    remaining_demand[p, m] -= alloc

        return individual

    def generate_individual(self):
        """生成单个可行分配方案（用于初始种群）"""
        # 70% 使用“紧急程度优先”初始化，30% 使用旧策略增加多样性
        if np.random.random() < 0.7:
            individual = self._generate_individual_urgency_first()
        else:
            individual = self._generate_individual_road_based()

        return self.repair(individual)
    
    def generate_population(self, size):
        """生成初始种群"""
        return [self.generate_individual() for _ in range(size)]
    
    def calculate_satisfaction_rate(self, individual):
        """计算满足率"""
        received = np.sum(individual, axis=0)
        satisfaction_rate = np.minimum(received / (self.demand + 1e-10), 1.0)
        overall_satisfaction = np.average(satisfaction_rate, axis=1, weights=self.material_weights)
        return satisfaction_rate, overall_satisfaction
    
    def calculate_transport_cost(self, individual):
        """计算运输成本"""
        total_cost = 0.0
        for w in range(self.num_warehouses):
            for p in range(self.num_points):
                transport_amount = np.sum(individual[w, p, :])
                if transport_amount > 0:
                    cost_factor = 1.0 / (self.road_conditions[w, p] + 1e-10)
                    total_cost += transport_amount * self.distances[w, p] * cost_factor
        return total_cost
    
    def calculate_fairness(self, individual):
        """计算公平性"""
        _, overall_satisfaction = self.calculate_satisfaction_rate(individual)
        variance = np.var(overall_satisfaction)
        return 1.0 / (1.0 + variance)
    
    def calculate_urgency_score(self, individual):
        """计算紧急程度得分"""
        _, overall_satisfaction = self.calculate_satisfaction_rate(individual)
        return np.sum(overall_satisfaction * self.urgency_weights)
    
    def calculate_time_efficiency(self, individual):
        """计算时间效率"""
        total_time = 0.0
        for w in range(self.num_warehouses):
            for p in range(self.num_points):
                transport_amount = np.sum(individual[w, p, :])
                if transport_amount > 0:
                    total_time += transport_amount * self.transport_time[w, p]
        return 1.0 / (1.0 + total_time / 1000.0)
    
    def calculate_vehicle_usage(self, individual):
        """计算车辆使用情况"""
        vehicle_usage = np.zeros(self.num_warehouses)
        for w in range(self.num_warehouses):
            total_from_warehouse = np.sum(individual[w, :, :])
            vehicle_usage[w] = np.ceil(total_from_warehouse / (self.vehicle_capacity[w] + 1e-10))
        return vehicle_usage
    
    def is_feasible(self, individual):
        """检查方案可行性"""
        # 库存约束
        for w in range(self.num_warehouses):
            for m in range(self.num_materials):
                if np.sum(individual[w, :, m]) > self.inventory[w, m] + 1e-6:
                    return False
        
        # 车辆约束
        vehicle_usage = self.calculate_vehicle_usage(individual)
        for w in range(self.num_warehouses):
            if vehicle_usage[w] > self.vehicles[w]:
                return False
        
        return True
    
    def fitness(self, individual):
        """计算综合适应度"""
        if not self.is_feasible(individual):
            return -1.0
        
        _, overall_satisfaction = self.calculate_satisfaction_rate(individual)
        satisfaction_score = np.mean(overall_satisfaction)
        
        cost_score = 1.0 / (1.0 + self.calculate_transport_cost(individual) / 10000.0)
        fairness_score = self.calculate_fairness(individual)
        urgency_score = self.calculate_urgency_score(individual)
        time_score = self.calculate_time_efficiency(individual)
        
        weights = self.objective_weights
        return (
            weights['satisfaction'] * satisfaction_score +
            weights['transport_cost'] * cost_score +
            weights['fairness'] * fairness_score +
            weights['urgency'] * urgency_score +
            weights['time_efficiency'] * time_score
        )
    
    def repair(self, individual):
        """修复不可行解（库存、需求、车辆约束迭代收敛）"""
        repaired = individual.copy()
        for _ in range(5):
            repaired = self._enforce_inventory_limit(repaired)
            repaired = self._enforce_demand_limit(repaired)
            repaired = self._enforce_vehicle_limit(repaired)
        return repaired

    def optimize(self, pop_size=100, generations=50, mutation_rate=0.1, elite_ratio=0.1):
        """遗传算法优化主函数（增强版）"""
        return self.optimize_enhanced(
            pop_size=pop_size,
            generations=generations,
            mutation_rate=mutation_rate,
            elite_ratio=elite_ratio,
            crossover_rate=0.85,
            tournament_size=3,
            local_search_steps=4,
            stagnation_patience=6,
        )
    
    def analyze_solution(self, individual):
        """分析方案指标"""
        _, overall_satisfaction = self.calculate_satisfaction_rate(individual)
        return {
            'satisfaction_rate': np.mean(overall_satisfaction) * 100,
            'fairness': self.calculate_fairness(individual),
            'urgency_score': self.calculate_urgency_score(individual),
            'time_efficiency': self.calculate_time_efficiency(individual),
            'transport_cost': self.calculate_transport_cost(individual),
            'vehicle_usage': self.calculate_vehicle_usage(individual),
            'detailed_satisfaction': overall_satisfaction * 100
        }

# ==================== 可视化模块 ====================
def plot_satisfaction_comparison(initial_metrics, optimized_metrics, point_names):
    """绘制优化前后满足率对比图"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    x = np.arange(len(point_names))
    width = 0.35
    
    ax1.bar(x - width/2, initial_metrics['detailed_satisfaction'], width, label='优化前')
    ax1.bar(x + width/2, optimized_metrics['detailed_satisfaction'], width, label='优化后')
    ax1.set_xlabel('受灾点')
    ax1.set_ylabel('满足率 (%)')
    ax1.set_title('各受灾点物资满足率对比')
    ax1.set_xticks(x)
    ax1.set_xticklabels(point_names, rotation=45)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 汇总指标对比
    metrics = ['satisfaction_rate', 'fairness', 'urgency_score', 'time_efficiency']
    metric_labels = ['满足率 (%)', '公平性', '紧急程度得分', '时间效率']
    initial_vals = [initial_metrics[m] for m in metrics]
    optimized_vals = [optimized_metrics[m] for m in metrics]
    
    ax2.bar(x[:4] - width/2, initial_vals, width, label='优化前')
    ax2.bar(x[:4] + width/2, optimized_vals, width, label='优化后')
    ax2.set_xlabel('指标')
    ax2.set_ylabel('数值')
    ax2.set_title('综合指标对比')
    ax2.set_xticks(x[:4])
    ax2.set_xticklabels(metric_labels, rotation=45)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig

def plot_fitness_history(fitness_history):
    """绘制适应度变化曲线"""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(range(1, len(fitness_history) + 1), fitness_history, 'b-', linewidth=2)
    ax.set_xlabel('迭代代数')
    ax.set_ylabel('最优适应度')
    ax.set_title('遗传算法迭代过程（全局最优）')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(1, len(fitness_history))
    return fig

def plot_allocation_heatmap(solution, warehouse_names, point_names):
    """绘制分配方案热力图"""
    total_allocation = np.sum(solution, axis=2)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(total_allocation, cmap='YlOrRd', aspect='auto')
    
    ax.set_xticks(np.arange(len(point_names)))
    ax.set_yticks(np.arange(len(warehouse_names)))
    ax.set_xticklabels(point_names)
    ax.set_yticklabels(warehouse_names)
    
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right', rotation_mode='anchor')
    
    # 添加数值标签
    for i in range(len(warehouse_names)):
        for j in range(len(point_names)):
            text = ax.text(j, i, f'{int(total_allocation[i, j])}',
                          ha='center', va='center', color='black', fontsize=8)
    
    ax.set_xlabel('受灾点')
    ax.set_ylabel('仓库')
    ax.set_title('物资分配方案热力图')
    plt.colorbar(im, label='分配数量')
    
    plt.tight_layout()
    return fig

# ==================== 主程序入口 ====================
def main():
    print("=" * 80)
    print("河南洪灾应急物资分配优化系统")
    print("基于遗传算法的救援物资分配模型")
    print("=" * 80)
    
    # 加载数据
    print("\n1. 加载数据...")
    data = load_data()
    point_names = [info['name'] for info in data['disaster_points_info'].values()]
    warehouse_names = list(data['warehouses_info'].keys())
    
    # 打印数据摘要
    print("\n数据摘要:")
    print(f"  - 受灾点数量: {data['disaster_points'].shape[0]}")
    print(f"  - 仓库数量: {data['warehouses'].shape[0]}")
    print(f"  - 物资类型: {data['demand'].shape[1]}")
    print(f"  - 总受灾人口: {int(data['disaster_points'][:, 3].sum()):,}")
    
    # 创建模型
    print("\n2. 初始化模型...")
    model = AllocationModel(data)
    
    # 生成初始方案
    print("\n3. 生成初始方案...")
    initial_solution = model.generate_individual()
    initial_metrics = model.analyze_solution(initial_solution)
    
    print("\n初始方案指标:")
    print(f"  - 平均满足率: {initial_metrics['satisfaction_rate']:.2f}%")
    print(f"  - 公平性指数: {initial_metrics['fairness']:.4f}")
    print(f"  - 紧急程度得分: {initial_metrics['urgency_score']:.4f}")
    print(f"  - 时间效率: {initial_metrics['time_efficiency']:.4f}")
    print(f"  - 运输成本: {int(initial_metrics['transport_cost']):,}")
    
    # 运行优化
    print("\n4. 运行遗传算法优化...")
    best_solution, fitness_history = model.optimize(pop_size=100, generations=50)
    optimized_metrics = model.analyze_solution(best_solution)
    
    print("\n优化后方案指标:")
    print(f"  - 平均满足率: {optimized_metrics['satisfaction_rate']:.2f}%")
    print(f"  - 公平性指数: {optimized_metrics['fairness']:.4f}")
    print(f"  - 紧急程度得分: {optimized_metrics['urgency_score']:.4f}")
    print(f"  - 时间效率: {optimized_metrics['time_efficiency']:.4f}")
    print(f"  - 运输成本: {int(optimized_metrics['transport_cost']):,}")
    
    # 对比分析
    print("\n5. 优化效果对比:")
    print(f"  - 满足率提升: {optimized_metrics['satisfaction_rate'] - initial_metrics['satisfaction_rate']:.2f}%")
    print(f"  - 公平性提升: {(optimized_metrics['fairness'] - initial_metrics['fairness']) / initial_metrics['fairness'] * 100:.2f}%")
    print(f"  - 运输成本变化: {(optimized_metrics['transport_cost'] - initial_metrics['transport_cost']) / initial_metrics['transport_cost'] * 100:.2f}%")
    
    # 生成可视化
    print("\n6. 生成可视化图表...")
    
    # 创建输出目录
    os.makedirs('output', exist_ok=True)
    
    # 绘制满足率对比图
    fig1 = plot_satisfaction_comparison(initial_metrics, optimized_metrics, point_names)
    fig1.savefig('output/satisfaction_comparison.png', dpi=300, bbox_inches='tight')
    print("  - 满足率对比图: output/satisfaction_comparison.png")
    
    # 绘制适应度变化曲线
    fig2 = plot_fitness_history(fitness_history)
    fig2.savefig('output/fitness_history.png', dpi=300, bbox_inches='tight')
    print("  - 适应度变化曲线: output/fitness_history.png")
    
    # 绘制分配热力图
    fig3 = plot_allocation_heatmap(best_solution, warehouse_names, point_names)
    fig3.savefig('output/allocation_heatmap.png', dpi=300, bbox_inches='tight')
    print("  - 分配热力图: output/allocation_heatmap.png")
    
    # 保存结果数据
    np.save('output/initial_solution.npy', initial_solution)
    np.save('output/optimized_solution.npy', best_solution)
    np.save('output/fitness_history.npy', fitness_history)
    print("\n  - 结果数据已保存到 output/ 目录")
    
    print("\n" + "=" * 80)
    print("物资分配优化完成！")
    print("=" * 80)

if __name__ == '__main__':
    main()
