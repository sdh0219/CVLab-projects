#!/bin/bash
# 一键启动 - macOS / Linux
# 用法: ./start.sh  或  bash start.sh

cd "$(dirname "$0")"

if command -v python3 &>/dev/null; then
  python3 start.py "$@"
elif command -v python &>/dev/null; then
  python start.py "$@"
else
  echo "错误: 未找到 Python，请先安装 Python 3.8+"
  exit 1
fi
