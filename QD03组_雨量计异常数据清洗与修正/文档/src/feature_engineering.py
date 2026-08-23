# -*- coding: utf-8 -*-
"""
feature_engineering.py —— 学习型异常检测的时序特征工程。

本模块只构造特征，不改变原始数据与规则清洗结果。水位、湿度、温度等
辅助字段如果存在则自动纳入；不存在时跳过，保证真实数据迁移时不报错。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C


OPTIONAL_SENSOR_COLUMNS = [
    "water_level", "water_level_m",
    "humidity", "humidity_pct",
    "temperature", "temperature_c",
]


def _run_lengths(mask: pd.Series) -> pd.Series:
    """计算连续 True 的长度；False 位置为 0。"""
    mask = mask.fillna(False).astype(bool)
    groups = (mask != mask.shift(fill_value=False)).cumsum()
    lengths = mask.groupby(groups).transform("sum")
    return lengths.where(mask, 0).astype(int)


def _same_value_lengths(s: pd.Series) -> pd.Series:
    """计算连续相同值长度，NaN 作为断点处理。"""
    comparable = s.where(~s.isna(), object())
    groups = (comparable != comparable.shift()).cumsum()
    return s.groupby(groups).transform("size").astype(int)


def build_features(df: pd.DataFrame,
                   rainfall_col: str = "rainfall_mm",
                   timestamp_col: str = "timestamp",
                   save_summary: bool = True) -> pd.DataFrame:
    """构造学习型检测特征。

    Parameters
    ----------
    df:
        至少包含 timestamp 与雨量列；可选包含水位/湿度/温度等列。
    rainfall_col:
        原始或待检测雨量列名。
    timestamp_col:
        时间戳列名。
    save_summary:
        是否写出 `output/reports/feature_summary.csv`。
    """
    if timestamp_col not in df.columns:
        raise ValueError(f"缺少时间戳字段: {timestamp_col}")
    if rainfall_col not in df.columns:
        raise ValueError(f"缺少雨量字段: {rainfall_col}")

    out = pd.DataFrame()
    out["timestamp"] = pd.to_datetime(df[timestamp_col])
    rain = pd.to_numeric(df[rainfall_col], errors="coerce")
    out["rainfall_10min"] = rain

    out["roll_30min_sum"] = rain.rolling(3, min_periods=1).sum()
    out["roll_1h_sum"] = rain.rolling(6, min_periods=1).sum()
    out["roll_3h_sum"] = rain.rolling(18, min_periods=1).sum()
    out["roll_1h_mean"] = rain.rolling(6, min_periods=1).mean()
    out["roll_1h_max"] = rain.rolling(6, min_periods=1).max()
    out["diff_1"] = rain.diff().fillna(0)
    out["is_zero"] = (rain.fillna(-9999) == 0).astype(int)
    out["consecutive_zero_len"] = _run_lengths(rain.fillna(-9999) == 0)
    out["consecutive_same_value_len"] = _same_value_lengths(rain)

    ts = out["timestamp"]
    hour = ts.dt.hour + ts.dt.minute / 60.0
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    out["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    doy = ts.dt.dayofyear.astype(float)
    out["dayofyear_sin"] = np.sin(2 * np.pi * doy / 366.0)
    out["dayofyear_cos"] = np.cos(2 * np.pi * doy / 366.0)

    for col in OPTIONAL_SENSOR_COLUMNS:
        if col in df.columns:
            out[col] = pd.to_numeric(df[col], errors="coerce")
            out[f"{col}_diff_1"] = out[col].diff().fillna(0)
            out[f"{col}_roll_1h_mean"] = out[col].rolling(6, min_periods=1).mean()

    if save_summary:
        save_feature_summary(out)
    return out


def save_feature_summary(features: pd.DataFrame,
                         path=C.FEATURE_SUMMARY_CSV) -> pd.DataFrame:
    """保存特征统计摘要，便于报告说明与复核。"""
    numeric = features.select_dtypes(include=[np.number])
    if numeric.empty:
        summary = pd.DataFrame(columns=["feature", "missing_rate"])
    else:
        summary = numeric.describe().T.reset_index().rename(columns={"index": "feature"})
        summary["missing_rate"] = [
            round(float(features[col].isna().mean()), 4) for col in summary["feature"]
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(path, index=False, encoding="utf-8-sig")
    return summary


if __name__ == "__main__":
    from data_quality import load_raw_rain, regularize_timeaxis

    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    feats = build_features(reg)
    print(f"特征矩阵: {feats.shape}")
    print(f"特征摘要已保存: {C.FEATURE_SUMMARY_CSV}")
