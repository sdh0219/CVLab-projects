@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo 正在启动 AI赋能防灾减灾多源数据融合平台...
echo.
streamlit run "3_AI融合平台_前端增强版\app.py"
pause
