from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/api/materials", tags=["物资调度"])


@router.get("/", response_model=List[schemas.ReliefMaterialResponse])
def get_materials(db: Session = Depends(get_db)):
    """获取物资列表"""
    return db.query(models.ReliefMaterial).all()


@router.post("/", response_model=schemas.ReliefMaterialResponse)
def create_material(material: schemas.ReliefMaterialCreate, db: Session = Depends(get_db)):
    """创建物资记录"""
    db_material = models.ReliefMaterial(**material.model_dump())
    db.add(db_material)
    db.commit()
    db.refresh(db_material)
    return db_material


@router.get("/allocations", response_model=List[schemas.MaterialAllocationResponse])
def get_allocations(db: Session = Depends(get_db)):
    """获取物资调拨记录"""
    return db.query(models.MaterialAllocation).all()


@router.post("/allocations", response_model=schemas.MaterialAllocationResponse)
def create_allocation(allocation: schemas.MaterialAllocationCreate, db: Session = Depends(get_db)):
    """创建物资调拨记录"""
    # 检查库存
    material = db.query(models.ReliefMaterial).filter(
        models.ReliefMaterial.id == allocation.material_id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="物资不存在")
    if material.available < allocation.quantity:
        raise HTTPException(status_code=400, detail="库存不足")
    
    # 更新库存
    material.allocated += allocation.quantity
    material.available -= allocation.quantity
    
    # 创建调拨记录
    db_allocation = models.MaterialAllocation(**allocation.model_dump())
    db.add(db_allocation)
    db.commit()
    db.refresh(db_allocation)
    return db_allocation


@router.get("/statistics")
def get_material_statistics(db: Session = Depends(get_db)):
    """获取物资统计"""
    materials = db.query(models.ReliefMaterial).all()
    
    total_stock = sum(m.total_stock for m in materials)
    total_allocated = sum(m.allocated for m in materials)
    total_available = sum(m.available for m in materials)
    
    by_type = {}
    for m in materials:
        if m.material_type not in by_type:
            by_type[m.material_type] = {"stock": 0, "allocated": 0, "available": 0}
        by_type[m.material_type]["stock"] += m.total_stock
        by_type[m.material_type]["allocated"] += m.allocated
        by_type[m.material_type]["available"] += m.available
    
    return {
        "total_stock": total_stock,
        "total_allocated": total_allocated,
        "total_available": total_available,
        "by_type": by_type
    }


@router.post("/calculate-demand")
def calculate_material_demand(affected_population: int, db: Session = Depends(get_db)):
    """根据受灾人口计算物资需求量"""
    # 每人每天基本需求
    water_per_person = 3  # 3瓶/天
    food_per_person = 2   # 2份/天
    medicine_per_100 = 1  # 每100人1份
    tent_per_family = 1   # 每4人1顶帐篷
    
    demand = {
        "饮用水": {
            "quantity": affected_population * water_per_person,
            "unit": "瓶",
            "description": f"{affected_population}人 x {water_per_person}瓶/天"
        },
        "食品": {
            "quantity": affected_population * food_per_person,
            "unit": "份",
            "description": f"{affected_population}人 x {food_per_person}份/天"
        },
        "药品": {
            "quantity": max(1, affected_population // 100),
            "unit": "份",
            "description": f"每100人1份"
        },
        "帐篷": {
            "quantity": max(1, affected_population // 4),
            "unit": "顶",
            "description": f"每4人1顶"
        }
    }
    
    return {"affected_population": affected_population, "demand": demand}
