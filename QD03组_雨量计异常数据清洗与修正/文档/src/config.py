# -*- coding: utf-8 -*-
"""
config.py —— 全局配置：路径、随机种子、物理常量、绘图样式（中文字体）

雨量计异常数据清洗与纠正项目
所有模块共用本文件中的常量与路径定义，保证可复现。
"""
from pathlib import Path
import os
import sys
import matplotlib
import matplotlib.dates as mdates
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# ----------------------------------------------------------------------------
# 1. 路径定义（以项目根目录为基准，自动定位，避免硬编码绝对路径）
# ----------------------------------------------------------------------------
SRC_DIR = Path(__file__).resolve().parent
if os.environ.get("RAIN_GAUGE_ROOT_DIR"):
    ROOT_DIR = Path(os.environ["RAIN_GAUGE_ROOT_DIR"]).resolve()
elif getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = SRC_DIR.parent

DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_CLEANED_DIR = ROOT_DIR / "data" / "cleaned"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATA_REAL_DIR = ROOT_DIR / "data" / "real"
DATA_REAL_PROCESSED_DIR = DATA_REAL_DIR
FIG_DIR = ROOT_DIR / "output" / "figures"
REPORT_DIR = ROOT_DIR / "output" / "reports"

for _d in (DATA_RAW_DIR, DATA_CLEANED_DIR, DATA_PROCESSED_DIR,
           DATA_REAL_DIR, DATA_REAL_PROCESSED_DIR, FIG_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# 关键文件名
RAW_RAIN_CSV = DATA_RAW_DIR / "rain_gauge_raw.csv"            # 含异常的原始雨量计数据
RAW_MULTI_CSV = DATA_RAW_DIR / "multi_sensor_raw.csv"        # 雨量计+水位站+气象站多传感器原始数据
TRUTH_CSV = DATA_RAW_DIR / "rain_gauge_truth.csv"           # 真值（仅用于评估，不参与清洗）
CLEANED_CSV = DATA_CLEANED_DIR / "rain_gauge_cleaned.csv"   # 清洗后数据
FLAG_CSV = DATA_CLEANED_DIR / "rain_gauge_flags.csv"        # 异常标记明细
CLEANED_QUALITY_CSV = DATA_PROCESSED_DIR / "cleaned_with_quality_flags.csv"
REAL_RAW_CSV = DATA_REAL_DIR / "raw_real_rainfall.csv"
REAL_PROCESSED_CSV = DATA_REAL_PROCESSED_DIR / "processed_real_qc.csv"
QUALITY_BEFORE_JSON = REPORT_DIR / "quality_before.json"
QUALITY_AFTER_JSON = REPORT_DIR / "quality_after.json"
EVAL_JSON = REPORT_DIR / "evaluation.json"
SUMMARY_TXT = REPORT_DIR / "summary.txt"
FEATURE_SUMMARY_CSV = REPORT_DIR / "feature_summary.csv"
ML_SCORES_CSV = REPORT_DIR / "ml_anomaly_scores.csv"
HYBRID_QC_CSV = REPORT_DIR / "hybrid_qc_decisions.csv"
METHOD_COMPARISON_CSV = REPORT_DIR / "method_comparison.csv"
ABLATION_RESULTS_CSV = REPORT_DIR / "ablation_results.csv"
WARNING_IMPACT_CSV = REPORT_DIR / "warning_impact.csv"
WARNING_IMPACT_SUMMARY_MD = REPORT_DIR / "warning_impact_summary.md"
REAL_VALIDATION_SUMMARY_MD = REPORT_DIR / "real_data_validation_summary.md"

# ----------------------------------------------------------------------------
# 2. 随机种子（保证数据生成、实验完全可复现）
# ----------------------------------------------------------------------------
RANDOM_SEED = 2024

# ----------------------------------------------------------------------------
# 3. 物理常量与业务阈值
# ----------------------------------------------------------------------------
# 采样分辨率：10 分钟
FREQ = "10min"
SAMPLES_PER_HOUR = 6

# 翻斗式雨量计分辨率：每翻斗 0.1 mm
TIP_RESOLUTION = 0.1

# 单个 10min 间隔物理上限（防灾意义下的极端短时雨强约束）。
# 中国短时强降水预警量级：10min 雨量超过约 16 mm 已属极端；
# 留出余量，设 40 mm/10min 为"物理不可能"的硬上限（超过即判超量程异常）。
RAIN_MAX_PER_INTERVAL = 40.0    # mm / 10min，硬上限
RAIN_PLAUSIBLE_PER_INTERVAL = 20.0  # mm / 10min，统计可疑阈值（结合上下文判断）

# 传感器卡滞判定：连续相同的"非零"值出现次数阈值
STUCK_MIN_REPEAT = 6            # 连续 6 个间隔（=1 小时）数值完全不变且非零 -> 卡滞

# 统计离群检测：滚动窗口与稳健离群倍数（基于 MAD）
ROLL_WINDOW = 13               # 滚动窗口长度（奇数，约 2 小时）
MAD_THRESHOLD = 8.0            # 稳健 Z 分数阈值（保守，避免误杀真实暴雨峰值）

# 虚假翻斗检测：干期孤立微量降雨
SPURIOUS_WINDOW = 3
SPURIOUS_MAX_TIP = 0.3

# 插值最长连续填补间隔（超过则视为长缺失，不做插值，保留缺失或置零并标注）
INTERP_LIMIT = 6               # 最多连续插补 6 个点（=1 小时）

# 滑动窗口平滑参数
SMOOTH_MEDIAN_WINDOW = 3       # 中值滤波窗口（去残余尖峰）
SMOOTH_MEAN_WINDOW = 3         # 移动平均窗口（轻度降噪）

# ----------------------------------------------------------------------------
# 4. 学习型异常检测配置（均为辅助 QC，不替代规则主线）
# ----------------------------------------------------------------------------
IF_CONTAMINATION = 0.035

LSTM_WINDOW_SIZE = 18          # 18 * 10min = 3h 历史窗口
LSTM_HIDDEN_DIM = 16
LSTM_EPOCHS = 20
LSTM_BATCH_SIZE = 128
LSTM_LEARNING_RATE = 1e-3
LSTM_THRESHOLD_QUANTILE = 0.99
LSTM_MIN_TRAIN_SEQUENCES = 120

# ----------------------------------------------------------------------------
# 5. 防灾预警阈值配置
# ----------------------------------------------------------------------------
WARNING_THRESHOLDS = {
    "10min": {"window": 1, "threshold_mm": 16.0, "label": "10min强降雨"},
    "1h": {"window": 6, "threshold_mm": 30.0, "label": "1h累计雨量"},
    "3h": {"window": 18, "threshold_mm": 50.0, "label": "3h累计雨量"},
    "24h": {"window": 144, "threshold_mm": 100.0, "label": "24h累计雨量"},
}

# ----------------------------------------------------------------------------
# 6. 绘图样式：中文字体 + 统一风格
# ----------------------------------------------------------------------------
# 中文字体按常见运行环境回退；Windows 下优先使用微软雅黑，标题更清晰。
_CN_FONTS = ["Microsoft YaHei", "DengXian", "SimHei", "SimSun",
             "Arial Unicode MS", "Heiti TC", "PingFang HK", "STHeiti", "Songti SC"]


def setup_matplotlib():
    """配置 matplotlib 中文显示与统一风格。"""
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = _CN_FONTS
    matplotlib.rcParams["axes.unicode_minus"] = False  # 正常显示负号
    matplotlib.rcParams["figure.dpi"] = 110
    matplotlib.rcParams["savefig.dpi"] = 150
    matplotlib.rcParams["savefig.bbox"] = "tight"
    matplotlib.rcParams["font.size"] = 11
    matplotlib.rcParams["axes.grid"] = True
    matplotlib.rcParams["grid.alpha"] = 0.3
    matplotlib.rcParams["axes.titlesize"] = 13
    matplotlib.rcParams["axes.titleweight"] = "normal"
    matplotlib.rcParams["axes.labelsize"] = 11
    matplotlib.rcParams["xtick.labelsize"] = 10
    matplotlib.rcParams["ytick.labelsize"] = 10


def _axes_list(axes):
    if isinstance(axes, (list, tuple)):
        out = []
        for item in axes:
            out.extend(_axes_list(item))
        return out
    if hasattr(axes, "flat"):
        return list(axes.flat)
    return [axes]


def style_axis(ax):
    """统一图表坐标轴细节，减少默认粗边框和杂乱感。"""
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#666666")
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors="#222222", width=0.8, length=3.5)
    return ax


