@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python train.py
python make_demo.py
python dehaze.py examples\hazy_input.jpg --output examples\gan_dehazed.jpg
pause

