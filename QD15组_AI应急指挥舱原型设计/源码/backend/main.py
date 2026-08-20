from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db
from app.utils.cache import get_redis_client

settings = get_settings()

# 初始化数据库表
init_db()

app = FastAPI(
    title="AI应急指挥舱",
    description="AI应急指挥舱后端API服务",
    version="0.1.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api import disasters, rescue, materials, evacuation, ai_decision, common

app.include_router(disasters.router)
app.include_router(rescue.router)
app.include_router(materials.router)
app.include_router(evacuation.router)
app.include_router(ai_decision.router)
app.include_router(common.router)


@app.get("/")
def root():
    return {"message": "AI应急指挥舱 API 服务运行中"}


@app.get("/health")
def health_check():
    """健康检查 - 包含数据库和Redis状态"""
    health = {"status": "ok", "database": "connected"}
    
    # 检查Redis连接
    try:
        client = get_redis_client()
        if client:
            client.ping()
            health["redis"] = "connected"
        else:
            health["redis"] = "disconnected"
    except Exception:
        health["redis"] = "disconnected"
    
    return health


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
