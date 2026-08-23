@echo off
setlocal EnableExtensions
chcp 936 >nul
cd /d "%~dp0"

rem ============================================
rem 一键部署环境.bat
rem ============================================
rem 职责：在全新Windows电脑上一键完成项目环境部署
rem 包括：检测/安装Python、创建虚拟环境、安装依赖、
rem       生成地震数据、执行项目自检
rem ============================================

set "PROJECT_DIR=%~dp0"
set "LOGS_DIR=%PROJECT_DIR%logs"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

rem 生成时间戳（日志文件用）
for /f "delims=" %%I in ('powershell -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set "TIMESTAMP=%%I"
set "LOG_FILE=%LOGS_DIR%\deploy_%TIMESTAMP%.txt"

echo ================================================
echo  地震预警信息自动生成系统 - 环境部署
echo ================================================
echo 项目路径: %PROJECT_DIR%
echo 日志文件: %LOG_FILE%
echo.

>> "%LOG_FILE%" echo ================================================
>> "%LOG_FILE%" echo 部署日志 - %DATE% %TIME%
>> "%LOG_FILE%" echo 项目路径: %PROJECT_DIR%
>> "%LOG_FILE%" echo ================================================

rem ── 阶段1：检测项目文件 ──
echo [1/11] 检测项目文件完整性...
>> "%LOG_FILE%" echo [1/11] 检测项目文件完整性

if not exist "%PROJECT_DIR%app.py" (
    echo 错误：未找到 app.py（项目可能不完整）
    >> "%LOG_FILE%" echo 错误：未找到 app.py
    goto :deploy_failed
)
if not exist "%PROJECT_DIR%requirements.txt" (
    echo 错误：未找到 requirements.txt
    >> "%LOG_FILE%" echo 错误：未找到 requirements.txt
    goto :deploy_failed
)
if not exist "%PROJECT_DIR%code\" (
    echo 错误：未找到 code/ 目录
    >> "%LOG_FILE%" echo 错误：未找到 code/
    goto :deploy_failed
)
echo   V 项目文件完整性检查通过
>> "%LOG_FILE%" echo 结果：通过

rem ── 阶段2：检测Python ──
echo [2/11] 检测系统Python环境...
>> "%LOG_FILE%" echo [2/11] 检测系统Python环境

set "SYSTEM_PYTHON="

py -3.11 --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "delims=" %%I in ('py -3.11 -c "import sys; print(sys.executable)"') do set "SYSTEM_PYTHON=%%I"
    goto :python_found
)

py -3.12 --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "delims=" %%I in ('py -3.12 -c "import sys; print(sys.executable)"') do set "SYSTEM_PYTHON=%%I"
    goto :python_found
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "SYSTEM_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :python_found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "SYSTEM_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :python_found
)

python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)"') do set "SYSTEM_PYTHON=%%I"
    goto :python_found
)

echo   ! 未检测到可用的 Python 3.11/3.12，准备安装项目自带 Python 3.11
>> "%LOG_FILE%" echo 结果：未找到可用 Python 3.11/3.12，安装项目自带
goto :install_python

:python_found
echo   V 找到Python: "%SYSTEM_PYTHON%"
>> "%LOG_FILE%" echo 结果：%SYSTEM_PYTHON%
for /f "delims=" %%V in ('"%SYSTEM_PYTHON%" --version 2^>^&1') do (
    >> "%LOG_FILE%" echo 版本：%%V
    echo   版本: %%V
)
goto :after_python

rem ── 阶段3：安装项目自带Python ──
:install_python
echo [2/11] 安装项目自带Python 3.11...
>> "%LOG_FILE%" echo [2/11] 安装项目自带Python 3.11

set "RUNTIME_DIR=%PROJECT_DIR%runtime"
set "INSTALLER=%RUNTIME_DIR%\python-3.11.9-amd64.exe"

if not exist "%INSTALLER%" (
    echo 错误：Python安装程序未找到
    echo 请确保 runtime\python-3.11.9-amd64.exe 存在
    >> "%LOG_FILE%" echo 错误：安装程序不存在：%INSTALLER%
    goto :deploy_failed
)

echo   正在静默安装（按当前用户）...
>> "%LOG_FILE%" echo 执行安装程序

"%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_pip=1 Include_launcher=1 Include_test=0
set "INSTALL_EXIT=%ERRORLEVEL%"

if %INSTALL_EXIT% neq 0 (
    echo   错误：Python安装失败（错误码：%INSTALL_EXIT%）
    >> "%LOG_FILE%" echo 错误：Python安装失败，错误码：%INSTALL_EXIT%
    goto :deploy_failed
)

echo   Python安装完成，查找安装路径...
>> "%LOG_FILE%" echo Python安装完成

