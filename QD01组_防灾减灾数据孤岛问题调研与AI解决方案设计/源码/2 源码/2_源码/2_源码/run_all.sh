#!/usr/bin/env bash
set -e
python -m pip install -r requirements.txt
python main.py --data_dir .. --output_dir outputs
