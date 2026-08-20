# ==============================================================================
# 通用版主程序 - 基于遗传算法的物资分配优化
# 特点：支持配置文件、数据自动适配、可扩展评价指标
# ==============================================================================

import numpy as np
import matplotlib.pyplot as plt
import os
import json

# 设置中文字体支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 导入数据加载器
from data_loader import DataLoader, create_sample_data
from ga_enhanced import GAEnhancedMixin

class UniversalAllocationModel(GAEnhancedMixin):
    """通用物资分配模型，支持自定义数据和评价指标"""
    
    def __init__(self, data, config=None):
        """
        初始化模型
        
        参数:
            data: 数据字典
            config: 配置字典（可选）
        """
        self.data = data
        self.config = config or self._get_default_config()
        
        # 自动检测数据规模
        self.num_points = data['disaster_points'].shape[0]
        self.num_warehouses = data['warehouses'].shape[0]
        self.num_materials = data['demand'].shape[1]
        
        # 提取数据
        self.disaster_points = data['disaster_points']
        self.warehouses = data['warehouses']
        self.distances = data['distance_matrix']
        self.road_conditions = data['road_conditions']
        self.transport_time = data['transport_time']
        self.demand = data['demand']
        self.inventory = data['inventory']
        
        # 提取或计算权重
        self.urgency_weights = data.get('urgency_weights')
        if self.urgency_weights is None:
            self.urgency_weights = self._calculate_urgency_weights()
        
        self.material_weights = data.get('material_weights')
        if self.material_weights is None:
            self.material_weights = np.ones(self.num_materials) / self.num_materials
        
        self.objective_weights = data.get('objective_weights', self._get_default_objective_weights())
        
        # 提取车辆信息
        self.vehicles = self.warehouses[:, 6]
        self.vehicle_capacity = self.warehouses[:, 7]
        
        print(f"模型初始化完成:")
        print(f"  - 受灾点数量: {self.num_points}")
        print(f"  - 仓库数量: {self.num_warehouses}")
        print(f"  - 物资类型: {self.num_materials}")
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            'algorithm': {
                'pop_size': 100,
                'generations': 50,
                'mutation_rate': 0.1,
                'crossover_rate': 0.8,
                'elite_ratio': 0.1
            }
        }
    
    def _get_default_objective_weights(self):
        """获取默认目标权重"""
        return {
            'satisfaction': 0.35,
            'transport_cost': 0.15,
            'fairness': 0.2,
            'urgency': 0.2,
            'time_efficiency': 0.1
        }
    
    def _calculate_urgency_weights(self):
        """计算紧急程度权重"""
        if self.disaster_points.shape[1] > 7:
            urgency = self.disaster_points[:, 7]
        else:
            urgency = np.ones(self.num_points)
        
        if np.sum(urgency) > 0:
            return urgency / np.sum(urgency)
        else:
            return np.ones(self.num_points) / self.num_points
    
    def set_objective_weights(self, weights):
        """设置目标权重"""
        self.objective_weights = weights
        print("目标权重已更新:", weights)

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
                    max_possible = self.demand[p, m] - np.sum(individual[:, p, m])
                    allocations[p] = min(allocations[p], max(0, max_possible))
                
                individual[w, :, m] = allocations
        
        return individual
    
    def _generate_individual_urgency_first(self):
        """改进初始化：紧急程度优先 + 路况/距离修正 + 车辆运力预算"""
        individual = np.zeros((self.num_warehouses, self.num_points, self.num_materials))
        
        remaining_inventory = self.inventory.copy().astype(float)
        remaining_demand = self.demand.copy().astype(float)
        
        urgency = self.urgency_weights.astype(float)
        
        for w in range(self.num_warehouses):
            budget = float(self.max_transport_capacity(w))
            if budget <= 0:
                continue
            
            road = self.road_conditions[w, :].astype(float)
            dist = self.distances[w, :].astype(float)
            demand_total = self.demand.sum(axis=1).astype(float)
            demand_norm = np.sqrt(demand_total + 1e-10)
            point_weight = urgency * np.clip(road, 0.0, None) / (dist + 1.0) / demand_norm
            
            if np.all(point_weight <= 0):
                point_weight = np.ones(self.num_points, dtype=float)
            
            point_weight = point_weight / (point_weight.sum() + 1e-10)
            point_quota = budget * point_weight
            
            for p in np.argsort(-urgency):
                if point_quota[p] <= 0:
                    continue
                
                demand_p = remaining_demand[p, :]
                if demand_p.sum() <= 0:
                    continue
                
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
        with np.errstate(divide='ignore', invalid='ignore'):
            satisfaction_rate = np.minimum(received / (self.demand + 1e-10), 1.0)
            satisfaction_rate = np.nan_to_num(satisfaction_rate, nan=0.0, posinf=1.0, neginf=0.0)
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
        
        fitness_value = 0.0
        weights = self.objective_weights
        
        # 物资满足率
        if weights.get('satisfaction', 0) > 0:
            _, overall_satisfaction = self.calculate_satisfaction_rate(individual)
            satisfaction_score = np.mean(overall_satisfaction)
            fitness_value += weights['satisfaction'] * satisfaction_score
        
        # 运输成本
        if weights.get('transport_cost', 0) > 0:
            cost_score = 1.0 / (1.0 + self.calculate_transport_cost(individual) / 10000.0)
            fitness_value += weights['transport_cost'] * cost_score
        
        # 公平性
        if weights.get('fairness', 0) > 0:
            fairness_score = self.calculate_fairness(individual)
            fitness_value += weights['fairness'] * fairness_score
        
        # 紧急程度
        if weights.get('urgency', 0) > 0:
            urgency_score = self.calculate_urgency_score(individual)
            fitness_value += weights['urgency'] * urgency_score
        
        # 时间效率
        if weights.get('time_efficiency', 0) > 0:
            time_score = self.calculate_time_efficiency(individual)
            fitness_value += weights['time_efficiency'] * time_score
        
        return fitness_value
    
    def repair(self, individual):
        """修复不可行解（库存、需求、车辆约束迭代收敛）"""
        repaired = individual.copy()
        for _ in range(5):
            repaired = self._enforce_inventory_limit(repaired)
            repaired = self._enforce_demand_limit(repaired)
            repaired = self._enforce_vehicle_limit(repaired)
        return repaired

    def optimize(self, pop_size=None, generations=None, mutation_rate=None):
        """遗传算法优化（增强版）"""
        algo_config = self.config.get('algorithm', {})
        pop_size = pop_size or algo_config.get('pop_size', 100)
        generations = generations or algo_config.get('generations', 50)
        mutation_rate = mutation_rate or algo_config.get('mutation_rate', 0.1)
        elite_ratio = algo_config.get('elite_ratio', 0.1)
        crossover_rate = algo_config.get('crossover_rate', 0.85)

        print(f"\n开始优化: 种群大小={pop_size}, 迭代次数={generations}, 变异率={mutation_rate}")

        best_solution, fitness_history = self.optimize_enhanced(
            pop_size=pop_size,
            generations=generations,
            mutation_rate=mutation_rate,
            elite_ratio=elite_ratio,
            crossover_rate=crossover_rate,
            tournament_size=3,
            local_search_steps=4,
            stagnation_patience=6,
        )

        print(f"\n优化完成! 最终适应度: {fitness_history[-1]:.4f}")
        return best_solution, fitness_history
    
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

