from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/api/evacuation", tags=["群众转移"])


@router.get("/shelters", response_model=List[schemas.ShelterResponse])
def get_shelters(db: Session = Depends(get_db)):
    """获取避难场所列表"""
    return db.query(models.Shelter).all()


@router.post("/shelters", response_model=schemas.ShelterResponse)
def create_shelter(shelter: schemas.ShelterCreate, db: Session = Depends(get_db)):
    """创建避难场所"""
    db_shelter = models.Shelter(**shelter.model_dump())
    db.add(db_shelter)
    db.commit()
    db.refresh(db_shelter)
    return db_shelter


@router.get("/transfers", response_model=List[schemas.TransferRecordResponse])
def get_transfer_records(db: Session = Depends(get_db)):
    """获取转移记录"""
    return db.query(models.TransferRecord).all()


@router.post("/transfers", response_model=schemas.TransferRecordResponse)
def create_transfer_record(record: schemas.TransferRecordCreate, db: Session = Depends(get_db)):
    """创建转移记录"""
    shelter = db.query(models.Shelter).filter(models.Shelter.id == record.shelter_id).first()
    if not shelter:
        raise HTTPException(status_code=404, detail="避难场所不存在")
    
    # 更新避难场所容纳人数
    shelter.current_occupancy += record.transfer_count
    if shelter.current_occupancy >= shelter.max_capacity:
        shelter.status = "full"
    
    db_record = models.TransferRecord(**record.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


@router.get("/plan")
def generate_evacuation_plan(
    affected_population: int,
    latitude: float,
    longitude: float,
    db: Session = Depends(get_db)
):
    """生成群众转移方案"""
    shelters = db.query(models.Shelter).filter(
        models.Shelter.status != "closed"
    ).all()

    # 计算可用容量
    available_shelters = []
    for shelter in shelters:
        available_capacity = shelter.max_capacity - shelter.current_occupancy
        if available_capacity > 0:
            available_shelters.append({
                **schemas.ShelterResponse.model_validate(shelter).model_dump(),
                "available_capacity": available_capacity
            })

    # 真实公开数据通常只有候选公共设施点位，没有逐点容量。
    # 这种情况下仍返回就近候选点，避免“生成方案”出现空结果。
    if not available_shelters:
        candidate_plan = []
        for shelter in shelters[:8]:
            candidate_plan.append({
                "shelter_id": shelter.id,
                "shelter_name": shelter.shelter_name,
                "transfer_count": 0,
                "available_capacity": 0,
                "suggestion": "候选公共设施，需现场核验容量后启用"
            })

        return {
            "affected_population": affected_population,
            "total_capacity": 0,
            "remaining_unassigned": affected_population,
            "capacity_status": "公开数据未提供逐点容量，已返回候选安置点",
            "plan": candidate_plan
        }

    # 按可用容量排序
    available_shelters.sort(key=lambda x: x["available_capacity"], reverse=True)
    
    # 分配转移方案
    remaining = affected_population
    plan = []
    for shelter in available_shelters:
        if remaining <= 0:
            break
        transfer_count = min(remaining, shelter["available_capacity"])
        plan.append({
            "shelter_id": shelter["id"],
            "shelter_name": shelter["shelter_name"],
            "transfer_count": transfer_count,
            "available_capacity": shelter["available_capacity"]
        })
        remaining -= transfer_count
    
    return {
        "affected_population": affected_population,
        "total_capacity": sum(s["available_capacity"] for s in available_shelters),
        "remaining_unassigned": remaining,
        "plan": plan
    }


@router.get("/statistics")
def get_evacuation_statistics(db: Session = Depends(get_db)):
    """获取转移统计"""
    total_transferred = db.query(models.TransferRecord).with_entities(
        func.sum(models.TransferRecord.transfer_count)
    ).scalar() or 0
    
    total_shelters = db.query(models.Shelter).count()
    open_shelters = db.query(models.Shelter).filter(
        models.Shelter.status == "open"
    ).count()
    full_shelters = db.query(models.Shelter).filter(
        models.Shelter.status == "full"
    ).count()
    
    total_capacity = db.query(models.Shelter).with_entities(
        func.sum(models.Shelter.max_capacity)
    ).scalar() or 0
    
    current_occupancy = db.query(models.Shelter).with_entities(
        func.sum(models.Shelter.current_occupancy)
    ).scalar() or 0
    
    return {
        "total_transferred": total_transferred,
        "total_shelters": total_shelters,
        "open_shelters": open_shelters,
        "full_shelters": full_shelters,
        "total_capacity": total_capacity,
        "current_occupancy": current_occupancy,
        "utilization_rate": round(current_occupancy / total_capacity * 100, 2) if total_capacity > 0 else 0
    }
