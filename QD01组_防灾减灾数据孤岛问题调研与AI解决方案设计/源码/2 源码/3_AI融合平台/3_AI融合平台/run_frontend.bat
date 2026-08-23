@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo 正在启动 AI赋能防灾减灾多源数据融合平台...
echo.
echo 如果浏览器没有自动打开，请复制终端中的 Local URL 到浏览器。
echo.
streamlit run "3_AI融合平台\app.py"
pause
