@echo off
chcp 65001 >nul 2>&1
title 17组 灾后经济恢复周期预测 - 一键运行
echo ============================================================
echo   17组 灾后经济恢复周期预测
echo   一键安装依赖 + 生成数据 + 训练模型 + 生成汇报 PPT
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

REM ---- [1/8] 创建虚拟环境 ----
if not exist ".venv\Scripts\python.exe" (
    echo [1/8] 正在创建 Python 虚拟环境（首次运行需要约 30 秒）...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请检查 Python 是否正确安装
        pause
        exit /b 1
    )
) else (
    echo [1/8] 虚拟环境已存在，跳过
)

REM ---- [2/8] 安装依赖 ----
echo [2/8] 正在安装依赖（pandas / scikit-learn / matplotlib / joblib / python-pptx）...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接
    echo        可尝试使用国内镜像：
    echo        ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause
    exit /b 1
)

REM ---- [3/8] 建立数据目录链接 ----
echo [3/8] 正在建立数据目录链接（让脚本能找到 数据集\ 里的数据）...
if not exist "data\raw" (
    mklink /J data "..\数据集" >nul 2>&1
    if not exist "data\raw" (
        echo [警告] 自动建立数据链接失败。请在命令行手动执行：
        echo        cd /d "%~dp0"
        echo        mklink /J data "..\数据集"
        echo        然后重新双击此文件
        pause
        exit /b 1
    ) else (
        echo       数据链接已建立 ✓
    )
) else (
    echo       数据链接已存在，跳过
)

REM ---- 说明：原始数据已内置，跳过 download_data.py ----
echo.
echo [提示] 原始数据已内置在 数据集\raw\（USGS 地震目录 / NOAA 重大地震 / BEA 州级 GDP），
echo        正常复现无需重新下载，已自动跳过 download_data.py。
echo        如需下载最新数据，可手动运行：".venv\Scripts\python.exe" download_data.py
echo.

REM ---- [4/8] 生成探索性整合数据 ----
echo [4/8] 正在运行 process_data.py（生成探索性整合数据）...
".venv\Scripts\python.exe" process_data.py
if errorlevel 1 (
    echo [警告] process_data.py 运行出错，不影响后续建模，继续下一步
) else (
    echo       探索性数据生成完成 ✓
)

REM ---- [5/8] 生成建模数据集 ----
echo [5/8] 正在运行 prepare_rf_recovery_dataset.py（生成 1500 行建模数据集）...
".venv\Scripts\python.exe" prepare_rf_recovery_dataset.py --limit 1500 --output earthquake_rf_recovery_dataset_1500.csv
if errorlevel 1 (
    echo [错误] 建模数据集生成失败
    pause
    exit /b 1
) else (
    echo       建模数据集生成完成 ✓
)

REM ---- [6/8] 训练梯度提升树 ----
echo [6/8] 正在训练梯度提升树模型（GBDT，约 1-2 分钟）...
".venv\Scripts\python.exe" train_gradient_boosting_recovery.py
if errorlevel 1 (
    echo [错误] GBDT 训练失败，无法继续
    pause
    exit /b 1
) else (
    echo       GBDT 训练完成 ✓
)

REM ---- [7/8] 训练随机森林 ----
echo [7/8] 正在训练随机森林模型（RF，与 GBDT 使用同一份数据，约 1-2 分钟）...
".venv\Scripts\python.exe" train_random_forest_recovery.py --data-path "data\processed\earthquake_rf_recovery_dataset_1500.csv" --feature-path "data\processed\earthquake_recovery_feature_columns.txt" --output-dir "outputs\random_forest_recovery_1500"
if errorlevel 1 (
    echo [警告] RF 训练失败，继续生成 PPT（PPT 只依赖 GBDT，不依赖 RF）
) else (
    echo       RF 训练完成 ✓
)

REM ---- [8/8] 生成汇报 PPT ----
echo [8/8] 正在生成汇报 PPT...
".venv\Scripts\python.exe" generate_recovery_ppt.py
if errorlevel 1 (
    echo [错误] PPT 生成失败（需先完成第 6 步 GBDT 训练）
    pause
    exit /b 1
) else (
    echo       汇报 PPT 生成完成 ✓
)

REM ---- 可选：生成 GBDT 原理流程图 ----
echo.
echo [可选] 正在生成 GBDT 原理流程图...
".venv\Scripts\python.exe" create_gbdt_principle_flowchart.py
if errorlevel 1 (
    echo [提示] 原理图生成失败，不影响主要结果，可忽略
) else (
    echo       原理图生成完成 ✓
)

REM ---- 完成 ----
echo.
echo ============================================================
echo   运行完成！
echo.
echo   主要结果文件：
echo     源码\地震灾后经济恢复周期预测汇报.pptx        ← 汇报 PPT（双击用 PowerPoint 打开）
echo     源码\outputs\gradient_boosting_recovery_1500_improved_balanced\  ← GBDT 结果
echo     源码\outputs\random_forest_recovery_1500\      ← RF 结果
echo     源码\outputs\presentation\charts\              ← PPT 配图（10 张）
echo     源码\dpf\gbdt_principle_flowchart_hd.png       ← GBDT 原理图
echo.
echo   结果目录里的关键文件：
echo     metrics.json                 模型评估指标（准确率 / F1）
echo     confusion_matrix.png         混淆矩阵图
echo     feature_importance_top20.png 特征重要性图
echo     *.joblib                     训练好的模型
echo.
echo   可用 PowerPoint 打开 .pptx 文件查看汇报
echo   可用图片查看器打开 .png 文件
echo   可用记事本或 Excel 打开 .json / .csv 文件
echo ============================================================
pause
