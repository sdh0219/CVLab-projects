# -*- coding: utf-8 -*-
"""
anomaly_detection.py —— 雨量计异常检测（不依赖真值，纯数据驱动）。

检测策略（多规则融合，对应技术方案中的"清洗规则"）：

  规则A 物理范围检查 (range check)
      - 负值：rainfall < 0           -> 'negative'（降雨物理上不可能为负）
      - 超量程：rainfall > 硬上限     -> 'spike' （40mm/10min 物理不可能）

  规则B 统计离群检测 (robust outlier, 基于滚动中位数 + MAD)
      - 在滚动窗口内用稳健 Z 分数 (x-median)/(1.4826*MAD) 衡量偏离；
      - 仅当数值同时超过"可疑阈值"且为局部孤立跳变时才判为 'spike'，
        避免误杀真实的持续性暴雨峰值。

  规则C 传感器卡滞检测 (stuck)
      - 连续 >=N 个完全相同的【非零】读数 -> 'stuck'（翻斗卡死，干期连续 0 不算）。

  规则D 虚假翻斗检测 (spurious)
      - 干期中孤立出现的微量降雨(<=0.3mm，前后窗口全干) -> 'spurious'。

  规则E 缺失 (missing)
      - NaN 直接标记为 'missing'。

输出：在原 DataFrame 上新增 'flag' 列（'' 表示正常），以及 'is_anomaly' 布尔列。
当多规则命中同一点时，按优先级 missing>spike>negative>stuck>spurious 取最严重者。
"""
import numpy as np
import pandas as pd

from config import (
    RAIN_MAX_PER_INTERVAL, RAIN_PLAUSIBLE_PER_INTERVAL,
    ROLL_WINDOW, MAD_THRESHOLD, STUCK_MIN_REPEAT,
    SPURIOUS_WINDOW, SPURIOUS_MAX_TIP,
)
from data_quality import detect_stuck_runs

_PRIORITY = {"missing": 5, "spike": 4, "negative": 3, "stuck": 2, "spurious": 1, "": 0}


def _assign(flags: np.ndarray, mask: np.ndarray, label: str):
    """按优先级写入标签：仅当新标签比已有标签更严重时覆盖。"""
    for i in np.where(mask)[0]:
        if _PRIORITY[label] > _PRIORITY[flags[i]]:
            flags[i] = label


def detect_statistical_spikes(s: pd.Series,
                              plausible_threshold=RAIN_PLAUSIBLE_PER_INTERVAL) -> np.ndarray:
    """基于滚动中位数 + MAD 的稳健离群检测，返回布尔掩码。

    设计要点：
      - 降雨序列零值占比极高，全局统计无意义，故用【滚动窗口】局部统计；
      - MAD 为 0（窗口内多为同值）时退化，故附加"绝对量级"门槛，
        只把"既统计离群、又超过可疑量级、且明显高于近邻"的点判为尖峰，
        从而保护真实暴雨峰值不被误删。
    """
    v = s.to_numpy(dtype=float)
    n = len(v)
    med = s.rolling(ROLL_WINDOW, center=True, min_periods=3).median()
    # MAD = median(|x - median|)
    abs_dev = (s - med).abs()
    mad = abs_dev.rolling(ROLL_WINDOW, center=True, min_periods=3).median()
    robust_z = (s - med) / (1.4826 * mad.replace(0, np.nan))

    # 近邻最大值（前后各 2 点，排除自身）
    neigh_max = s.shift(1).rolling(5, center=True, min_periods=1).max()

    mask = (
        (robust_z.abs() > MAD_THRESHOLD)               # 统计上极端偏离
        & (s > plausible_threshold)                    # 量级达到可疑阈值
        & (s > 3 * neigh_max.fillna(0) + 1.0)          # 远高于近邻（孤立跳变）
    ).to_numpy()
    return np.nan_to_num(mask, nan=False).astype(bool)


def detect_spurious_tips(s: pd.Series, window=SPURIOUS_WINDOW,
                         max_tip=SPURIOUS_MAX_TIP) -> np.ndarray:
    """干期孤立微量降雨检测：value∈(0, max_tip] 且前后 window 个点全为 0。"""
    v = s.to_numpy(dtype=float)
    n = len(v)
    mask = np.zeros(n, dtype=bool)
    for i in range(n):
        x = v[i]
        if np.isnan(x) or x <= 0 or x > max_tip:
            continue
        lo = max(0, i - window)
        hi = min(n, i + window + 1)
        neigh = np.delete(v[lo:hi], i - lo)
        neigh = neigh[~np.isnan(neigh)]
        if neigh.size > 0 and np.all(neigh == 0):
            mask[i] = True
    return mask


def detect_anomalies(df: pd.DataFrame, col="rainfall_mm",
                     max_per_interval=RAIN_MAX_PER_INTERVAL,
                     plausible_threshold=RAIN_PLAUSIBLE_PER_INTERVAL) -> pd.DataFrame:
    """对雨量列执行多规则异常检测，返回带 'flag' / 'is_anomaly' 的副本。"""
    df = df.copy()
    s = df[col]
    n = len(s)
    flags = np.array([""] * n, dtype=object)

    # E 缺失
    _assign(flags, s.isna().to_numpy(), "missing")
    # A 负值
    _assign(flags, (s < 0).to_numpy(), "negative")
    # A 超量程（硬上限）
    _assign(flags, (s > max_per_interval).to_numpy(), "spike")
    # B 统计离群尖峰
    _assign(flags, detect_statistical_spikes(s, plausible_threshold), "spike")
    # C 卡滞
    _assign(flags, detect_stuck_runs(s, STUCK_MIN_REPEAT), "stuck")
    # D 虚假翻斗
    _assign(flags, detect_spurious_tips(s), "spurious")

    df["flag"] = flags
    df["is_anomaly"] = df["flag"] != ""
    return df


def detection_counts(df: pd.DataFrame) -> dict:
    vc = df.loc[df["is_anomaly"], "flag"].value_counts().to_dict()
    return {k: int(v) for k, v in vc.items()}


if __name__ == "__main__":
    from data_quality import load_raw_rain, regularize_timeaxis
    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    det = detect_anomalies(reg)
    print("检测到的异常计数:", detection_counts(det))
    print("异常总数:", int(det["is_anomaly"].sum()))
