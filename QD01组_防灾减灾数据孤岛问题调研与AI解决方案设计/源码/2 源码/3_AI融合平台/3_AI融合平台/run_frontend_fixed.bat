@echo off
chcp 65001 >nul
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
cd /d "%~dp0"
echo 正在启动 AI赋能防灾减灾多源数据融合平台...
echo.
C:\Users\Lenovo\AppData\Local\Programs\Python\Python310\python.exe -m streamlit run "%~dp0app.py"
pause
