"""
数据库模型定义
包含：灾情、救援力量、物资、避难场所、人口、交通、气象等
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import enum


class DisasterType(str, enum.Enum):
    flood = "flood"
    earthquake = "earthquake"
    forest_fire = "forest_fire"
    extreme_weather = "extreme_weather"


class WarningLevel(str, enum.Enum):
    blue = "blue"
    yellow = "yellow"
    orange = "orange"
    red = "red"


class ResponseLevel(str, enum.Enum):
    level_1 = "I"
    level_2 = "II"
    level_3 = "III"
    level_4 = "IV"


class DisasterEvent(Base):
    """灾情事件表"""
    __tablename__ = "disaster_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_name = Column(String(200), nullable=False, comment="事件名称")
    disaster_type = Column(Enum(DisasterType), nullable=False, comment="灾害类型")
    warning_level = Column(Enum(WarningLevel), nullable=False, comment="预警等级")
    response_level = Column(Enum(ResponseLevel), comment="响应等级")
    
    # 位置信息
    latitude = Column(Float, nullable=False, comment="纬度")
    longitude = Column(Float, nullable=False, comment="经度")
    affected_area = Column(Float, comment="受灾面积(平方公里)")
    
    # 灾情描述
    description = Column(Text, comment="灾情描述")
    affected_population = Column(Integer, comment="受灾人口")
    casualties = Column(Integer, default=0, comment="伤亡人数")
    
    # 时间
    start_time = Column(DateTime, server_default=func.now(), comment="开始时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class RescueTeam(Base):
    """救援队伍表"""
    __tablename__ = "rescue_teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String(200), nullable=False, comment="队伍名称")
    team_type = Column(String(50), nullable=False, comment="队伍类型：消防/医疗/无人机/车辆")
    
    # 位置信息
    latitude = Column(Float, nullable=False, comment="纬度")
    longitude = Column(Float, nullable=False, comment="经度")
    
    # 队伍信息
    member_count = Column(Integer, default=0, comment="人数")
    equipment = Column(JSON, comment="装备清单")
    status = Column(String(20), default="available", comment="状态：available/dispatched/returning")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReliefMaterial(Base):
    """应急物资表"""
    __tablename__ = "relief_materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_name = Column(String(100), nullable=False, comment="物资名称")
    material_type = Column(String(50), nullable=False, comment="物资类型")
    
    # 库存信息
    total_stock = Column(Integer, default=0, comment="总库存")
    allocated = Column(Integer, default=0, comment="已调拨")
    available = Column(Integer, default=0, comment="可用库存")
    
    # 单位
    unit = Column(String(20), default="个", comment="单位")
    
    # 存放位置
    warehouse_name = Column(String(200), comment="仓库名称")
    warehouse_latitude = Column(Float, comment="仓库纬度")
    warehouse_longitude = Column(Float, comment="仓库经度")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class MaterialAllocation(Base):
    """物资调拨记录表"""
    __tablename__ = "material_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("relief_materials.id"), comment="物资ID")
    disaster_event_id = Column(Integer, ForeignKey("disaster_events.id"), comment="灾情事件ID")
    
    quantity = Column(Integer, nullable=False, comment="调拨数量")
    status = Column(String(20), default="pending", comment="状态：pending/in_transit/delivered")
    
    # 调拨方案
    allocation_plan = Column(Text, comment="调拨方案说明")
    
    created_at = Column(DateTime, server_default=func.now())


class Shelter(Base):
    """避难场所表"""
    __tablename__ = "shelters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shelter_name = Column(String(200), nullable=False, comment="场所名称")
    
    # 位置信息
    latitude = Column(Float, nullable=False, comment="纬度")
    longitude = Column(Float, nullable=False, comment="经度")
    address = Column(String(500), comment="详细地址")
    
    # 容量信息
    max_capacity = Column(Integer, nullable=False, comment="最大容纳人数")
    current_occupancy = Column(Integer, default=0, comment="当前容纳人数")
    
    # 设施
    facilities = Column(JSON, comment="设施清单")
    status = Column(String(20), default="open", comment="状态：open/closed/full")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PopulationData(Base):
    """人口数据表"""
    __tablename__ = "population_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_name = Column(String(200), nullable=False, comment="区域名称")
    
    # 位置信息
    latitude = Column(Float, nullable=False, comment="纬度")
    longitude = Column(Float, nullable=False, comment="经度")
    
    # 人口信息
    total_population = Column(Integer, comment="总人口")
    affected_population = Column(Integer, comment="受灾人口")
    key_population = Column(JSON, comment="重点人群分布：老人/儿童/残疾人等")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RoadStatus(Base):
    """道路状态表"""
    __tablename__ = "road_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    road_name = Column(String(200), nullable=False, comment="道路名称")
    
    # 位置信息
    start_latitude = Column(Float, comment="起点纬度")
    start_longitude = Column(Float, comment="起点经度")
    end_latitude = Column(Float, comment="终点纬度")
    end_longitude = Column(Float, comment="终点经度")
    
    # 状态信息
    status = Column(String(20), default="normal", comment="状态：normal/congested/blocked")
    congestion_index = Column(Float, default=0, comment="拥堵指数 0-10")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WeatherData(Base):
    """气象数据表"""
    __tablename__ = "weather_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_name = Column(String(200), nullable=False, comment="区域名称")
    
    # 气象指标
    rainfall = Column(Float, comment="降雨量(mm)")
    wind_speed = Column(Float, comment="风速(m/s)")
    temperature = Column(Float, comment="气温(℃)")
    humidity = Column(Float, comment="湿度(%)")
    
    # 预警
    warning_level = Column(Enum(WarningLevel), comment="预警等级")
    warning_description = Column(Text, comment="预警描述")
    
    recorded_at = Column(DateTime, server_default=func.now(), comment="记录时间")


class AIDecision(Base):
    """AI决策记录表"""
    __tablename__ = "ai_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disaster_event_id = Column(Integer, ForeignKey("disaster_events.id"), comment="关联灾情事件ID")
    
    # 1. 自然语言灾情输入
    input_data = Column(Text, comment="自然语言灾情描述")
    
    # 2. AI信息抽取结果
    extracted_info = Column(JSON, comment="AI抽取的结构化信息")
    
    # 3. 风险评估结果
    risk_assessment = Column(JSON, comment="风险评估结果")
    
    # 4. 案例匹配(RAG)结果
    matched_cases = Column(JSON, comment="匹配的历史案例")
    
    # 5. 资源需求预测
    resource_prediction = Column(JSON, comment="资源需求预测结果")
    
    # 6. 处置方案
    response_plan = Column(Text, comment="生成的处置方案")
    
    # 7. 指挥命令
    command_orders = Column(JSON, comment="生成的指挥命令列表")
    
    # 完整AI响应（保留用于调试）
    full_response = Column(Text, comment="完整AI响应")
    
    # 状态
    status = Column(String(20), default="pending", comment="状态：pending/confirmed/rejected")
    
    created_at = Column(DateTime, server_default=func.now())


class TransferRecord(Base):
    """群众转移记录表"""
    __tablename__ = "transfer_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disaster_event_id = Column(Integer, ForeignKey("disaster_events.id"), comment="关联灾情事件ID")
    shelter_id = Column(Integer, ForeignKey("shelters.id"), comment="关联避难场所ID")
    
    transfer_count = Column(Integer, comment="转移人数")
    status = Column(String(20), default="planned", comment="状态：planned/in_progress/completed")
    
    plan_description = Column(Text, comment="转移方案描述")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
