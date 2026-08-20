from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import models
from app.schemas import schemas
from app.services.ai_service import get_ai_decision_workflow

router = APIRouter(prefix="/api/ai", tags=["AI辅助决策"])


@router.post("/decision", response_model=schemas.AIDecisionResponse)
async def create_ai_decision(
    request: schemas.AIDecisionRequest,
    db: Session = Depends(get_db)
):
    """创建AI辅助决策 - 完整工作流"""
    # 调用AI服务工作流
    ai_result = await get_ai_decision_workflow(request.natural_language_input)
    
    # 保存到数据库
    db_decision = models.AIDecision(
        disaster_event_id=request.disaster_event_id,
        input_data=request.natural_language_input,
        extracted_info=ai_result.get("extracted_info"),
        risk_assessment=ai_result.get("risk_assessment"),
        matched_cases=ai_result.get("matched_cases"),
        resource_prediction=ai_result.get("resource_prediction"),
        response_plan=ai_result.get("response_plan"),
        command_orders=ai_result.get("command_orders"),
        full_response=ai_result.get("full_response"),
        status="pending"
    )
    db.add(db_decision)
    db.commit()
    db.refresh(db_decision)
    
    return db_decision


@router.get("/decisions", response_model=list[schemas.AIDecisionResponse])
def get_ai_decisions(db: Session = Depends(get_db)):
    """获取AI决策记录列表"""
    return db.query(models.AIDecision).order_by(models.AIDecision.created_at.desc()).all()


@router.get("/decisions/{decision_id}", response_model=schemas.AIDecisionResponse)
def get_decision_by_id(decision_id: int, db: Session = Depends(get_db)):
    """获取单个AI决策记录"""
    decision = db.query(models.AIDecision).filter(
        models.AIDecision.id == decision_id
    ).first()
    if not decision:
        raise HTTPException(status_code=404, detail="决策记录不存在")
    return decision


@router.patch("/decisions/{decision_id}/confirm")
def confirm_ai_decision(decision_id: int, db: Session = Depends(get_db)):
    """确认AI决策"""
    decision = db.query(models.AIDecision).filter(
        models.AIDecision.id == decision_id
    ).first()
    if not decision:
        raise HTTPException(status_code=404, detail="决策记录不存在")
    
    decision.status = "confirmed"
    db.commit()
    return {"message": "决策已确认", "decision_id": decision_id}


@router.patch("/decisions/{decision_id}/reject")
def reject_ai_decision(decision_id: int, db: Session = Depends(get_db)):
    """拒绝AI决策"""
    decision = db.query(models.AIDecision).filter(
        models.AIDecision.id == decision_id
    ).first()
    if not decision:
        raise HTTPException(status_code=404, detail="决策记录不存在")
    
    decision.status = "rejected"
    db.commit()
    return {"message": "决策已拒绝", "decision_id": decision_id}
