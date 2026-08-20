@echo off
chcp 65001 >nul 2>&1
title 13组 基于遗传算法的救援物资分配优化 - 一键运行
echo ============================================================
echo   13组 基于遗传算法的救援物资分配优化
echo   一键安装依赖 + 运行 + 生成结果
echo ============================================================
echo.

REM ---- 检查 Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python！
    echo.
    echo 请先安装 Python 3.10+：
    echo   1. 打开浏览器访问 https://www.python.org/downloads/
    echo   2. 下载并安装，安装时务必勾选 "Add Python to PATH"
    echo   3. 安装完成后重新双击此文件
    echo.
    pause
    exit /b 1
)

REM ---- 切换到脚本所在目录（源码/）----
cd /d "%~dp0"

REM ---- 创建虚拟环境 ----
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] 正在创建 Python 虚拟环境（首次运行约 30 秒）...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请检查 Python 是否正确安装
        pause
        exit /b 1
    )
) else (
    echo [1/4] 虚拟环境已存在，跳过
)

REM ---- 激活虚拟环境并安装 Python 依赖 ----
call ".venv\Scripts\activate.bat"
echo [2/4] 正在安装 Python 依赖（numpy / pandas / matplotlib / flask 等）...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] Python 依赖安装失败，请检查网络连接
    echo        也可尝试手动执行：pip install -r requirements.txt
    pause
    exit /b 1
)
echo       Python 依赖安装完成

REM ---- 检测 Node.js（前端可视化所需）----
echo.
where npm >nul 2>&1
if errorlevel 1 (
    echo [3/4] 未检测到 Node.js - 启用降级方案：仅运行后端算法生成图表结果
    echo.
    echo [4/4] 正在运行遗传算法优化（河南洪灾基准案例，约 10-20 秒）...
    echo.
    python "code\main.py"
    if errorlevel 1 (
        echo.
        echo [错误] 后端运行失败，请查看上方报错信息
        pause
        exit /b 1
    )
    echo.
    echo ============================================================
    echo   后端运行完成！
    echo.
    echo   结果文件保存在：源码\output\
    echo     satisfaction_comparison.png  各受灾点满足率对比图
    echo     fitness_history.png          遗传算法收敛曲线
    echo     allocation_heatmap.png       仓库-受灾点分配热力图
    echo.
    echo   [提示] 当前为"仅后端"模式，未启动交互式可视化大屏。
    echo          如需查看 Web 可视化大屏，请安装 Node.js 18+：
    echo            https://nodejs.org/
    echo          安装后重新双击此文件即可自动启动完整系统。
    echo ============================================================
    pause
    exit /b 0
)

REM ---- Node.js 存在：启动完整系统（后端 + Web 可视化）----
echo [3/4] 检测到 Node.js，将启动完整系统（后端算法 + Web 可视化大屏）
echo       前端首次运行会自动安装依赖，请耐心等待 1-3 分钟
echo.
echo [4/4] 正在启动...
echo       启动后请在浏览器访问：http://127.0.0.1:5180
echo       后端 API 服务地址：  http://127.0.0.1:5181
echo       按 Ctrl+C 可停止服务
echo.
python start.py
echo.
echo 服务已停止。
pause
