"""模拟数据生成脚本"""
import random
from datetime import datetime, timedelta
from sqlalchemy import text
from app.database import SessionLocal, engine, Base
from app.models import models

# 创建所有表
Base.metadata.create_all(bind=engine)


def generate_mock_data():
    """生成模拟数据"""
    db = SessionLocal()
    
    try:
        # 禁用外键检查（MySQL）
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        db.commit()
        
        # 清空现有数据
        for table in [
            models.DisasterEvent, models.RescueTeam, models.ReliefMaterial,
            models.MaterialAllocation, models.Shelter, models.PopulationData,
            models.RoadStatus, models.WeatherData, models.AIDecision, models.TransferRecord
        ]:
            db.query(table).delete()
        
        # 重置自增ID
        for table_name in [
            "disaster_events", "rescue_teams", "relief_materials",
            "material_allocations", "shelters", "population_data",
            "road_status", "weather_data", "ai_decisions", "transfer_records"
        ]:
            db.execute(text(f"ALTER TABLE {table_name} AUTO_INCREMENT = 1"))
        db.commit()
        
        # ========== 灾情事件 ==========
        disasters = [
            {
                "event_name": "城南洪涝灾害",
                "disaster_type": models.DisasterType.flood,
                "warning_level": models.WarningLevel.red,
                "response_level": models.ResponseLevel.level_2,
                "latitude": 30.5728,
                "longitude": 104.0668,
                "affected_area": 150.5,
                "description": "持续暴雨导致城南区域严重内涝，多处道路积水",
                "affected_population": 12000,
                "casualties": 3
            },
            {
                "event_name": "北部山区滑坡",
                "disaster_type": models.DisasterType.extreme_weather,
                "warning_level": models.WarningLevel.orange,
                "response_level": models.ResponseLevel.level_3,
                "latitude": 30.7228,
                "longitude": 104.1168,
                "affected_area": 45.2,
                "description": "强降雨引发北部山区多处滑坡",
                "affected_population": 3500,
                "casualties": 1
            },
            {
                "event_name": "东部森林火情",
                "disaster_type": models.DisasterType.forest_fire,
                "warning_level": models.WarningLevel.yellow,
                "response_level": models.ResponseLevel.level_4,
                "latitude": 30.5228,
                "longitude": 104.2168,
                "affected_area": 80.0,
                "description": "东部林区发现火情，正在蔓延",
                "affected_population": 800,
                "casualties": 0
            }
        ]
        
        for d in disasters:
            db.add(models.DisasterEvent(**d))
        
        # ========== 救援队伍 ==========
        rescue_teams = [
            {"team_name": "城南消防中队", "team_type": "消防", "latitude": 30.5628, "longitude": 104.0568, "member_count": 45, "equipment": {"消防车": 5, "救生艇": 3, "抽水机": 10}, "status": "available"},
            {"team_name": "城北消防大队", "team_type": "消防", "latitude": 30.6028, "longitude": 104.0768, "member_count": 60, "equipment": {"消防车": 8, "云梯车": 2, "救生艇": 5}, "status": "available"},
            {"team_name": "市急救中心", "team_type": "医疗", "latitude": 30.5828, "longitude": 104.0868, "member_count": 30, "equipment": {"救护车": 10, "急救箱": 50}, "status": "available"},
            {"team_name": "人民医院救援队", "team_type": "医疗", "latitude": 30.5528, "longitude": 104.0468, "member_count": 25, "equipment": {"救护车": 5, "急救箱": 30}, "status": "dispatched"},
            {"team_name": "无人机侦察队", "team_type": "无人机", "latitude": 30.5728, "longitude": 104.0768, "member_count": 8, "equipment": {"无人机": 12, "红外相机": 6}, "status": "available"},
            {"team_name": "应急救援车队", "team_type": "车辆", "latitude": 30.5928, "longitude": 104.0568, "member_count": 20, "equipment": {"运输车": 15, "指挥车": 2}, "status": "available"},
            {"team_name": "武警救援支队", "team_type": "消防", "latitude": 30.5428, "longitude": 104.0968, "member_count": 100, "equipment": {"冲锋舟": 8, "救生衣": 200, "抽水机": 15}, "status": "available"},
            {"team_name": "第二医院救援队", "team_type": "医疗", "latitude": 30.6128, "longitude": 104.0368, "member_count": 20, "equipment": {"救护车": 4, "急救箱": 20}, "status": "available"},
        ]
        
        for team in rescue_teams:
            db.add(models.RescueTeam(**team))
        
        # ========== 应急物资 ==========
        materials = [
            {"material_name": "饮用水", "material_type": "生活物资", "total_stock": 100000, "allocated": 15000, "available": 85000, "unit": "瓶", "warehouse_name": "市应急物资仓库", "warehouse_latitude": 30.5828, "warehouse_longitude": 104.0668},
            {"material_name": "方便面", "material_type": "生活物资", "total_stock": 50000, "allocated": 8000, "available": 42000, "unit": "箱", "warehouse_name": "市应急物资仓库", "warehouse_latitude": 30.5828, "warehouse_longitude": 104.0668},
            {"material_name": "急救药品", "material_type": "医疗物资", "total_stock": 5000, "allocated": 500, "available": 4500, "unit": "份", "warehouse_name": "医疗物资储备库", "warehouse_latitude": 30.5728, "warehouse_longitude": 104.0868},
            {"material_name": "帐篷", "material_type": "安置物资", "total_stock": 2000, "allocated": 300, "available": 1700, "unit": "顶", "warehouse_name": "市应急物资仓库", "warehouse_latitude": 30.5828, "warehouse_longitude": 104.0668},
            {"material_name": "发电机", "material_type": "设备物资", "total_stock": 200, "allocated": 30, "available": 170, "unit": "台", "warehouse_name": "设备物资储备库", "warehouse_latitude": 30.5928, "warehouse_longitude": 104.0568},
            {"material_name": "救生衣", "material_type": "救援物资", "total_stock": 10000, "allocated": 2000, "available": 8000, "unit": "件", "warehouse_name": "市应急物资仓库", "warehouse_latitude": 30.5828, "warehouse_longitude": 104.0668},
            {"material_name": "沙袋", "material_type": "防汛物资", "total_stock": 50000, "allocated": 10000, "available": 40000, "unit": "个", "warehouse_name": "防汛物资储备库", "warehouse_latitude": 30.5628, "warehouse_longitude": 104.0768},
        ]
        
        for m in materials:
            db.add(models.ReliefMaterial(**m))
        
        # ========== 避难场所 ==========
        shelters = [
            {"shelter_name": "市体育中心", "latitude": 30.5828, "longitude": 104.0468, "address": "城南体育路1号", "max_capacity": 5000, "current_occupancy": 1200, "facilities": {"床位": 5000, "卫生间": 20, "医疗点": 2}, "status": "open"},
            {"shelter_name": "第一中学", "latitude": 30.5928, "longitude": 104.0768, "address": "城中教育路10号", "max_capacity": 3000, "current_occupancy": 800, "facilities": {"床位": 3000, "卫生间": 15, "医疗点": 1}, "status": "open"},
            {"shelter_name": "国际会展中心", "latitude": 30.5628, "longitude": 104.0968, "address": "城东会展大道88号", "max_capacity": 8000, "current_occupancy": 2500, "facilities": {"床位": 8000, "卫生间": 30, "医疗点": 3}, "status": "open"},
            {"shelter_name": "社区活动中心", "latitude": 30.6028, "longitude": 104.0368, "address": "城北社区路5号", "max_capacity": 1500, "current_occupancy": 1500, "facilities": {"床位": 1500, "卫生间": 8, "医疗点": 1}, "status": "full"},
            {"shelter_name": "工人文化宫", "latitude": 30.5428, "longitude": 104.0668, "address": "城南工人路20号", "max_capacity": 2000, "current_occupancy": 500, "facilities": {"床位": 2000, "卫生间": 10, "医疗点": 1}, "status": "open"},
        ]
        
        for s in shelters:
            db.add(models.Shelter(**s))
        
        # ========== 人口数据 ==========
        population_data = [
            {"region_name": "城南片区", "latitude": 30.5728, "longitude": 104.0668, "total_population": 50000, "affected_population": 12000, "key_population": {"老人": 2500, "儿童": 1800, "残疾人": 300}},
            {"region_name": "城北片区", "latitude": 30.6028, "longitude": 104.0768, "total_population": 35000, "affected_population": 3500, "key_population": {"老人": 1200, "儿童": 800, "残疾人": 150}},
            {"region_name": "城东片区", "latitude": 30.5628, "longitude": 104.0968, "total_population": 40000, "affected_population": 800, "key_population": {"老人": 800, "儿童": 500, "残疾人": 100}},
            {"region_name": "城西片区", "latitude": 30.5828, "longitude": 104.0368, "total_population": 30000, "affected_population": 0, "key_population": {"老人": 600, "儿童": 400, "残疾人": 80}},
        ]
        
        for p in population_data:
            db.add(models.PopulationData(**p))
        
        # ========== 道路状态 ==========
        roads = [
            {"road_name": "城南大道", "start_latitude": 30.5628, "start_longitude": 104.0568, "end_latitude": 30.5828, "end_longitude": 104.0768, "status": "blocked", "congestion_index": 10},
            {"road_name": "人民路", "start_latitude": 30.5728, "start_longitude": 104.0468, "end_latitude": 30.5928, "end_longitude": 104.0668, "status": "congested", "congestion_index": 8},
            {"road_name": "建设路", "start_latitude": 30.5528, "start_longitude": 104.0668, "end_latitude": 30.5728, "end_longitude": 104.0868, "status": "blocked", "congestion_index": 10},
            {"road_name": "环城高速", "start_latitude": 30.5428, "start_longitude": 104.0368, "end_latitude": 30.6028, "end_longitude": 104.0968, "status": "normal", "congestion_index": 3},
            {"road_name": "东风路", "start_latitude": 30.5828, "start_longitude": 104.0568, "end_latitude": 30.5628, "end_longitude": 104.0768, "status": "congested", "congestion_index": 7},
            {"road_name": "解放路", "start_latitude": 30.5928, "start_longitude": 104.0468, "end_latitude": 30.5728, "end_longitude": 104.0668, "status": "normal", "congestion_index": 4},
            {"road_name": "中山路", "start_latitude": 30.5528, "start_longitude": 104.0768, "end_latitude": 30.5828, "end_longitude": 104.0968, "status": "blocked", "congestion_index": 10},
            {"road_name": "迎宾大道", "start_latitude": 30.6028, "start_longitude": 104.0668, "end_latitude": 30.5828, "end_longitude": 104.0868, "status": "normal", "congestion_index": 2},
        ]
        
        for r in roads:
            db.add(models.RoadStatus(**r))
        
        # ========== 气象数据 ==========
        now = datetime.now()
        weather_data = [
            {"region_name": "城南", "rainfall": 150.5, "wind_speed": 12.5, "temperature": 25.3, "humidity": 95, "warning_level": models.WarningLevel.red, "warning_description": "暴雨红色预警：预计未来3小时降雨量将达100毫米以上", "recorded_at": now},
            {"region_name": "城北", "rainfall": 85.2, "wind_speed": 8.3, "temperature": 24.1, "humidity": 88, "warning_level": models.WarningLevel.orange, "warning_description": "暴雨橙色预警：预计未来3小时降雨量将达50毫米以上", "recorded_at": now},
            {"region_name": "城东", "rainfall": 45.0, "wind_speed": 6.2, "temperature": 26.5, "humidity": 80, "warning_level": models.WarningLevel.yellow, "warning_description": "暴雨黄色预警：预计未来6小时降雨量将达30毫米以上", "recorded_at": now},
            {"region_name": "城西", "rainfall": 20.0, "wind_speed": 4.5, "temperature": 27.0, "humidity": 70, "warning_level": models.WarningLevel.blue, "warning_description": "暴雨蓝色预警：预计未来12小时降雨量将达15毫米以上", "recorded_at": now},
        ]
        
        for w in weather_data:
            db.add(models.WeatherData(**w))
        
        # ========== 物资调拨记录 ==========
        allocations = [
            {"material_id": 1, "disaster_event_id": 1, "quantity": 15000, "status": "delivered", "allocation_plan": "紧急调拨饮用水至城南灾区"},
            {"material_id": 2, "disaster_event_id": 1, "quantity": 5000, "status": "in_transit", "allocation_plan": "调拨方便面至城南灾区"},
            {"material_id": 4, "disaster_event_id": 1, "quantity": 200, "status": "delivered", "allocation_plan": "调拨帐篷至城南灾区安置点"},
            {"material_id": 3, "disaster_event_id": 2, "quantity": 300, "status": "in_transit", "allocation_plan": "调拨急救药品至北部山区"},
        ]
        
        for a in allocations:
            db.add(models.MaterialAllocation(**a))
        
        # ========== 转移记录 ==========
        transfers = [
            {"disaster_event_id": 1, "shelter_id": 1, "transfer_count": 1200, "status": "completed", "plan_description": "城南片区第一批转移至市体育中心"},
            {"disaster_event_id": 1, "shelter_id": 3, "transfer_count": 2500, "status": "completed", "plan_description": "城南片区第二批转移至国际会展中心"},
            {"disaster_event_id": 1, "shelter_id": 5, "transfer_count": 500, "status": "in_progress", "plan_description": "城南片区第三批转移至工人文化宫"},
            {"disaster_event_id": 2, "shelter_id": 2, "transfer_count": 800, "status": "completed", "plan_description": "北部山区群众转移至第一中学"},
        ]
        
        for t in transfers:
            db.add(models.TransferRecord(**t))
        
        db.commit()
        
        # 恢复外键检查
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        db.commit()
        
        print("模拟数据生成成功！")
        
    except Exception as e:
        db.rollback()
        print(f"生成模拟数据失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    generate_mock_data()