timeout /t 3 /nobreak >nul

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "SYSTEM_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    echo   V Python已安装: "%SYSTEM_PYTHON%"
    >> "%LOG_FILE%" echo 路径：%SYSTEM_PYTHON%
    goto :after_python
)

py -3.11 --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "delims=" %%I in ('py -3.11 -c "import sys; print(sys.executable)"') do set "SYSTEM_PYTHON=%%I"
    echo   V Python已安装: "%SYSTEM_PYTHON%"
    >> "%LOG_FILE%" echo 路径：%SYSTEM_PYTHON%
    goto :after_python
)

echo   错误：安装后无法定位Python
>> "%LOG_FILE%" echo 错误：安装后无法定位Python
goto :deploy_failed

:after_python

rem ── 阶段4：创建虚拟环境 ──
echo [3/11] 创建项目虚拟环境 .venv...
>> "%LOG_FILE%" echo [3/11] 创建虚拟环境

set "VENV_DIR=%PROJECT_DIR%.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

if exist "%VENV_PYTHON%" (
    echo   V 虚拟环境已存在（将复用）
    >> "%LOG_FILE%" echo 虚拟环境已存在，跳过创建
    goto :check_venv
)

>> "%LOG_FILE%" echo 执行："%SYSTEM_PYTHON%" -m venv "%VENV_DIR%"
"%SYSTEM_PYTHON%" -m venv "%VENV_DIR%"
if %ERRORLEVEL% neq 0 (
    echo   错误：虚拟环境创建失败（错误码：%ERRORLEVEL%）
    >> "%LOG_FILE%" echo 错误：虚拟环境创建失败，错误码：%ERRORLEVEL%
    goto :deploy_failed
)

echo   V 虚拟环境创建成功
>> "%LOG_FILE%" echo 结果：成功

:check_venv
if not exist "%VENV_PYTHON%" (
    echo   错误：虚拟环境Python不存在
    >> "%LOG_FILE%" echo 错误：%VENV_PYTHON% 不存在
    goto :deploy_failed
)

"%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ! 现有虚拟环境Python版本不兼容或已损坏，将删除并重建
    >> "%LOG_FILE%" echo 现有虚拟环境不可用，将删除并重建
    rmdir /s /q "%VENV_DIR%" >nul 2>&1
    goto :after_python
)

>> "%LOG_FILE%" echo 虚拟环境Python路径：%VENV_PYTHON%
for /f "delims=" %%V in ('"%VENV_PYTHON%" --version 2^>^&1') do (
    >> "%LOG_FILE%" echo 虚拟环境Python版本：%%V
)

rem ── 阶段5：升级pip ──
echo [4/11] 升级pip...
>> "%LOG_FILE%" echo [4/11] 升级pip

"%VENV_PYTHON%" -m pip install --upgrade pip >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ! pip升级失败（继续部署）
    >> "%LOG_FILE%" echo 警告：pip升级失败
) else (
    echo   V pip升级完成
    >> "%LOG_FILE%" echo 结果：成功
)

rem ── 阶段6：离线安装依赖 ──
echo [5/11] 安装项目依赖（优先离线）...
>> "%LOG_FILE%" echo [5/11] 安装依赖

set "WHEEL_DIR=%PROJECT_DIR%wheelhouse"

if exist "%WHEEL_DIR%" (
    dir /b "%WHEEL_DIR%\*.whl" >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo   发现离线包目录（wheelhouse），尝试离线安装...
        >> "%LOG_FILE%" echo 尝试离线安装
        "%VENV_PYTHON%" -m pip install --no-index --find-links="%WHEEL_DIR%" -r "%PROJECT_DIR%requirements.txt" >> "%LOG_FILE%" 2>&1
        if %ERRORLEVEL% equ 0 (
            echo   V 离线安装成功
            >> "%LOG_FILE%" echo 结果：离线安装成功
            goto :pip_check
        ) else (
            echo   ! 离线安装不完整，尝试联网补充...
            >> "%LOG_FILE%" echo 离线安装未完成，尝试联网
        )
    )
)

rem ── 阶段7：联网安装依赖 ──
echo   正在联网安装依赖...
>> "%LOG_FILE%" echo 尝试联网安装

"%VENV_PYTHON%" -m pip install -r "%PROJECT_DIR%requirements.txt" >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo   错误：依赖安装失败（请检查网络连接）
    >> "%LOG_FILE%" echo 错误：依赖安装失败
    goto :deploy_failed
)
echo   V 依赖安装成功
>> "%LOG_FILE%" echo 结果：成功

:pip_check
rem ── 阶段8：pip check ──
echo [6/11] 执行 pip check 验证依赖...
>> "%LOG_FILE%" echo [6/11] pip check