def main():
    """主函数"""
    print("=" * 70)
    print("通用版物资分配优化系统")
    print("基于遗传算法的救援物资分配模型 (通用版)")
    print("=" * 70)
    
    # 创建数据加载器
    loader = DataLoader('config.json')
    
    # 加载数据
    data = loader.load()
    
    # 验证数据
    valid, errors = loader.validate_data(data)
    if not valid:
        print("\n数据验证失败:")
        for error in errors:
            print(f"  - {error}")
        print("\n请检查数据格式后重试")
        return
    
    print("\n数据验证通过!")
    
    # 从配置获取算法参数
    config = loader.get_config()
    
    # 创建模型
    model = UniversalAllocationModel(data, config)
    
    # 可选：自定义目标权重
    # model.set_objective_weights({
    #     'satisfaction': 0.4,
    #     'transport_cost': 0.1,
    #     'fairness': 0.2,
    #     'urgency': 0.2,
    #     'time_efficiency': 0.1
    # })
    
    # 生成初始方案
    print("\n生成初始方案...")
    initial_solution = model.generate_individual()
    initial_metrics = model.analyze_solution(initial_solution)
    
    print("\n初始方案指标:")
    print(f"  - 平均满足率: {initial_metrics['satisfaction_rate']:.2f}%")
    print(f"  - 公平性指数: {initial_metrics['fairness']:.4f}")
    print(f"  - 紧急程度得分: {initial_metrics['urgency_score']:.4f}")
    print(f"  - 时间效率: {initial_metrics['time_efficiency']:.4f}")
    print(f"  - 运输成本: {int(initial_metrics['transport_cost']):,}")
    
    # 运行优化
    print("\n运行遗传算法优化...")
    best_solution, fitness_history = model.optimize()
    optimized_metrics = model.analyze_solution(best_solution)
    
    print("\n优化后方案指标:")
    print(f"  - 平均满足率: {optimized_metrics['satisfaction_rate']:.2f}%")
    print(f"  - 公平性指数: {optimized_metrics['fairness']:.4f}")
    print(f"  - 紧急程度得分: {optimized_metrics['urgency_score']:.4f}")
    print(f"  - 时间效率: {optimized_metrics['time_efficiency']:.4f}")
    print(f"  - 运输成本: {int(optimized_metrics['transport_cost']):,}")
    
    # 对比分析
    print("\n" + "=" * 70)
    print("优化效果对比:")
    print("=" * 70)
    print(f"  - 满足率提升: {optimized_metrics['satisfaction_rate'] - initial_metrics['satisfaction_rate']:.2f}%")
    print(f"  - 公平性变化: {(optimized_metrics['fairness'] - initial_metrics['fairness']) / initial_metrics['fairness'] * 100:.2f}%")
    print(f"  - 运输成本变化: {(optimized_metrics['transport_cost'] - initial_metrics['transport_cost']) / initial_metrics['transport_cost'] * 100:.2f}%")
    
    print("\n" + "=" * 70)
    print("优化完成!")
    print("=" * 70)
    
    # 返回数据和模型供后续使用
    return data, model, initial_solution, best_solution, fitness_history

if __name__ == '__main__':
    result = main()
