"""Pydantic Schemas for API request/response validation"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.models import DisasterType, WarningLevel, ResponseLevel


# ========== 灾情事件 ==========
class DisasterEventBase(BaseModel):
    event_name: str
    disaster_type: DisasterType
    warning_level: WarningLevel
    response_level: Optional[ResponseLevel] = None
    latitude: float
    longitude: float
    affected_area: Optional[float] = None
    description: Optional[str] = None
    affected_population: Optional[int] = None
    casualties: int = 0


class DisasterEventCreate(DisasterEventBase):
    pass


class DisasterEventResponse(DisasterEventBase):
    id: int
    start_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 救援队伍 ==========
class RescueTeamBase(BaseModel):
    team_name: str
    team_type: str
    latitude: float
    longitude: float
    member_count: int = 0
    equipment: Optional[dict] = None
    status: str = "available"


class RescueTeamCreate(RescueTeamBase):
    pass


class RescueTeamResponse(RescueTeamBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 应急物资 ==========
class ReliefMaterialBase(BaseModel):
    material_name: str
    material_type: str
    total_stock: int = 0
    allocated: int = 0
    available: int = 0
    unit: str = "个"
    warehouse_name: Optional[str] = None
    warehouse_latitude: Optional[float] = None
    warehouse_longitude: Optional[float] = None


class ReliefMaterialCreate(ReliefMaterialBase):
    pass


class ReliefMaterialResponse(ReliefMaterialBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 物资调拨 ==========
class MaterialAllocationCreate(BaseModel):
    material_id: int
    disaster_event_id: int
    quantity: int
    allocation_plan: Optional[str] = None


class MaterialAllocationResponse(BaseModel):
    id: int
    material_id: int
    disaster_event_id: int
    quantity: int
    status: str
    allocation_plan: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 避难场所 ==========
class ShelterBase(BaseModel):
    shelter_name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    max_capacity: int
    current_occupancy: int = 0
    facilities: Optional[dict] = None
    status: str = "open"


class ShelterCreate(ShelterBase):
    pass


class ShelterResponse(ShelterBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 人口数据 ==========
class PopulationDataBase(BaseModel):
    region_name: str
    latitude: float
    longitude: float
    total_population: Optional[int] = None
    affected_population: Optional[int] = None
    key_population: Optional[dict] = None


class PopulationDataResponse(PopulationDataBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 道路状态 ==========
class RoadStatusBase(BaseModel):
    road_name: str
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    status: str = "normal"
    congestion_index: float = 0


class RoadStatusResponse(RoadStatusBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 气象数据 ==========
class WeatherDataResponse(BaseModel):
    id: int
    region_name: str
    rainfall: Optional[float] = None
    wind_speed: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    warning_level: Optional[WarningLevel] = None
    warning_description: Optional[str] = None
    recorded_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== AI决策 ==========
class AIDecisionRequest(BaseModel):
    disaster_event_id: Optional[int] = None
    natural_language_input: str = Field(..., description="自然语言灾情描述")


class AIDecisionResponse(BaseModel):
    id: int
    disaster_event_id: Optional[int] = None
    input_data: Optional[str] = None
    extracted_info: Optional[dict] = None
    risk_assessment: Optional[dict] = None
    matched_cases: Optional[list] = None
    resource_prediction: Optional[dict] = None
    response_plan: Optional[str] = None
    command_orders: Optional[list] = None
    full_response: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 群众转移 ==========
class TransferRecordCreate(BaseModel):
    disaster_event_id: int
    shelter_id: int
    transfer_count: int
    plan_description: Optional[str] = None


class TransferRecordResponse(BaseModel):
    id: int
    disaster_event_id: int
    shelter_id: int
    transfer_count: int
    status: str
    plan_description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 通用响应 ==========
class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[dict] = None
