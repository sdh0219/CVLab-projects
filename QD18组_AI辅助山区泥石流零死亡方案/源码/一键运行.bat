@echo off
chcp 65001 >nul 2>&1
title 18组 AI辅助山区泥石流零死亡方案 - 一键运行
echo ============================================================
echo   18组 AI辅助山区泥石流零死亡方案
echo   一键安装依赖 + 生成授权 + 运行 + 生成结果
echo ============================================================
echo.

REM ---- 检查 Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python！
    echo.
    echo 请先安装 Python 3.10 ~ 3.12：
    echo   1. 打开浏览器访问 https://www.python.org/downloads/
    echo   2. 下载并安装，安装时务必勾选 "Add Python to PATH"
    echo   3. 安装完成后重新双击此文件
    echo.
    echo [提示] 若 rasterio 安装失败，推荐改用 Anaconda/Miniconda，
    echo       详见 复现指南.md 第六章 6.5 节。
    echo.
    pause
    exit /b 1
)

REM ---- 切换到脚本所在目录（源码/）----
cd /d "%~dp0"

REM 国内镜像（如不需要可删除 -i 后面那段）
set PIP_INDEX=-i https://pypi.tuna.tsinghua.edu.cn/simple

REM ---- 创建虚拟环境 ----
if not exist ".venv\Scripts\python.exe" (
    echo [1/5] 正在创建 Python 虚拟环境（首次约 30 秒）...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请检查 Python 是否正确安装
        pause
        exit /b 1
    )
) else (
    echo [1/5] 虚拟环境已存在，跳过
)

REM ---- 升级 pip ----
".venv\Scripts\python.exe" -m pip install --upgrade pip -q %PIP_INDEX%

REM ---- 安装依赖（rasterio 单独装，便于定位失败）----
echo.
echo [2/5] 正在安装依赖（首次约 1~3 分钟，请耐心等待）...
echo       第一步：numpy / matplotlib / pycryptodome / psycopg2-binary
".venv\Scripts\python.exe" -m pip install "numpy==2.2.6" "matplotlib==3.10.9" "pycryptodome==3.23.0" "psycopg2-binary==2.9.12" -q %PIP_INDEX%
if errorlevel 1 (
    echo [警告] 部分依赖安装失败，正在重试（去掉 -q 显示详细日志）...
    ".venv\Scripts\python.exe" -m pip install "numpy==2.2.6" "matplotlib==3.10.9" "pycryptodome==3.23.0" "psycopg2-binary==2.9.12" %PIP_INDEX%
)

echo       第二步：rasterio（含 GDAL，体积较大）
".venv\Scripts\python.exe" -m pip install "rasterio==1.4.4" -q %PIP_INDEX%
if errorlevel 1 (
    echo [警告] 镜像安装 rasterio 失败，改用默认源重试...
    ".venv\Scripts\python.exe" -m pip install "rasterio==1.4.4"
)

REM ---- 验证 rasterio 是否真的可用 ----
".venv\Scripts\python.exe" -c "import rasterio; print('rasterio', rasterio.__version__)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ============================================================
    echo [错误] rasterio 安装失败或无法导入！
    echo.
    echo rasterio 依赖 GDAL 库，Windows 下 pip 偶尔装不上。
    echo 请改用 conda 方式（详见 复现指南.md 第六章 6.5 节）：
    echo.
    echo   conda create -n debris-flow python=3.10 -y
    echo   conda activate debris-flow
    echo   conda install -c conda-forge gdal rasterio numpy=2.2.6 matplotlib=3.10.9 -y
    echo   pip install pycryptodome==3.23.0 psycopg2-binary==2.9.12
    echo.
    echo   cd /d "%~dp0"
    echo   python keygen.py
    echo   python main.py
    echo ============================================================
    pause
    exit /b 1
)

REM ---- 生成设备绑定授权 license（单次授权，每次运行前必须重新生成）----
echo.
echo [3/5] 正在生成设备绑定授权 license...
".venv\Scripts\python.exe" keygen.py
if errorlevel 1 (
    echo [错误] 授权生成失败
    pause
    exit /b 1
)

REM ---- 运行主程序 ----
echo.
echo [4/5] 正在运行主程序
echo       流程：解密数据 ^> AHP易发性评估 ^> 降雨监测 ^> 分级预警
echo             ^> 转移路线规划 ^> 救援调度 ^> 数据导出 ^> 可视化出图
echo       首次运行约需 1~2 分钟，请耐心等待...
echo.
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo.
    echo ============================================================
    echo [错误] 主程序运行失败
    echo.
    echo 常见原因与对策：
    echo   1) 授权失效 / 设备不匹配
    echo      - license 为单次授权，请重新双击此文件（会自动重新生成）
    echo      - 必须在“同一台电脑”上生成并运行（绑定 MAC+主机名）
    echo   2) 路径找不到数据
    echo      - 检查 源码\config.json 中 paths 是否指向真实目录
    echo      - 若移动过项目文件夹，请同步修改 config.json 的路径
    echo   3) 解密失败
    echo      - 切勿手动修改 数据集\database_data\*.enc 文件
    echo ============================================================
    pause
    exit /b 1
)

REM ---- 完成 ----
echo.
echo ============================================================
echo   运行完成！
echo.
echo   结果文件保存在：
echo   源码\output\
echo.
echo   关键结果文件：
echo     fig1_risk_assessment.png     泥石流易发性 + 风险等级图
echo     fig2_factor_scores.png       10 因子标准化得分图
echo     fig3_monitoring_stations.png 雨量监测站点分布
echo     fig4_warning_simulation.png  分级预警区域模拟
echo     fig5_evacuation_routes.png   群众转移路线规划
echo     fig6_dem_risk_overlay.png    DEM 高程与易发性对比
echo     grid_data.csv                逐像元数据（Excel 可直接打开）
echo     monitoring_stations.json     监测站点
echo     evacuation_plans.json         转移计划
echo     warning_rules.json           预警规则
echo     rescue_forces.json           救援力量
echo     settlements.json             高风险聚落
echo.
echo   .png  双击用图片查看器打开
echo   .csv  用 Excel 或记事本打开
echo   .json 用记事本或浏览器打开
echo ============================================================
echo.
echo [5/5] 提示：授权为“单次使用”，下次运行本脚本会自动重新生成。
pause
