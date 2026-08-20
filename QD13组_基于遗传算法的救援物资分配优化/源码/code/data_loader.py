# ==============================================================================
# 数据加载器 - 支持多种数据格式和自定义数据
# ==============================================================================

import numpy as np
import json
import os

class DataLoader:
    """通用数据加载器，支持从多种数据源加载数据"""
    
    def __init__(self, config_file='config.json'):
        """
        初始化数据加载器
        
        参数:
            config_file: 配置文件路径
        """
        self.config = self._load_config(config_file)
        
    def _load_config(self, config_file):
        """加载配置文件"""
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"配置文件 {config_file} 不存在，使用默认配置")
            return self._get_default_config()
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            'data': {
                'disaster_points_file': None,
                'use_simulation': True
            },
            'algorithm': {
                'pop_size': 100,
                'generations': 50,
                'mutation_rate': 0.1,
                'crossover_rate': 0.8,
                'elite_ratio': 0.1
            },
            'objectives': {
                'satisfaction': {'weight': 0.35, 'enabled': True},
                'transport_cost': {'weight': 0.15, 'enabled': True},
                'fairness': {'weight': 0.2, 'enabled': True},
                'urgency': {'weight': 0.2, 'enabled': True},
                'time_efficiency': {'weight': 0.1, 'enabled': True}
            }
        }
    
    def load(self):
        """
        加载数据
        返回: 包含所有数据的字典
        """
        if self.config['data']['use_simulation']:
            return self._load_simulation_data()
        else:
            return self._load_custom_data()
    
    def _load_simulation_data(self):
        """加载模拟数据"""
        print("加载模拟数据...")
        
        # 模拟受灾点数据：6个受灾点，8个字段
        disaster_points = np.array([
            [1, 113.65, 34.76, 1150100, 2300200, 575050, 23002, 4],
            [2, 112.98, 34.76, 63000, 126000, 31500, 1260, 3],
            [3, 113.42, 34.51, 293500, 587000, 146750, 5870, 3],
            [4, 113.72, 34.38, 80000, 160000, 40000, 1600, 2],
            [5, 113.38, 34.79, 210300, 420600, 105150, 4206, 3],
            [6, 113.03, 34.45, 151000, 302000, 75500, 3020, 2]
        ])
        
        # 模拟仓库数据：3个仓库，8个字段
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
        
        # 道路状况矩阵
        road_conditions = np.array([
            [1.0, 0.8, 0.9, 0.95, 0.85, 0.7],
            [0.7, 0.9, 0.75, 0.6, 0.8, 0.85],
            [0.85, 0.65, 0.7, 0.8, 0.6, 0.55]
        ])
        
        # 运输时间矩阵
        transport_time = np.array([
            [0.5, 1.5, 1.0, 1.0, 0.8, 1.5],
            [3.0, 2.0, 2.5, 4.0, 2.5, 2.5],
            [2.0, 3.5, 3.0, 1.5, 3.0, 3.5]
        ])
        
        # 需求矩阵（自动从受灾点数据提取）
        demand = disaster_points[:, 4:7]
        
        # 库存矩阵（自动从仓库数据提取）
        inventory = warehouses[:, 3:6]
        
        # 权重设置
        urgency_weights = np.array([0.4, 0.25, 0.2, 0.05, 0.07, 0.03])
        material_weights = np.array([0.5, 0.35, 0.15])
        
        # 目标权重
        objective_weights = {
            'satisfaction': 0.35,
            'transport_cost': 0.15,
            'fairness': 0.2,
            'urgency': 0.2,
            'time_efficiency': 0.1
        }
        
        # 元数据
        disaster_points_info = {
            1: {'name': '郑州', 'population': 1150100, 'casualties': 112132, 'urgency': 21.6},
            2: {'name': '巩义', 'population': 63000, 'casualties': 84203, 'urgency': 2.02},
            3: {'name': '新密', 'population': 293500, 'casualties': 58265, 'urgency': 3.36},
            4: {'name': '新郑', 'population': 80000, 'casualties': 17865, 'urgency': 1.0},
            5: {'name': '荥阳', 'population': 210300, 'casualties': 96742, 'urgency': 2.86},
            6: {'name': '登封', 'population': 151000, 'casualties': 13856, 'urgency': 1.28}
        }
        
        warehouses_info = {
            '仓库1': {'location': (113.62, 34.75), 'inventory': [49903, 128546, 19102]},
            '仓库2': {'location': (112.45, 34.62), 'inventory': [35645, 91818, 13644]},
            '仓库3': {'location': (114.35, 34.78), 'inventory': [28516, 73455, 10915]}
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
    
    def _load_custom_data(self):
        """从文件加载自定义数据"""
        data_file = self.config['data']['disaster_points_file']
        
        if not data_file or not os.path.exists(data_file):
            print(f"数据文件 {data_file} 不存在，使用模拟数据")
            return self._load_simulation_data()
        
        try:
            # 动态导入数据模块
            import importlib.util
            spec = importlib.util.spec_from_file_location("data_module", data_file)
            data_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(data_module)
            
            # 提取数据
            data = {
                'disaster_points': data_module.disaster_points,
                'warehouses': data_module.warehouses,
                'distance_matrix': data_module.distance_matrix,
                'road_conditions': data_module.road_conditions,
                'transport_time': data_module.transport_time,
                'demand': getattr(data_module, 'demand', None),
                'inventory': getattr(data_module, 'inventory', None),
                'urgency_weights': getattr(data_module, 'urgency_weights', None),
                'material_weights': getattr(data_module, 'material_weights', None),
                'objective_weights': getattr(data_module, 'objective_weights', None),
                'disaster_points_info': getattr(data_module, 'disaster_points_info', {}),
                'warehouses_info': getattr(data_module, 'warehouses_info', {}),
                'metadata': getattr(data_module, 'metadata', {}),
                'material_names': getattr(data_module, 'material_names', None),
            }
            
            # 自动计算需求和库存
            if data['demand'] is None:
                data['demand'] = data['disaster_points'][:, 4:7]
            if data['inventory'] is None:
                data['inventory'] = data['warehouses'][:, 3:6]
            if data['urgency_weights'] is None:
                data['urgency_weights'] = self._calculate_urgency_weights(data['disaster_points'])
            if data['material_weights'] is None:
                data['material_weights'] = np.ones(data['demand'].shape[1]) / data['demand'].shape[1]
            if data['objective_weights'] is None:
                data['objective_weights'] = {
                    'satisfaction': 0.35,
                    'transport_cost': 0.15,
                    'fairness': 0.2,
                    'urgency': 0.2,
                    'time_efficiency': 0.1
                }
            
            print(f"成功加载自定义数据: {data_file}")
            return data
            
        except Exception as e:
            print(f"加载数据失败: {e}，使用模拟数据")
            return self._load_simulation_data()
    
    def _calculate_urgency_weights(self, disaster_points):
        """根据受灾点数据自动计算紧急程度权重"""
        # 使用紧急系数列（索引7）计算权重
        urgency = disaster_points[:, 7]
        if np.sum(urgency) > 0:
            return urgency / np.sum(urgency)
        else:
            return np.ones(len(urgency)) / len(urgency)
    
    def validate_data(self, data):
        """验证数据格式"""
        required_keys = [
            'disaster_points', 'warehouses', 'distance_matrix',
            'road_conditions', 'transport_time', 'demand', 'inventory'
        ]
        
        errors = []
        
        # 检查必需字段
        for key in required_keys:
            if key not in data:
                errors.append(f"缺少必需字段: {key}")
        
        if errors:
            return False, errors
        
        # 验证维度一致性
        try:
            num_warehouses = data['warehouses'].shape[0]
            num_points = data['disaster_points'].shape[0]
            num_materials = data['demand'].shape[1]
            
            # 距离矩阵维度
            if data['distance_matrix'].shape != (num_warehouses, num_points):
                errors.append(f"距离矩阵维度错误: 期望 ({num_warehouses}, {num_points})")
            
            # 道路状况矩阵维度
            if data['road_conditions'].shape != (num_warehouses, num_points):
                errors.append(f"道路状况矩阵维度错误: 期望 ({num_warehouses}, {num_points})")
            
            # 运输时间矩阵维度
            if data['transport_time'].shape != (num_warehouses, num_points):
                errors.append(f"运输时间矩阵维度错误: 期望 ({num_warehouses}, {num_points})")
            
            # 需求矩阵维度
            if data['demand'].shape != (num_points, num_materials):
                errors.append(f"需求矩阵维度错误: 期望 ({num_points}, {num_materials})")
            
            # 库存矩阵维度
            if data['inventory'].shape != (num_warehouses, num_materials):
                errors.append(f"库存矩阵维度错误: 期望 ({num_warehouses}, {num_materials})")
            
        except Exception as e:
            errors.append(f"维度验证失败: {str(e)}")
        
        return len(errors) == 0, errors
    
    def get_config(self):
        """获取当前配置"""
        return self.config
    
    def update_config(self, key_path, value):
        """
        更新配置项
        
        参数:
            key_path: 配置路径，如 'algorithm.pop_size'
            value: 新值
        """
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def save_config(self, filename='config_updated.json'):
        """保存配置到文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        print(f"配置已保存到: {filename}")

def create_sample_data(num_points=6, num_warehouses=3, num_materials=3):
    """
    创建示例数据（用于测试通用性）
    
    参数:
        num_points: 受灾点数量
        num_warehouses: 仓库数量
        num_materials: 物资类型数量
    
    返回:
        data: 数据字典
    """
    # 随机生成受灾点数据
    disaster_points = np.random.randint(50, 200, size=(num_points, 8))
    disaster_points[:, 0] = np.arange(1, num_points + 1)  # ID
    disaster_points[:, 1] = np.random.uniform(112, 115, num_points)  # 经度
    disaster_points[:, 2] = np.random.uniform(34, 35, num_points)  # 纬度
    disaster_points[:, 7] = np.random.randint(1, 5, num_points)  # 紧急系数
    
    # 随机生成仓库数据
    warehouses = np.random.randint(1000, 50000, size=(num_warehouses, 8))
    warehouses[:, 0] = np.arange(1, num_warehouses + 1)  # ID
    warehouses[:, 1] = np.random.uniform(112, 115, num_warehouses)  # 经度
    warehouses[:, 2] = np.random.uniform(34, 35, num_warehouses)  # 纬度
    warehouses[:, 6] = np.random.randint(10, 50, num_warehouses)  # 车辆数量
    warehouses[:, 7] = 100  # 车辆容量
    
    # 随机生成矩阵数据
    distance_matrix = np.random.randint(10, 200, size=(num_warehouses, num_points))
    road_conditions = np.random.uniform(0.5, 1.0, size=(num_warehouses, num_points))
    transport_time = np.random.uniform(0.5, 5.0, size=(num_warehouses, num_points))
    demand = disaster_points[:, 4:7] if num_materials == 3 else np.random.randint(1000, 50000, size=(num_points, num_materials))
    inventory = warehouses[:, 3:6] if num_materials == 3 else np.random.randint(5000, 20000, size=(num_warehouses, num_materials))
    
    # 权重设置
    urgency_weights = np.random.rand(num_points)
    urgency_weights /= urgency_weights.sum()
    material_weights = np.ones(num_materials) / num_materials
    objective_weights = {
        'satisfaction': 0.35,
        'transport_cost': 0.15,
        'fairness': 0.2,
        'urgency': 0.2,
        'time_efficiency': 0.1
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
        'disaster_points_info': {i+1: {'name': f'地点{i+1}'} for i in range(num_points)},
        'warehouses_info': {f'仓库{i+1}': {'location': tuple(warehouses[i, 1:3])} for i in range(num_warehouses)}
    }
