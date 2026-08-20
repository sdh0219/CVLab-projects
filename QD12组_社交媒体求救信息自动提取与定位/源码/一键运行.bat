@echo off
chcp 65001 >nul 2>&1
title 12组 社交媒体求救信息自动提取与定位 - 一键运行
echo ============================================================
echo   12组 社交媒体求救信息自动提取与定位
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

REM ---- 步骤 1: 创建虚拟环境 ----
if not exist ".venv\Scripts\python.exe" (
    echo [1/7] 正在创建 Python 虚拟环境（首次运行需要约 30 秒）...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请检查 Python 是否正确安装
        pause
        exit /b 1
    )
) else (
    echo [1/7] 虚拟环境已存在，跳过
)

REM ---- 步骤 2: 升级 pip ----
echo [2/7] 正在升级 pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q

REM ---- 步骤 3: 安装 PyTorch (CPU 版，不需要 GPU 也能跑) ----
".venv\Scripts\python.exe" -c "import torch" >nul 2>&1
if errorlevel 1 (
    echo [3/7] 正在安装 PyTorch CPU 版（约 200MB，首次需要 2-5 分钟）...
    echo       如有 NVIDIA 显卡想用 GPU 加速训练，可手动改用 GPU 版：
    echo       pip install torch --index-url https://download.pytorch.org/whl/cu121
    ".venv\Scripts\python.exe" -m pip install torch --index-url https://download.pytorch.org/whl/cpu -q
    if errorlevel 1 (
        echo [警告] PyTorch CPU 版安装失败，尝试默认源...
        ".venv\Scripts\python.exe" -m pip install torch -q
    )
) else (
    echo [3/7] PyTorch 已安装，跳过
)

REM ---- 步骤 4: 安装其他依赖 ----
echo [4/7] 正在安装其他依赖（transformers/jieba/seqeval/pandas/folium 等）...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接
    echo        可尝试使用国内镜像：pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause
    exit /b 1
)

REM ---- 步骤 5: 数据准备（生成地名库 + 原始数据 + BIO 标注）----
echo.
echo [5/7] 正在准备数据（地名库 + 数据集 + BIO 标注）...
".venv\Scripts\python.exe" -m src.geo.build_geo_dict
if errorlevel 1 echo       [警告] 地名库生成出错，将使用已有数据
".venv\Scripts\python.exe" -m src.data.build_dataset
if errorlevel 1 echo       [警告] 数据集生成出错，将使用已有数据
".venv\Scripts\python.exe" -m src.data.annotate
if errorlevel 1 echo       [警告] BIO 标注出错，将使用已有数据

REM ---- 步骤 6: 训练或推理（自动检测是否已有检查点）----
echo.
set HAS_CKPT=0
if exist "outputs\checkpoints\bert_ner_best\pytorch_model.bin" set HAS_CKPT=1

if "%HAS_CKPT%"=="1" (
    echo [6/7] 检测到已训练好的模型检查点，跳过训练（直接评估 + 推理）
    echo       项目已内置训练好的 BERT+CRF 模型，无需训练即可使用
    echo       如需重新训练，删除 outputs\checkpoints\bert_ner_best 文件夹后再运行
    echo.
    echo 正在评估模型（复现测试集 F1 = 0.95）...
    ".venv\Scripts\python.exe" -m src.evaluate
    if errorlevel 1 echo       [警告] 评估出错
    echo.
    echo 正在批量推理 288 条求救文本...
    ".venv\Scripts\python.exe" -m src.infer --batch
    if errorlevel 1 (
        echo [错误] 推理失败
        pause
        exit /b 1
    )
) else (
    echo [6/7] 未检测到检查点，开始训练 BERT NER 模型...
    echo       CPU 训练较慢（约 30-60 分钟），有 GPU 约 5-10 分钟
    echo       提示：可先用 --epochs 3 快速测试
    echo.
    echo 正在运行规则基线（对照实验）...
    ".venv\Scripts\python.exe" -m src.baselines.rule_based
    echo.
    echo 正在训练 BERT+CRF 模型...
    ".venv\Scripts\python.exe" -m src.train
    if errorlevel 1 (
        echo [错误] 训练失败
        pause
        exit /b 1
    )
    echo.
    echo 正在评估模型...
    ".venv\Scripts\python.exe" -m src.evaluate
    echo.
    echo 正在批量推理 288 条求救文本...
    ".venv\Scripts\python.exe" -m src.infer --batch
)

REM ---- 步骤 7: 生成求救点分布仪表盘 ----
echo.
echo [7/7] 正在生成求救点分布仪表盘（交互式 HTML 地图）...
if not exist "outputs\maps\static\jquery\jquery-3.7.1.min.js" (
    echo       首次使用，正在下载地图静态资源（约 278KB，一次即可）...
    ".venv\Scripts\python.exe" scripts\download_static.py
)
".venv\Scripts\python.exe" -m src.visualize
if errorlevel 1 echo       [警告] 可视化出错，可尝试手动运行 python -m src.visualize

REM ---- 完成 ----
echo.
echo ============================================================
echo   运行完成！
echo.
echo   结果文件保存在：
echo   源码\outputs\maps\rescue_map.html        ← 求救点分布仪表盘（浏览器打开）
echo   源码\outputs\reports\metrics.json         ← 评估指标（F1 约 0.95）
echo   源码\outputs\reports\training_curve.png   ← 训练曲线图（如已训练）
echo   数据集\processed\structured_results.csv   ← 结构化结果表（Excel 打开）
echo.
echo   怎么看结果：
echo     1. 双击 rescue_map.html → 浏览器打开求救点分布仪表盘
echo        （288 个求救点按真实经纬度标注，支持搜索/筛选/点击定位）
echo     2. 用 Excel 打开 structured_results.csv → 查看 288 条提取结果
echo        （含地点/人员/灾情/需求/经纬度等字段）
echo ============================================================
pause
