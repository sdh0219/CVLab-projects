@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo   救援物资分配优化系统 - 一键启动
echo.

where python >nul 2>&1
if %errorlevel% equ 0 (
    python start.py %*
    goto :end
)

where python3 >nul 2>&1
if %errorlevel% equ 0 (
    python3 start.py %*
    goto :end
)

echo 错误: 未找到 Python，请先安装 Python 3.8+
pause
exit /b 1

:end
