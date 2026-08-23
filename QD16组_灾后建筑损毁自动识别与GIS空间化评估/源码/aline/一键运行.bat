@echo off
chcp 65001 >nul 2>&1
title 16组 灾后建筑损毁自动识别 - 一键推理
echo ============================================================
echo   16组 灾后建筑损毁自动识别与 GIS 空间化评估
echo   一键安装依赖 + 加载预训练权重 + 推理（CPU 模式）
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

REM ---- 切换到脚本所在目录（源码\aline\）----
cd /d "%~dp0"

REM ---- 检查权重文件 ----
if not exist "outputs\checkpoints\best.pth" (
    echo [错误] 预训练权重文件 outputs\checkpoints\best.pth 不存在！
    echo.
    echo 这个文件（105 MB）因超过 GitHub 限制可能未随项目一起获取。
    echo 请从以下途径获取：
    echo   1. 从项目提供者处获取 best.pth 文件
    echo   2. 放到 源码\aline\outputs\checkpoints\ 目录下
    echo   3. 重新运行此脚本
    echo.
    pause
    exit /b 1
)

REM ---- 创建虚拟环境 ----
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] 正在创建 Python 虚拟环境（首次运行需要约 30 秒）...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
) else (
    echo [1/4] 虚拟环境已存在，跳过
)

REM ---- 安装依赖 ----
echo [2/4] 正在安装依赖（PyTorch CPU 版 + OpenCV 等，首次需要约 5 分钟）...
echo       如果长时间无输出，请耐心等待，正在下载...
".venv\Scripts\python.exe" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu -q
if errorlevel 1 (
    echo [错误] PyTorch 安装失败，请检查网络连接
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install opencv-python shapely matplotlib tqdm numpy -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

REM ---- 运行推理（CPU 模式）----
echo.
echo [3/4] 正在运行推理（CPU 模式，加载预训练权重 best.pth）...
echo       对测试集影像进行建筑物损毁分级识别...
set FORCE_CPU=1
".venv\Scripts\python.exe" inference.py
if errorlevel 1 (
    echo.
    echo [错误] 推理运行失败
    echo.
    echo 常见原因：
    echo   1. 中文路径问题 - 请尝试将项目移到纯英文路径下（如 D:\projects\16group\）
    echo   2. 权重文件不匹配 - best.pth 与当前代码版本不一致
    echo   3. 测试数据缺失 - 检查 数据集\aline_dataset\test_ex\ 是否有影像文件
    echo.
    echo 详细报错信息见上方输出
    pause
    exit /b 1
)

REM ---- 运行统计 ----
echo.
echo [4/4] 正在生成统计数据和柱状图...
".venv\Scripts\python.exe" stats.py
if errorlevel 1 (
    echo [警告] 统计步骤出错，但推理结果已生成
) else (
    echo       统计完成 ✓
)

REM ---- 完成 ----
echo.
echo ============================================================
echo   运行完成！
echo.
echo   推理结果保存在：
echo   源码\aline\outputs\predictions\
echo     - *_overlay.png       （灾后影像 + 损毁着色叠加图）
echo     - *_dmg_color.png     （彩色损毁分级图）
echo     - *_dmg.npy           （损毁索引数据）
echo.
echo   统计结果保存在：
echo   源码\aline\outputs\stats\
echo     - *.csv               （逐栋损毁统计）
echo     - *.png               （损毁等级柱状图）
echo.
echo   可用图片查看器打开 .png 文件查看结果
echo ============================================================
pause
