@echo off
chcp 65001 >nul 2>&1
title 15组 AI应急指挥舱 - 一键运行
echo ============================================================
echo   15组 AI应急指挥舱原型设计
echo   一键安装依赖 + 导入数据 + 启动前后端
echo ============================================================
echo.

REM ---- 检查 Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python！
    echo   请先安装 Python 3.10+：https://www.python.org/downloads/
    echo   安装时务必勾选 "Add Python to PATH"
    pause
    exit /b 1
)

REM ---- 检查 Node.js ----
where node >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Node.js！
    echo   请先安装 Node.js 18+：https://nodejs.org/
    echo   下载 LTS 版本，安装时勾选 "Add to PATH"
    pause
    exit /b 1
)

REM ---- 切换到源码目录 ----
cd /d "%~dp0"

REM ==================== 后端 ====================
echo ============================================================
echo   [1/5] 后端环境配置
echo ============================================================

cd backend

if not exist ".venv\Scripts\python.exe" (
    echo   正在创建后端虚拟环境...
    python -m venv .venv
) else (
    echo   后端虚拟环境已存在
)

echo   正在安装后端依赖（首次约 2 分钟）...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo   [错误] 后端依赖安装失败
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   [2/5] 导入数据
echo ============================================================
if exist "import_real_data.py" (
    ".venv\Scripts\python.exe" import_real_data.py
    if errorlevel 1 (
        echo   [警告] 数据导入出错，尝试用基础数据初始化...
        ".venv\Scripts\python.exe" -c "from app.database import init_db; init_db()"
    ) else (
        echo   数据导入完成 ✓
    )
) else (
    echo   未找到 import_real_data.py，跳过数据导入
)

cd ..

REM ==================== 前端 ====================
echo.
echo ============================================================
echo   [3/5] 前端依赖安装
echo ============================================================
cd frontend

if not exist "node_modules" (
    echo   正在安装前端依赖（首次约 3 分钟，需下载约 200 MB）...
    call npm install
    if errorlevel 1 (
        echo   [错误] 前端依赖安装失败
        pause
        exit /b 1
    )
) else (
    echo   前端依赖已存在
)

cd ..

REM ==================== 启动 ====================
echo.
echo ============================================================
echo   [4/5] 启动后端服务
echo ============================================================
echo   后端地址: http://localhost:8000
echo   API 文档: http://localhost:8000/docs
echo.

start "后端服务 - AI应急指挥舱" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

echo ============================================================
echo   [5/5] 启动前端大屏
echo ============================================================
echo   前端地址: http://localhost:5173
echo.

start "前端大屏 - AI应急指挥舱" cmd /k "cd /d %~dp0frontend && npm run dev"

echo ============================================================
echo   启动完成！
echo.
echo   请等待两个窗口显示"running"后：
echo   1. 打开浏览器访问 http://localhost:5173 查看大屏
echo   2. API 接口文档在 http://localhost:8000/docs
echo.
echo   注意：
echo   - 不需要 Redis 和 OpenAI API key，大屏可正常显示
echo   - AI 决策功能不可用（需要 OpenAI key）
echo   - 关闭两个弹出窗口即可停止服务
echo ============================================================
echo.
pause
