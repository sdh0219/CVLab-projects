# -*- coding: utf-8 -*-
"""
cleaning.py —— 异常修正与数据清洗主流程（对应技术方案"处理方法"）。

清洗管线（在已规整时间轴 + 已检测异常的基础上）：
  步骤1 异常掩膜    ：将所有被标记的异常点置为 NaN（统一交给插值处理）。
  步骤2 插值修正    ：基于时间的线性插值填补短缺口（连续缺口<=limit）；
                      超过 limit 的长缺口不臆造数值，保守置 0 并标注为低可信。
  步骤3 物理约束    ：非负约束（雨量 clip 到 >=0）+ 翻斗分辨率重量化(0.1mm)。
  步骤4 滑动窗口平滑：先中值滤波(去残余尖峰)，再轻度移动平均(降噪)，
                      作为可选的最终降噪结果，单列输出以便对比。

输出列：
  rainfall_mm        原始（含异常，规整后）
  rainfall_corrected 主清洗结果（去异常+插值+物理约束）—— 交付的"清洗后数据"
  rainfall_smoothed  在 corrected 上再做滑动窗口平滑的结果（供对比/降噪展示）
  flag               异常类型标记
  filled_longgap     是否为长缺口保守填补（低可信）
"""
import numpy as np
import pandas as pd

from config import (
    INTERP_LIMIT, TIP_RESOLUTION,
    SMOOTH_MEDIAN_WINDOW, SMOOTH_MEAN_WINDOW,
)


def mask_anomalies(df: pd.DataFrame, col="rainfall_mm") -> pd.Series:
    """步骤1：把被标记的异常点置 NaN，得到待插值序列。"""
    s = df[col].copy()
    s[df["is_anomaly"]] = np.nan
    return s


def interpolate_series(s: pd.Series, time_index: pd.Series, limit=INTERP_LIMIT):
    """步骤2：基于时间的线性插值，仅填补 <=limit 的连续缺口。

    返回 (插值后序列, 长缺口布尔掩码)。长缺口处保留 NaN（稍后保守置0）。
    """
    tmp = pd.Series(s.to_numpy(), index=pd.DatetimeIndex(time_index))
    # 标记插值前的缺口位置
    na_before = tmp.isna()
    interp = tmp.interpolate(method="time", limit=limit, limit_direction="both")
    # 经 limit 限制后仍为 NaN 的位置 = 长缺口
    longgap = interp.isna() & na_before
    interp = interp.reset_index(drop=True)
    longgap = longgap.reset_index(drop=True)
    return interp, longgap


def apply_physical_constraints(s: pd.Series) -> pd.Series:
    """步骤3：非负约束 + 翻斗分辨率重量化。"""
    s = s.clip(lower=0)
    s = (s / TIP_RESOLUTION).round() * TIP_RESOLUTION
    return s.round(1)


def sliding_window_smooth(s: pd.Series,
                          median_window=SMOOTH_MEDIAN_WINDOW,
                          mean_window=SMOOTH_MEAN_WINDOW) -> pd.Series:
    """步骤4：滑动窗口平滑 = 中值滤波(去残余尖峰) + 移动平均(降噪)。"""
    med = s.rolling(median_window, center=True, min_periods=1).median()
    smooth = med.rolling(mean_window, center=True, min_periods=1).mean()
    smooth = smooth.clip(lower=0)
    return (smooth / TIP_RESOLUTION).round() * TIP_RESOLUTION


def clean_pipeline(df_detected: pd.DataFrame, col="rainfall_mm") -> tuple[pd.DataFrame, dict]:
    """执行完整清洗管线。输入需已包含 'flag'/'is_anomaly' 列。"""
    df = df_detected.copy().reset_index(drop=True)
    log = {}

    # 步骤1 掩膜
    masked = mask_anomalies(df, col)
    log["掩膜为缺失的异常点数"] = int(df["is_anomaly"].sum())

    # 步骤2 插值
    interp, longgap = interpolate_series(masked, df["timestamp"], INTERP_LIMIT)
    log["插值填补点数"] = int(masked.isna().sum() - longgap.sum())
    log["长缺口保守置0点数"] = int(longgap.sum())

    # 长缺口保守置 0（无法臆造，标注低可信）
    interp = interp.fillna(0.0)

    # 步骤3 物理约束
    corrected = apply_physical_constraints(interp)

    # 步骤4 滑动窗口平滑（在 corrected 上）
    smoothed = sliding_window_smooth(corrected)

    df["rainfall_corrected"] = corrected
    df["rainfall_smoothed"] = smoothed
    df["filled_longgap"] = longgap.to_numpy()

    log["清洗后总降雨量(mm)"] = round(float(corrected[corrected > 0].sum()), 1)
    log["平滑后总降雨量(mm)"] = round(float(smoothed[smoothed > 0].sum()), 1)
    return df, log


if __name__ == "__main__":
    from data_quality import load_raw_rain, regularize_timeaxis
    from anomaly_detection import detect_anomalies
    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    det = detect_anomalies(reg)
    cleaned, log = clean_pipeline(det)
    print("清洗日志:")
    for k, v in log.items():
        print(f"  {k}: {v}")
    print("\n清洗后前 5 行:")
    print(cleaned[["timestamp", "rainfall_mm", "rainfall_corrected",
                   "rainfall_smoothed", "flag"]].head())
