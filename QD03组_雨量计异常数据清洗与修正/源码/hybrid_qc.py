# -*- coding: utf-8 -*-
"""
hybrid_qc.py —— 规则 QC 与学习型 QC 的融合决策。

原则：
  - 规则法判定的严重异常直接修正；
  - 规则正常但学习型方法可疑时，只进入 manual_review，不直接删除峰值；
  - 规则和学习型同时命中时，作为高置信异常；
  - 对真实暴雨峰值进行保护，避免模型误判造成削峰。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C


def build_hybrid_qc(rule_df: pd.DataFrame,
                    ml_scores: pd.DataFrame | None = None,
                    save_path=C.HYBRID_QC_CSV) -> pd.DataFrame:
    df = rule_df.copy().reset_index(drop=True)
    out = pd.DataFrame({"timestamp": pd.to_datetime(df["timestamp"])})
    out["rule_anomaly_label"] = df["is_anomaly"].fillna(False).astype(int)
    out["rule_anomaly_type"] = df["flag"].fillna("")

    if ml_scores is not None:
        ml = ml_scores.copy()
        keep = [
            "timestamp", "if_anomaly_score", "if_anomaly_label",
            "lstm_reconstruction_error", "lstm_anomaly_label",
        ]
        keep = [c for c in keep if c in ml.columns]
        out = out.merge(ml[keep], on="timestamp", how="left")

    for col in ["if_anomaly_label", "lstm_anomaly_label"]:
        if col not in out.columns:
            out[col] = 0
        out[col] = out[col].fillna(0).astype(int)

    rule = out["rule_anomaly_label"].astype(bool)
    if_hit = out["if_anomaly_label"].astype(bool)
    lstm_hit = out["lstm_anomaly_label"].astype(bool)
    ml_hit = if_hit | lstm_hit
    raw = pd.to_numeric(df["rainfall_mm"], errors="coerce")
    protected_peak = (~rule) & raw.ge(C.RAIN_PLAUSIBLE_PER_INTERVAL).fillna(False)

    out["hybrid_anomaly_label"] = 0
    out["hybrid_anomaly_type"] = "normal"
    out["hybrid_confidence"] = 0.98
    out["final_decision"] = "keep"
    out["anomaly_source"] = "none"

    # 规则法命中：保持可解释主线，直接修正。
    out.loc[rule, "hybrid_anomaly_label"] = 1
    out.loc[rule, "hybrid_anomaly_type"] = out.loc[rule, "rule_anomaly_type"]
    out.loc[rule, "hybrid_confidence"] = 0.86
    out.loc[rule, "final_decision"] = "correct"
    out.loc[rule, "anomaly_source"] = "rule"

    # 学习型方法单独命中：保留值，只提示复核。
    ml_only = (~rule) & ml_hit
    out.loc[ml_only, "hybrid_anomaly_label"] = 1
    out.loc[ml_only, "hybrid_anomaly_type"] = "ml_suspicious"
    out.loc[ml_only, "hybrid_confidence"] = 0.62
    out.loc[ml_only, "final_decision"] = "manual_review"
    out.loc[ml_only & if_hit & ~lstm_hit, "anomaly_source"] = "isolation_forest"
    out.loc[ml_only & lstm_hit & ~if_hit, "anomaly_source"] = "lstm_ae"
    out.loc[ml_only & lstm_hit & if_hit, "anomaly_source"] = "hybrid"

    # 规则 + 学习型同时命中：高置信异常。
    both = rule & ml_hit
    out.loc[both, "hybrid_confidence"] = 0.95
    out.loc[both, "anomaly_source"] = "hybrid"

    # 保护真实暴雨峰值：模型单独判异常时只复核，不改值。
    out.loc[protected_peak & ml_only, "hybrid_anomaly_type"] = "protected_peak_review"
    out.loc[protected_peak & ml_only, "hybrid_confidence"] = 0.58
    out.loc[protected_peak & ml_only, "final_decision"] = "manual_review"

    if "filled_longgap" in df.columns:
        longgap = df["filled_longgap"].fillna(False).astype(bool)
        out.loc[longgap, "hybrid_anomaly_type"] = "long_gap_low_confidence"
        out.loc[longgap, "hybrid_confidence"] = 0.45
        out.loc[longgap, "final_decision"] = "manual_review"

    save_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(save_path, index=False, encoding="utf-8-sig")
    return out


if __name__ == "__main__":
    from data_quality import load_raw_rain, regularize_timeaxis
    from anomaly_detection import detect_anomalies

    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    det = detect_anomalies(reg)
    hybrid = build_hybrid_qc(det)
    print(hybrid["final_decision"].value_counts())
