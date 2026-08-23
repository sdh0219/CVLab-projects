@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo 正在启动 AI融合平台看板增强版...
echo 使用解释器: Python 3.11
echo ==========================================

:: 下面这一行必须用英文双引号包裹整个路径
"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" -m streamlit run "%~dp0app.py"

pause