# -*- coding: utf-8 -*-
"""
A 线全局配置：建筑物灾后损毁自动识别
所有可调参数集中在此，方便在真 xBD 与本地调试间切换。
"""
import os

# ============ 路径 ============
ROOT = os.path.dirname(os.path.abspath(__file__))

# xBD 数据根目录。重构后数据集已移至项目根的"数据集/aline_dataset/"（含 train_ex/hold_ex/test_ex）。
# ROOT = 源码/aline/，项目根 = ROOT 上两级，路径自适应，迁移项目目录无需改源码。
PROJ_ROOT = os.path.dirname(os.path.dirname(ROOT))
DATA_ROOT = os.path.join(PROJ_ROOT, "数据集", "aline_dataset")

TRAIN_DIR = os.path.join(DATA_ROOT, "train_ex")
VAL_DIR   = os.path.join(DATA_ROOT, "hold_ex")   # xBD 用 hold 作验证；没有就复用 test
TEST_DIR  = os.path.join(DATA_ROOT, "test_ex")

CKPT_DIR  = os.path.join(ROOT, "outputs", "checkpoints")
PRED_DIR  = os.path.join(ROOT, "outputs", "predictions")
STATS_DIR = os.path.join(ROOT, "outputs", "stats")
for d in (CKPT_DIR, PRED_DIR, STATS_DIR):
    os.makedirs(d, exist_ok=True)

# ============ 类别定义 ============
# xBD 官方 4 级损毁标度 + 背景 + 建筑(定位)
# 损毁分类头：5 类
DAMAGE_CLASSES = ["background", "no-damage", "minor-damage", "major-damage", "destroyed"]
NUM_DAMAGE = len(DAMAGE_CLASSES)          # 5
NUM_LOC = 2                               # 定位头：背景 / 建筑

# xBD JSON 里的 subtype 字符串 → 损毁类别 id
SUBTYPE_TO_ID = {
    "no-damage": 1,
    "minor-damage": 2,
    "major-damage": 3,
    "destroyed": 4,
    "un-classified": 1,   # 未分类的当作完好处理，避免污染严重等级
}

# 可视化配色 (BGR for OpenCV)，与等级对应
DAMAGE_COLORS_BGR = {
    0: (0, 0, 0),         # background  黑
    1: (0, 180, 0),       # no-damage   绿
    2: (0, 220, 220),     # minor       黄
    3: (0, 120, 255),     # major       橙
    4: (0, 0, 230),       # destroyed   红
}

# ============ 影像 / 物理参数 ============
IMG_SIZE = 512            # 训练输入尺寸（真 xBD 为 1024，显存不够时下采样或切片，见 README）
GSD_M = 1.0            # 地面分辨率(米/像素)。xBD Maxar 影像约 0.5m；用于面积换算

# ============ 训练超参 ============
PRETRAINED = True        # 调试设 False（离线随机初始化）；真训练设 True 用 ImageNet 预训练编码器
ENCODER = "resnet34"
BATCH_SIZE = 4
EPOCHS = 30
LR = 1e-3
WEIGHT_DECAY = 1e-4
NUM_WORKERS = 2
DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"

# 损失类别权重（背景像素占绝大多数，需压低；损毁等级越重越关注）
DAMAGE_CLASS_WEIGHTS = [0.05, 1.0, 2.0, 2.0, 2.0]
LOSS_LOC_W = 0.4          # 定位损失权重
LOSS_DMG_W = 1.0          # 损毁分类损失权重
