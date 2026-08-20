"""集中配置：路径、实体标签、训练超参数。

所有模块都从这里读取路径和常量，避免硬编码。
Run any script from project root:  python -m src.train
"""
from __future__ import annotations

import os
from pathlib import Path

# ------------------------------------------------------------------
# 路径配置 / Paths  (PROJ_ROOT = 项目根目录 = 本文件的上两级)
# ------------------------------------------------------------------
PROJ_ROOT = Path(__file__).resolve().parent.parent

# 数据集已按四分类规范迁移到项目根目录的"数据集/"文件夹
# （PROJ_ROOT = 源码/，其上一级为项目根目录 = 12组_社交媒体求救信息自动提取与定位/）
DATA_DIR = PROJ_ROOT.parent / "数据集"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
GEO_DIR = DATA_DIR / "geo"

OUTPUTS_DIR = PROJ_ROOT / "outputs"
CKPT_DIR = OUTPUTS_DIR / "checkpoints"
REPORTS_DIR = OUTPUTS_DIR / "reports"
MAPS_DIR = OUTPUTS_DIR / "maps"

# 关键文件路径 / key file paths
RAW_FILE = RAW_DIR / "distress_messages_raw.jsonl"
TRAIN_FILE = PROCESSED_DIR / "train.jsonl"
DEV_FILE = PROCESSED_DIR / "dev.jsonl"
TEST_FILE = PROCESSED_DIR / "test.jsonl"
STRUCTURED_CSV = PROCESSED_DIR / "structured_results.csv"
GEO_DICT_FILE = GEO_DIR / "china_geo_dict.json"
BEST_CKPT_DIR = CKPT_DIR / "bert_ner_best"
METRICS_FILE = REPORTS_DIR / "metrics.json"
BADCASE_FILE = REPORTS_DIR / "badcase.txt"
RESCUE_MAP_FILE = MAPS_DIR / "rescue_map.html"

# ------------------------------------------------------------------
# 实体标签体系 / Entity tag set (BIO scheme)
# 4 类实体: LOC(地点) PER(人员) DIS(灾情) NEED(需求)
# ------------------------------------------------------------------
ENTITY_TYPES = ["LOC", "PER", "DIS", "NEED"]

# 标签列表, 顺序固定. 0 = O, 1,2=B/I-LOC, ... 与模型输出维度对齐
TAG_LIST = ["O"] + [f"{p}-{t}" for t in ENTITY_TYPES for p in ("B", "I")]
TAG2ID = {t: i for i, t in enumerate(TAG_LIST)}
ID2TAG = {i: t for t, i in TAG2ID.items()}
NUM_TAGS = len(TAG_LIST)  # = 9

# ------------------------------------------------------------------
# 模型与训练超参数 / Model & Training hyperparameters
# ------------------------------------------------------------------
# 模型路径: 优先用项目内的本地权重 (绝对路径, 不受工作目录影响)
# 本地路径不存在时 (如未运行 download_model.py), 回退为 HuggingFace 模型名走在线下载
_LOCAL_BERT = PROJ_ROOT / "models" / "AI-ModelScope" / "bert-base-chinese"
BERT_MODEL_NAME = str(_LOCAL_BERT) if _LOCAL_BERT.exists() else "bert-base-chinese"
MAX_LEN = 128
TRAIN_BATCH = 16
EVAL_BATCH = 32
LEARNING_RATE = 2e-5
NUM_EPOCHS = 10
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.1
GRAD_CLIP = 1.0
USE_CRF = True              # 是否在 BERT 之上加 CRF 层
SEED = 42

# 数据划分比例 / data split ratio
SPLIT_RATIO = (0.7, 0.1, 0.2)  # train : dev : test

# 设备 / device (延迟导入 torch, 让数据构建等不依赖 torch 的脚本也能 import config)
def _detect_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"  # torch 未装时的占位; 训练/推理会提示先装


DEVICE = _detect_device()

# ------------------------------------------------------------------
# 地理编码 / Geocoding
# ------------------------------------------------------------------
# 在线 API Key (从环境变量读取; 不设置则只使用本地库)
AMAP_KEY = os.environ.get("AMAP_KEY", "")  # 高德地理编码 Key
BAIDU_AK = os.environ.get("BAIDU_AK", "")  # 百度地理编码 AK (备用)
GEOCODE_TIMEOUT = 5  # 在线请求超时秒数


def ensure_dirs() -> None:
    """运行前确保所有输出目录存在。"""
    for d in (DATA_DIR, RAW_DIR, PROCESSED_DIR, GEO_DIR,
              OUTPUTS_DIR, CKPT_DIR, REPORTS_DIR, MAPS_DIR, BEST_CKPT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def print_config() -> None:
    print("=" * 60)
    print("项目配置 / Project Configuration")
    print("=" * 60)
    print(f"  项目根目录   : {PROJ_ROOT}")
    print(f"  设备 / Device: {DEVICE}")
    print(f"  BERT 模型    : {BERT_MODEL_NAME}")
    print(f"  是否使用 CRF : {USE_CRF}")
    print(f"  实体类型     : {ENTITY_TYPES}")
    print(f"  标签数       : {NUM_TAGS} ({TAG_LIST})")
    print(f"  最大长度     : {MAX_LEN}")
    print(f"  超参 epoch   : {NUM_EPOCHS}, lr={LEARNING_RATE}, bs={TRAIN_BATCH}")
    print(f"  高德 API Key : {'已设置' if AMAP_KEY else '未设置(仅本地库)'}")
    print("=" * 60)
