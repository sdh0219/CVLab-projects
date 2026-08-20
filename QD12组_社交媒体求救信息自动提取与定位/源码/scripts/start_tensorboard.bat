@echo off
REM ==========================================================
REM 启动 TensorBoard 查看训练曲线
REM 启动后浏览器访问: http://localhost:6006
REM 按 Ctrl+C 停止
REM ==========================================================
chcp 65001 >nul
cd /d "%~dp0\.."

echo ==========================================================
echo  启动 TensorBoard...
echo  日志目录: outputs\reports\tensorboard
echo  浏览器访问: http://localhost:6006
echo  按 Ctrl+C 停止
echo ==========================================================
echo.

".venv\Scripts\tensorboard.exe" --logdir outputs/reports/tensorboard --port 6006
