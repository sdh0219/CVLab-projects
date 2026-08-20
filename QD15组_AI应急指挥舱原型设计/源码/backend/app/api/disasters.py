from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/api/disasters", tags=["灾情态势"])


@router.get("/statistics")
def get_disaster_statistics(db: Session = Depends(get_db)):
    """获取灾情统计数据"""
    total_events = db.query(models.DisasterEvent).count()
    events_by_type = {}
    for event_type in models.DisasterType:
        count = db.query(models.DisasterEvent).filter(
            models.DisasterEvent.disaster_type == event_type
        ).count()
        events_by_type[event_type.value] = count
    
    total_affected = db.query(models.DisasterEvent).with_entities(
        func.sum(models.DisasterEvent.affected_population)
    ).scalar() or 0
    
    return {
        "total_events": total_events,
        "events_by_type": events_by_type,
        "total_affected_population": total_affected
    }


@router.get("/", response_model=List[schemas.DisasterEventResponse])
def get_disaster_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取灾情事件列表"""
    events = db.query(models.DisasterEvent).offset(skip).limit(limit).all()
    return events


@router.get("/{event_id}", response_model=schemas.DisasterEventResponse)
def get_disaster_event(event_id: int, db: Session = Depends(get_db)):
    """获取单个灾情事件"""
    event = db.query(models.DisasterEvent).filter(models.DisasterEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="灾情事件不存在")
    return event


@router.post("/", response_model=schemas.DisasterEventResponse)
def create_disaster_event(event: schemas.DisasterEventCreate, db: Session = Depends(get_db)):
    """创建灾情事件"""
    db_event = models.DisasterEvent(**event.model_dump())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event
