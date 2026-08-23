@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 936 >nul
cd /d "%~dp0"

rem ============================================
rem start_project.bat
rem ============================================
rem 职责：启动地震预警系统
rem 前置条件：已通过 一键部署环境.bat 完成部署
rem ============================================

set "PROJECT_DIR=%~dp0"
set "LOGS_DIR=%PROJECT_DIR%logs"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

for /f "delims=" %%I in ('powershell -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set "TIMESTAMP=%%I"
set "LOG_FILE=%LOGS_DIR%\start_%TIMESTAMP%.txt"

echo ================================================
echo  地震预警信息自动生成系统
echo ================================================
echo 项目路径: %PROJECT_DIR%
echo 日志文件: %LOG_FILE%
echo.

>> "%LOG_FILE%" echo ================================================
>> "%LOG_FILE%" echo 启动日志 - %DATE% %TIME%
>> "%LOG_FILE%" echo 项目路径：%PROJECT_DIR%
>> "%LOG_FILE%" echo ================================================

rem ── 1. 检查虚拟环境 ──
echo [1/8] 检查虚拟环境...
set "VENV_DIR=%PROJECT_DIR%.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo.
    echo  项目环境尚未部署。
    echo 正在自动调用环境部署脚本完成安装...
    echo.
    >> "%LOG_FILE%" echo 虚拟环境不存在，自动调用部署脚本
    set "DEPLOY_BAT="
    for %%F in ("%PROJECT_DIR%*.bat") do (
        if /i not "%%~nxF"=="start_project.bat" set "DEPLOY_BAT=%%~fF"
    )
    if not defined DEPLOY_BAT (
        echo   错误：未找到环境部署脚本
        >> "%LOG_FILE%" echo 错误：未找到环境部署脚本
        pause
        exit /b 1
    )
    set "SKIP_START_PROMPT=1"
    call "!DEPLOY_BAT!"
    if errorlevel 1 (
        set "SKIP_START_PROMPT="
        echo   错误：自动部署失败
        >> "%LOG_FILE%" echo 错误：自动部署失败
        pause
        exit /b 1
    )
    set "SKIP_START_PROMPT="
    if not exist "%VENV_PYTHON%" (
        echo   错误：部署后仍未找到虚拟环境Python
        >> "%LOG_FILE%" echo 错误：部署后仍未找到 %VENV_PYTHON%
        pause
        exit /b 1
    )
)
echo   V 虚拟环境存在
>> "%LOG_FILE%" echo 虚拟环境：%VENV_PYTHON%

rem ── 2. 检查核心依赖 ──
echo [2/8] 检查核心依赖...
>> "%LOG_FILE%" echo [2/8] 检查依赖

"%VENV_PYTHON%" -c "import flask,pandas,matplotlib,requests; print('OK')" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ! 依赖不完整，尝试修复安装...
    >> "%LOG_FILE%" echo 依赖缺失，尝试修复
    "%VENV_PYTHON%" -m pip install -r "%PROJECT_DIR%requirements.txt" >> "%LOG_FILE%" 2>&1
    if %ERRORLEVEL% neq 0 (
        echo   错误：依赖修复失败
        >> "%LOG_FILE%" echo 错误：依赖修复失败
        pause
        exit /b 1
    )
    echo   V 依赖修复完成
)
echo   V 核心依赖检查通过
>> "%LOG_FILE%" echo 结果：通过

rem ── 3. 检查数据文件 ──
echo [3/8] 检查地震数据文件...
>> "%LOG_FILE%" echo [3/8] 检查数据

set "DATA_EXISTS=0"
if exist "%PROJECT_DIR%data\processed\earthquake_events_processed.csv" set "DATA_EXISTS=1"

if %DATA_EXISTS% equ 0 (
    echo   ! 处理后数据不存在
    >> "%LOG_FILE%" echo 处理后数据不存在
) else (
    echo   V 地震数据文件存在
    >> "%LOG_FILE%" echo 数据文件存在
)

rem ── 4. 检查app.py ──
echo [4/8] 检查应用文件...
>> "%LOG_FILE%" echo [4/8] 检查应用文件

