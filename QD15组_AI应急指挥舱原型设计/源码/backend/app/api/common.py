import json
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.utils.cache import cache_get, cache_set, cache_clear_pattern
from typing import List


def to_int(value):
    """将值转换为int，处理Decimal等类型"""
    if value is None:
        return 0
    return int(value)


router = APIRouter(prefix="/api/common", tags=["公共数据"])


@router.get("/weather", response_model=List[schemas.WeatherDataResponse])
def get_weather_data(db: Session = Depends(get_db)):
    """获取气象数据"""
    return db.query(models.WeatherData).all()


@router.get("/roads", response_model=List[schemas.RoadStatusResponse])
def get_road_status(db: Session = Depends(get_db)):
    """获取道路状态"""
    return db.query(models.RoadStatus).all()


@router.get("/population", response_model=List[schemas.PopulationDataResponse])
def get_population_data(db: Session = Depends(get_db)):
    """获取人口数据"""
    return db.query(models.PopulationData).all()


@router.get("/dashboard")
def get_dashboard_data(db: Session = Depends(get_db)):
    """获取大屏仪表盘汇总数据 - 带Redis缓存"""
    try:
        # 尝试从Redis获取缓存
        cache_key = "dashboard:summary"
        cached = cache_get(cache_key)
        if cached:
            return json.loads(cached)
        
        # 灾情统计
        total_events = db.query(models.DisasterEvent).count()
        active_events = db.query(models.DisasterEvent).filter(
            models.DisasterEvent.response_level.in_([models.ResponseLevel.level_1, models.ResponseLevel.level_2])
        ).count()
        
        # 救援力量
        total_teams = db.query(models.RescueTeam).count()
        available_teams = db.query(models.RescueTeam).filter(
            models.RescueTeam.status == "available"
        ).count()
        
        # 物资
        total_materials = db.query(models.ReliefMaterial).all()
        total_stock = to_int(sum(m.total_stock for m in total_materials))
        total_available = to_int(sum(m.available for m in total_materials))
        
        # 避难场所
        total_shelters = db.query(models.Shelter).count()
        open_shelters = db.query(models.Shelter).filter(
            models.Shelter.status == "open"
        ).count()
        
        # 转移
        total_transferred = to_int(db.query(models.TransferRecord).with_entities(
            func.sum(models.TransferRecord.transfer_count)
        ).scalar())
        
        # 道路
        blocked_roads = db.query(models.RoadStatus).filter(
            models.RoadStatus.status == "blocked"
        ).count()
        
        result = {
            "disaster": {
                "total_events": total_events,
                "active_events": active_events
            },
            "rescue": {
                "total_teams": total_teams,
                "available_teams": available_teams
            },
            "materials": {
                "total_stock": total_stock,
                "total_available": total_available
            },
            "shelters": {
                "total": total_shelters,
                "open": open_shelters
            },
            "evacuation": {
                "total_transferred": total_transferred
            },
            "roads": {
                "blocked": blocked_roads
            }
        }
        
        # 缓存到Redis
        cache_set(cache_key, json.dumps(result))
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise
