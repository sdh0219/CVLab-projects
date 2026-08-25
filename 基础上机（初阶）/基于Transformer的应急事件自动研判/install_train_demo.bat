@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python make_dataset.py
python train.py
python demo.py
pause

