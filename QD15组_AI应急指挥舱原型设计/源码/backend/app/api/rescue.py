from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app.models import models
from app.schemas import schemas
import math

router = APIRouter(prefix="/api/rescue", tags=["救援力量"])


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两点间距离(km) - Haversine公式"""
    R = 6371  # 地球半径(km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


@router.get("/teams", response_model=List[schemas.RescueTeamResponse])
def get_rescue_teams(team_type: str = None, status: str = None, db: Session = Depends(get_db)):
    """获取救援队伍列表"""
    query = db.query(models.RescueTeam)
    if team_type:
        query = query.filter(models.RescueTeam.team_type == team_type)
    if status:
        query = query.filter(models.RescueTeam.status == status)
    return query.all()


@router.post("/teams", response_model=schemas.RescueTeamResponse)
def create_rescue_team(team: schemas.RescueTeamCreate, db: Session = Depends(get_db)):
    """创建救援队伍"""
    db_team = models.RescueTeam(**team.model_dump())
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team


@router.get("/nearest")
def get_nearest_rescue_teams(
    latitude: float,
    longitude: float,
    team_type: str = None,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """获取最近的救援队伍"""
    teams = db.query(models.RescueTeam).filter(
        models.RescueTeam.status == "available"
    ).all()
    
    if team_type:
        teams = [t for t in teams if t.team_type == team_type]
    
    # 计算距离
    teams_with_distance = []
    for team in teams:
        distance = calculate_distance(latitude, longitude, team.latitude, team.longitude)
        # 估算到达时间(假设平均速度60km/h)
        eta_hours = distance / 60
        teams_with_distance.append({
            **schemas.RescueTeamResponse.model_validate(team).model_dump(),
            "distance_km": round(distance, 2),
            "eta_hours": round(eta_hours, 2)
        })
    
    # 按距离排序
    teams_with_distance.sort(key=lambda x: x["distance_km"])
    return teams_with_distance[:limit]


@router.get("/statistics")
def get_rescue_statistics(db: Session = Depends(get_db)):
    """获取救援力量统计"""
    total_teams = db.query(models.RescueTeam).count()
    available_teams = db.query(models.RescueTeam).filter(
        models.RescueTeam.status == "available"
    ).count()
    total_members = db.query(models.RescueTeam).with_entities(
        func.sum(models.RescueTeam.member_count)
    ).scalar() or 0
    
    by_type = {}
    for team_type in ["消防", "医疗", "无人机", "车辆"]:
        count = db.query(models.RescueTeam).filter(
            models.RescueTeam.team_type == team_type
        ).count()
        by_type[team_type] = count
    
    return {
        "total_teams": total_teams,
        "available_teams": available_teams,
        "total_members": total_members,
        "by_type": by_type
    }