if not exist "%PROJECT_DIR%app.py" (
    echo   错误：app.py 不存在
    >> "%LOG_FILE%" echo 错误：app.py 不存在
    pause
    exit /b 1
)
echo   V app.py 存在

rem ── 5. 运行main.py ──
echo [5/8] 运行 main.py（准备统计图）...
>> "%LOG_FILE%" echo [5/8] 执行 main.py

"%VENV_PYTHON%" "%PROJECT_DIR%main.py" >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ! main.py 执行异常
    >> "%LOG_FILE%" echo main.py 返回：%ERRORLEVEL%
) else (
    echo   V main.py 执行完成
    >> "%LOG_FILE%" echo main.py 执行成功
)

rem ── 6. 检查5000端口 ──
echo [6/8] 检查端口 5000...
>> "%LOG_FILE%" echo [6/8] 检查端口

netstat -ano | findstr ":5000 " >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo   ! 端口 5000 已被占用，将尝试关闭旧进程
    >> "%LOG_FILE%" echo 端口5000已被占用
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5000 "') do (
        if not "%%P"=="0" (
            taskkill /f /pid %%P >nul 2>&1
        )
    )
    timeout /t 2 /nobreak >nul
    echo   旧进程已关闭
    >> "%LOG_FILE%" echo 旧进程已关闭
) else (
    echo   V 端口 5000 可用
    >> "%LOG_FILE%" echo 端口5000可用
)

rem ── 7. 启动Flask ──
echo [7/8] 启动 Flask Web 服务...
>> "%LOG_FILE%" echo [7/8] 启动Flask

start "地震预警系统服务" cmd /k ""%VENV_PYTHON%" "%PROJECT_DIR%app.py""
echo   V Flask 已启动
>> "%LOG_FILE%" echo Flask进程已启动

rem ── 8. 等待服务就绪 ──
echo [8/8] 等待服务就绪...
>> "%LOG_FILE%" echo [8/8] 等待HTTP 200

set "WAIT_MAX=30"
set "WAIT_COUNT=0"

:wait_loop
set /a "WAIT_COUNT+=1"
if %WAIT_COUNT% gtr %WAIT_MAX% goto :wait_timeout

"%VENV_PYTHON%" -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:5000/', timeout=2); print(r.status)" > "%TEMP%\flask_status.txt" 2>&1
set /p HTTP_STATUS=<"%TEMP%\flask_status.txt"
if "%HTTP_STATUS%"=="200" goto :wait_ok

timeout /t 1 /nobreak >nul
goto :wait_loop

:wait_ok
echo   V 服务已就绪（HTTP 200）
>> "%LOG_FILE%" echo 结果：HTTP 200（第%WAIT_COUNT%秒）

start "" "http://127.0.0.1:5000"
echo   V 浏览器已打开
echo.
echo ================================================
echo  V 系统启动成功！
echo ================================================
echo.
echo 首页：http://127.0.0.1:5000
echo 仪表盘：http://127.0.0.1:5000/dashboard
echo 关闭Flask服务窗口即可停止项目。
echo.
echo 启动日志：%LOG_FILE%
echo.
>> "%LOG_FILE%" echo ================================================
>> "%LOG_FILE%" echo 启动结果：成功
>> "%LOG_FILE%" echo ================================================
echo 如果浏览器没有自动打开，请手动访问：http://127.0.0.1:5000
echo Flask服务在另一个窗口运行，关闭服务窗口即可停止项目。
echo.
echo 按任意键关闭本启动窗口...
pause >nul

goto :eof

:wait_timeout
echo   X 服务启动超时（%WAIT_MAX%秒）
>> "%LOG_FILE%" echo 错误：等待HTTP 200超时（%WAIT_MAX%秒）
echo.
echo 请检查日志：%LOG_FILE%
echo 可尝试手动运行：
echo   "%VENV_PYTHON%" "%PROJECT_DIR%app.py"
echo.
>> "%LOG_FILE%" echo ================================================
>> "%LOG_FILE%" echo 启动结果：超时失败
>> "%LOG_FILE%" echo ================================================

pause
exit /b 1