def style_axes(axes):
    for ax in _axes_list(axes):
        style_axis(ax)


def format_date_axis(ax, timestamps, max_ticks=6, date_fmt=None, rotation=0):
    """压缩时间刻度，避免长时间序列横轴标签重叠。"""
    ts = pd.to_datetime(pd.Series(timestamps)).dropna()
    locator = mdates.AutoDateLocator(minticks=4, maxticks=max_ticks)
    if date_fmt is None:
        date_fmt = "%m-%d"
        if not ts.empty and ts.dt.year.nunique() > 1:
            date_fmt = "%Y-%m-%d"
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(date_fmt))
    ax.tick_params(axis="x", labelsize=9, rotation=rotation, pad=5)
    ax.margins(x=0.01)
    if not ts.empty:
        ax.set_xlim(ts.min(), ts.max())


def time_axis_label(timestamps):
    ts = pd.to_datetime(pd.Series(timestamps)).dropna()
    years = ts.dt.year.unique()
    if len(years) == 1:
        return f"时间（{int(years[0])}）"
    return "时间"


def rotate_xticklabels(ax, rotation=20):
    for tick in ax.get_xticklabels():
        tick.set_rotation(rotation)
        tick.set_ha("right" if rotation else "center")


def add_bar_labels(ax, bars, fmt="{:.0f}", dy=2, fontsize=9):
    for bar in bars:
        value = bar.get_height()
        if pd.isna(value):
            continue
        label = fmt.format(value)
        va = "bottom" if value >= 0 else "top"
        offset = dy if value >= 0 else -dy
        ax.annotate(
            label,
            xy=(bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center",
            va=va,
            fontsize=fontsize,
        )


def set_suptitle(fig, title, fontsize=13.5, y=0.965):
    fig.suptitle(title, fontsize=fontsize, fontweight="normal", y=y)


def finish_figure(fig, path=None, rect=(0, 0.01, 1, 0.94), w_pad=None, h_pad=None):
    kwargs = {"rect": rect}
    if w_pad is not None:
        kwargs["w_pad"] = w_pad
    if h_pad is not None:
        kwargs["h_pad"] = h_pad
    fig.tight_layout(**kwargs)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path)


# 统一配色（异常类型 -> 颜色），供各图复用，保证全项目视觉一致
ANOMALY_COLORS = {
    "missing": "#9e9e9e",      # 缺失：灰
    "negative": "#1f77b4",     # 负值：蓝
    "spike": "#d62728",        # 尖峰/超量程：红
    "stuck": "#9467bd",        # 卡滞：紫
    "spurious": "#ff7f0e",     # 虚假翻斗：橙
}

ANOMALY_CN = {
    "missing": "缺失值",
    "negative": "负值",
    "spike": "尖峰/超量程",
    "stuck": "传感器卡滞",
    "spurious": "虚假翻斗",
}

if __name__ == "__main__":
    setup_matplotlib()
    print("项目根目录:", ROOT_DIR)
    print("随机种子:", RANDOM_SEED)
    print("中文字体回退顺序:", _CN_FONTS)
