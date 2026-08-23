# -*- coding: utf-8 -*-
"""
data_quality.py —— 数据质量统计与时间轴规整。

提供：
  - load_raw_rain(): 读取原始雨量计数据
  - regularize_timeaxis(): 时间戳去重、排序、对齐到规则时间网格（清洗第 0 步）
  - quality_report(): 计算缺失率、负值、超量程、卡滞、零值占比、统计量等质量指标
"""
import json
import numpy as np
import pandas as pd

from config import (
    FREQ, RAIN_MAX_PER_INTERVAL, STUCK_MIN_REPEAT,
    RAW_RAIN_CSV,
)


def load_raw_rain(path=RAW_RAIN_CSV) -> pd.DataFrame:
    """读取原始雨量计 CSV，解析时间戳。"""
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df


def regularize_timeaxis(df: pd.DataFrame, freq=FREQ) -> tuple[pd.DataFrame, dict]:
    """时间轴规整（清洗第 0 步）：

    1. 去除完全重复的时间戳（采集器重发）——保留首次出现；
    2. 按时间排序（修复乱序）；
    3. 重建规则时间网格（缺失的时刻补 NaN），使后续按位置/滚动窗口处理有意义。

    返回 (规整后DataFrame, 操作统计dict)。
    """
    info = {}
    n0 = len(df)

    # 1) 重复时间戳
    dup_mask = df.duplicated(subset=["timestamp"], keep="first")
    info["重复时间戳行数"] = int(dup_mask.sum())
    df = df[~dup_mask].copy()

    # 2) 乱序：检测是否非单调，再排序
    info["时间戳是否乱序"] = bool(not df["timestamp"].is_monotonic_increasing)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # 3) 对齐规则网格
    full_index = pd.date_range(df["timestamp"].min(), df["timestamp"].max(), freq=freq)
    df = df.set_index("timestamp").reindex(full_index)
    df.index.name = "timestamp"
    info["规整前行数"] = int(n0)
    info["规整后行数(规则网格)"] = int(len(df))
    info["对齐网格新增的缺失时刻数"] = int(len(df) - (n0 - info["重复时间戳行数"]))
    # 站点号回填
    if "station_id" in df.columns:
        df["station_id"] = df["station_id"].ffill().bfill()
    return df.reset_index(), info


def detect_stuck_runs(values: pd.Series, min_repeat=STUCK_MIN_REPEAT) -> np.ndarray:
    """检测"连续相同非零值"形成的卡滞游程，返回布尔数组（True=疑似卡滞）。

    注意：连续为 0（干期）是正常的，不算卡滞，只针对非零恒定读数。
    """
    v = values.to_numpy(dtype=float)
    n = len(v)
    stuck = np.zeros(n, dtype=bool)
    i = 0
    while i < n:
        j = i
        # 找到从 i 开始的等值游程（NaN 不参与）
        while (j + 1 < n and not np.isnan(v[i]) and v[j + 1] == v[i]):
            j += 1
        run_len = j - i + 1
        if run_len >= min_repeat and not np.isnan(v[i]) and v[i] > 0:
            stuck[i:j + 1] = True
        i = j + 1
    return stuck


def quality_report(df: pd.DataFrame, col="rainfall_mm") -> dict:
    """对某一雨量列计算数据质量指标。"""
    s = df[col]
    n = len(s)
    n_missing = int(s.isna().sum())
    n_negative = int((s < 0).sum())
    n_over = int((s > RAIN_MAX_PER_INTERVAL).sum())
    stuck = detect_stuck_runs(s)
    n_stuck = int(stuck.sum())
    valid = s.dropna()
    n_zero = int((valid == 0).sum())
    n_pos = int((valid > 0).sum())

    report = {
        "总样本数": n,
        "缺失值数": n_missing,
        "缺失率(%)": round(100 * n_missing / n, 2),
        "负值数": n_negative,
        "超量程数(>%.0fmm/10min)" % RAIN_MAX_PER_INTERVAL: n_over,
        "疑似卡滞点数": n_stuck,
        "零值(无雨)点数": n_zero,
        "有效降雨点数": n_pos,
        "完整率(%)": round(100 * (n - n_missing) / n, 2),
        "最大值": None if valid.empty else round(float(valid.max()), 2),
        "最小值": None if valid.empty else round(float(valid.min()), 2),
        "均值": None if valid.empty else round(float(valid.mean()), 4),
        "中位数": None if valid.empty else round(float(valid.median()), 4),
        "标准差": None if valid.empty else round(float(valid.std()), 4),
        "总降雨量(mm)": None if valid.empty else round(float(valid[valid > 0].sum()), 1),
    }
    return report


def save_report(report: dict, path):
    path = str(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raw = load_raw_rain()
    print("原始入库行数:", len(raw))
    reg, info = regularize_timeaxis(raw)
    print("\n--- 时间轴规整 ---")
    for k, v in info.items():
        print(f"  {k}: {v}")
    print("\n--- 规整后数据质量 ---")
    rep = quality_report(reg)
    for k, v in rep.items():
        print(f"  {k}: {v}")
