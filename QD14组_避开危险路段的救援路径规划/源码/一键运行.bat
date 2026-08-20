@echo off
chcp 65001 >nul 2>&1
title 14组 避开危险路段的救援路径规划 - 一键运行
echo ============================================================
echo   14组 避开危险路段的救援路径规划
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
    echo [1/4] 正在创建 Python 虚拟环境（首次运行需要约 30 秒）...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请检查 Python 是否正确安装
        pause
        exit /b 1
    )
) else (
    echo [1/4] 虚拟环境已存在，跳过
)

REM ---- 安装依赖 ----
echo [2/4] 正在安装依赖（Pillow）...
".venv\Scripts\python.exe" -m pip install "Pillow>=10.0" -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)

REM ---- 运行地震场景 ----
echo.
echo [3/4] 正在运行地震场景（1679年三河-平谷地震）...
".venv\Scripts\python.exe" "src\rescue_planner.py" --data-dir "..\数据集\amap_earthquake" --output-dir "..\数据集\结果输出\amap_earthquake"
if errorlevel 1 (
    echo [警告] 地震场景运行出错，继续尝试洪水场景
) else (
    echo       地震场景完成 ✓
)

REM ---- 运行洪水场景 ----
echo.
echo [4/4] 正在运行洪水场景（2012年北京7·21暴雨）...
".venv\Scripts\python.exe" "src\rescue_planner.py" --data-dir "..\数据集\amap_flood" --output-dir "..\数据集\结果输出\amap_flood"
if errorlevel 1 (
    echo [警告] 洪水场景运行出错
) else (
    echo       洪水场景完成 ✓
)

REM ---- 完成 ----
echo.
echo ============================================================
echo   运行完成！
echo.
echo   结果文件保存在：
echo   数据集\结果输出\amap_earthquake\  （地震场景）
echo   数据集\结果输出\amap_flood\       （洪水场景）
echo.
echo   关键结果文件：
echo     path_comparison.csv    路径对比数据
echo     route_map.png          路线图
echo     route_map_abstract.png 抽象路网图
echo.
echo   可用文本编辑器或 Excel 打开 .csv 文件查看
echo   可用图片查看器打开 .png 文件查看
echo ============================================================
pause
