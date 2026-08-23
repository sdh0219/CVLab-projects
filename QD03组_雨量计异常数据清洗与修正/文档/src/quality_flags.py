# -*- coding: utf-8 -*-
"""
quality_flags.py —— 逐点质量标识与可信度输出。

质量标识面向监测业务：不仅给出清洗后的雨量，还保留原始值、修正值、
平滑值、异常来源、最终处理建议和可信度分数。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import config as C


FLAG_NAMES = {
    0: "正常",
    1: "可疑但保留",
    2: "异常已修正",
    3: "长缺口低可信",
    4: "不可用",
}


def _first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def build_quality_flags(cleaned: pd.DataFrame,
                        hybrid: pd.DataFrame | None = None,
                        save_path=C.CLEANED_QUALITY_CSV) -> pd.DataFrame:
    """生成逐点质量标识表。

    Parameters
    ----------
    cleaned:
        规则清洗后的 DataFrame，需包含 timestamp、rainfall_mm、flag、
        rainfall_corrected、rainfall_smoothed、filled_longgap。
    hybrid:
        可选的混合决策表，包含 hybrid_*、final_decision、anomaly_source 等列。
    """
    df = cleaned.copy().reset_index(drop=True)
    if hybrid is not None:
        h = hybrid.copy()
        keep_cols = [
            "timestamp", "hybrid_anomaly_label", "hybrid_anomaly_type",
            "hybrid_confidence", "final_decision", "anomaly_source",
        ]
        keep_cols = [c for c in keep_cols if c in h.columns]
        df = df.merge(h[keep_cols], on="timestamp", how="left")

    raw_col = _first_existing(df, ["rainfall_mm", "rainfall_raw_mm"])
    if raw_col is None:
        raise ValueError("质量标识需要 rainfall_mm 或 rainfall_raw_mm 字段")

    out = pd.DataFrame()
    out["timestamp"] = pd.to_datetime(df["timestamp"])
    out["station_id"] = df["station_id"] if "station_id" in df.columns else "RG-001"
    out["raw_rainfall"] = df[raw_col]
    out["corrected_rainfall"] = df["rainfall_corrected"]
    out["smoothed_rainfall"] = df["rainfall_smoothed"]
    out["anomaly_type"] = df.get("flag", "").fillna("")

    rule_anomaly = out["anomaly_type"] != ""
    longgap = df.get("filled_longgap", False)
    if not isinstance(longgap, pd.Series):
        longgap = pd.Series([False] * len(df))
    longgap = longgap.fillna(False).astype(bool)

    final_decision = df.get("final_decision")
    default_decision = pd.Series(np.where(rule_anomaly, "correct", "keep"), index=df.index)
    if final_decision is None:
        final_decision = default_decision
    else:
        final_decision = final_decision.fillna(default_decision)

    anomaly_source = df.get("anomaly_source")
    default_source = pd.Series(np.where(rule_anomaly, "rule", "none"), index=df.index)
    if anomaly_source is None:
        anomaly_source = default_source
    else:
        anomaly_source = anomaly_source.fillna(default_source)

    quality_flag = np.zeros(len(df), dtype=int)
    quality_flag[rule_anomaly.to_numpy()] = 2
    quality_flag[final_decision.eq("manual_review").to_numpy()] = 1
    quality_flag[longgap.to_numpy()] = 3
    quality_flag[final_decision.eq("unusable").to_numpy()] = 4

    confidence = np.full(len(df), 0.98, dtype=float)
    confidence[quality_flag == 1] = 0.65
    confidence[quality_flag == 2] = 0.86
    confidence[quality_flag == 3] = 0.45
    confidence[quality_flag == 4] = 0.10
    if "hybrid_confidence" in df.columns:
        hc = pd.to_numeric(df["hybrid_confidence"], errors="coerce")
        confidence = np.where(hc.notna(), np.minimum(confidence, hc.fillna(1.0)), confidence)

    out["quality_flag"] = quality_flag
    out["quality_flag_name"] = out["quality_flag"].map(FLAG_NAMES)
    out["confidence_score"] = np.round(confidence, 3)
    out["anomaly_source"] = anomaly_source
    out["final_decision"] = final_decision

    save_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(save_path, index=False, encoding="utf-8-sig")
    plot_quality_flag_distribution(out)
    return out


def plot_quality_flag_distribution(qc: pd.DataFrame,
                                   path=C.FIG_DIR / "fig_quality_flags_distribution.png"):
    """质量标识分布图，作为课程报告中的业务化输出补充。"""
    counts = qc["quality_flag_name"].value_counts().reindex(FLAG_NAMES.values(), fill_value=0)
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    colors = ["#2ca02c", "#ffbf00", "#4472c4", "#9467bd", "#d62728"]
    bars = ax.bar(counts.index, counts.values, color=colors)
    ax.set_title("质量标识分布", fontsize=13, pad=10)
    ax.set_ylabel("样本点数")
    ax.set_xlabel("质量标识")
    ax.tick_params(axis="x", labelsize=10)
    C.add_bar_labels(ax, bars)
    C.style_axis(ax)
    C.finish_figure(fig, path, rect=[0.02, 0.03, 1, 0.95])
    plt.close(fig)


if __name__ == "__main__":
    from data_quality import load_raw_rain, regularize_timeaxis
    from anomaly_detection import detect_anomalies
    from cleaning import clean_pipeline

    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    det = detect_anomalies(reg)
    cleaned, _ = clean_pipeline(det)
    qc = build_quality_flags(cleaned)
    print(qc.head())
    print(f"质量标识已保存: {C.CLEANED_QUALITY_CSV}")
