#!/usr/bin/env bash
# ==========================================================
# 启动 TensorBoard 查看训练曲线
# 启动后浏览器访问: http://localhost:6006
# 按 Ctrl+C 停止
# ==========================================================
cd "$(dirname "$0")/.."

echo "=========================================================="
echo " 启动 TensorBoard..."
echo " 日志目录: outputs/reports/tensorboard"
echo " 浏览器访问: http://localhost:6006"
echo " 按 Ctrl+C 停止"
echo "=========================================================="

tensorboard --logdir outputs/reports/tensorboard --port 6006
