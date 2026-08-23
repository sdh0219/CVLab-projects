@echo off
python -m pip install -r requirements.txt
python main.py --data_dir .. --output_dir outputs
pause