"%VENV_PYTHON%" -m pip check >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ! pip check 发现依赖问题
    >> "%LOG_FILE%" echo 警告：依赖存在冲突或缺失
) else (
    echo   V pip check 通过
    >> "%LOG_FILE%" echo 结果：通过
)

rem ── 阶段9：验证核心模块导入 ──
echo [7/11] 验证核心模块可导入...
>> "%LOG_FILE%" echo [7/11] 验证核心模块

"%VENV_PYTHON%" -c "import flask,pandas,matplotlib,requests,numpy; print('OK')" >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo   错误：核心模块导入失败
    >> "%LOG_FILE%" echo 错误：模块导入验证未通过
    goto :deploy_failed
)
echo   V 核心模块导入验证通过（flask, pandas, matplotlib, requests, numpy）
>> "%LOG_FILE%" echo 结果：通过

rem ── 阶段10：检查真实地震数据 ──
echo [8/11] 检查真实地震数据文件...
>> "%LOG_FILE%" echo [8/11] 检查数据

set "PROCESSED_DIR=%PROJECT_DIR%data\processed"
set "DATA_OK=0"
if exist "%PROCESSED_DIR%\earthquake_events_processed.csv" (
    set "DATA_OK=1"
    echo   V 处理后数据存在
    >> "%LOG_FILE%" echo 处理后数据存在
) else (
    echo   ! 处理后数据不存在
    >> "%LOG_FILE%" echo 处理后数据不存在
)

rem ── 阶段11：运行main.py ──
echo [9/11] 运行 main.py（生成四张地震统计图）...
>> "%LOG_FILE%" echo [9/11] 执行 main.py

"%VENV_PYTHON%" "%PROJECT_DIR%main.py" >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo   错误：main.py 运行失败
    >> "%LOG_FILE%" echo 错误：main.py 返回非零值
    goto :deploy_failed
)
echo   V main.py 执行成功
>> "%LOG_FILE%" echo 结果：成功

set "CHARTS_DIR=%PROJECT_DIR%static\charts"
set "CHARTS_OK=1"
if not exist "%CHARTS_DIR%" set "CHARTS_OK=0"
if not exist "%CHARTS_DIR%\magnitude_distribution.png" set "CHARTS_OK=0"
if not exist "%CHARTS_DIR%\depth_distribution.png" set "CHARTS_OK=0"
if not exist "%CHARTS_DIR%\time_trend.png" set "CHARTS_OK=0"
if not exist "%CHARTS_DIR%\location_scatter.png" set "CHARTS_OK=0"

if %CHARTS_OK% equ 1 (
    echo   V 四张地震统计图已生成
    >> "%LOG_FILE%" echo 统计图：四张全部存在
) else (
    echo   ! 统计图生成可能不完整
    >> "%LOG_FILE%" echo 统计图：部分缺失
)

rem ── 阶段12：Flask自检 ──
echo [10/11] 执行Flask基础自检...
>> "%LOG_FILE%" echo [10/11] Flask自检

"%VENV_PYTHON%" -c "import os,sys; sys.path.insert(0, os.environ['PROJECT_DIR']); from app import app; client=app.test_client(); r=client.get('/'); print(r.status_code); raise SystemExit(0 if r.status_code == 200 else 1)" >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ! 应用自检异常（不影响部署完成）
    >> "%LOG_FILE%" echo 自检结果：异常
) else (
    echo   V 应用自检通过
    >> "%LOG_FILE%" echo 自检结果：通过
)

rem ── 部署成功 ──
echo [11/11] 部署完成！
echo.
echo ================================================
echo  V 环境部署成功！
echo ================================================
echo.
echo 以后启动项目只需要双击：
echo   start_project.bat
echo.
echo 部署日志：%LOG_FILE%
echo.
>> "%LOG_FILE%" echo ================================================
>> "%LOG_FILE%" echo 部署结果：成功
>> "%LOG_FILE%" echo ================================================

if "%SKIP_START_PROMPT%"=="1" goto :eof

set /p START_NOW="是否现在启动项目？(Y/N): "
if /i "%START_NOW%"=="Y" (
    echo.
    echo 正在启动项目...
    call "%PROJECT_DIR%start_project.bat"
)

goto :eof

rem ── 部署失败 ──
:deploy_failed
echo.
echo ================================================
echo  X 环境部署失败！
echo ================================================
echo.
echo 请查看日志了解详情：
echo   %LOG_FILE%
echo.
>> "%LOG_FILE%" echo ================================================
>> "%LOG_FILE%" echo 部署结果：失败
>> "%LOG_FILE%" echo ================================================

pause
exit /b 1
