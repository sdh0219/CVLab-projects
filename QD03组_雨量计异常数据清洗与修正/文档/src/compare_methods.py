# -*- coding: utf-8 -*-
"""
compare_methods.py —— 规则法、学习型方法与组合方法对比实验。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import config as C
from cleaning import clean_pipeline
from evaluation import detection_metrics, correction_metrics


METHOD_LABELS = {
    "规则法": "规则法",
    "Isolation Forest": "Isolation\nForest",
    "LSTM-AE": "LSTM-AE",
    "规则法 + Isolation Forest": "规则法+\nIF",
    "规则法 + LSTM-AE": "规则法+\nLSTM-AE",
    "规则法 + IF + LSTM-AE": "规则法+\nIF+LSTM",
}


def _truth_labels(raw_labels: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.Series:
    return (raw_labels.copy()
            .drop_duplicates(subset=["timestamp"], keep="first")
            .set_index("timestamp")["anomaly_truth"]
            .reindex(idx)
            .reset_index(drop=True))


def _truth_rain(truth_df: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.Series:
    return (truth_df.copy()
            .set_index("timestamp")["rainfall_mm"]
            .reindex(idx)
            .reset_index(drop=True))


def _method_frame(base: pd.DataFrame, flags: pd.Series | np.ndarray) -> pd.DataFrame:
    det = base.copy()
    det["flag"] = pd.Series(flags).fillna("").astype(str).to_numpy()
    det["is_anomaly"] = det["flag"] != ""
    return det


def _enabled_status(scores: pd.DataFrame | None, col: str) -> str:
    if scores is None or col not in scores.columns or scores.empty:
        return "skipped: ml scores not available"
    return str(scores[col].iloc[0])


def _evaluate_method(name: str,
                     status: str,
                     det: pd.DataFrame | None,
                     truth_labels: pd.Series,
                     truth_rain: pd.Series) -> dict:
    row = {
        "method": name,
        "status": status,
        "precision": np.nan,
        "recall": np.nan,
        "f1": np.nan,
        "accuracy": np.nan,
        "fp": np.nan,
        "fn": np.nan,
        "total_rainfall_error_pct": np.nan,
        "mae": np.nan,
        "rmse": np.nan,
        "anomaly_count": np.nan,
    }
    if status != "enabled" or det is None:
        return row

    cleaned, _ = clean_pipeline(det)
    det_m = detection_metrics(cleaned["flag"], truth_labels)
    cor_m = correction_metrics(
        cleaned["rainfall_mm"],
        cleaned["rainfall_corrected"],
        cleaned["rainfall_smoothed"],
        truth_rain,
    )
    cm = det_m["混淆矩阵"]
    row.update({
        "precision": det_m["精确率(%)"],
        "recall": det_m["召回率(%)"],
        "f1": det_m["F1(%)"],
        "accuracy": det_m["准确率(%)"],
        "fp": cm["FP"],
        "fn": cm["FN"],
        "total_rainfall_error_pct": cor_m["总降雨量相对误差(%)"]["清洗后"],
        "mae": cor_m["逐点误差"]["清洗后corrected"]["MAE"],
        "rmse": cor_m["逐点误差"]["清洗后corrected"]["RMSE"],
        "anomaly_count": int(cleaned["is_anomaly"].sum()),
    })
    return row


def run_method_comparison(reg: pd.DataFrame,
                          rule_det: pd.DataFrame,
                          ml_scores: pd.DataFrame | None,
                          truth_df: pd.DataFrame,
                          raw_labels: pd.DataFrame,
                          save_path=C.METHOD_COMPARISON_CSV) -> pd.DataFrame:
    """运行方法对比实验并输出 CSV/PNG。"""
    idx = pd.DatetimeIndex(rule_det["timestamp"])
    labels = _truth_labels(raw_labels, idx)
    truth = _truth_rain(truth_df, idx)
    base = reg.copy().reset_index(drop=True)

    if_status = _enabled_status(ml_scores, "if_status")
    lstm_status = _enabled_status(ml_scores, "lstm_status")
    if_enabled = if_status == "enabled"
    lstm_enabled = lstm_status == "enabled"

    rule_flags = rule_det["flag"].fillna("")
    empty = pd.Series([""] * len(base))

    rows = []
    methods: list[tuple[str, str, pd.DataFrame | None]] = []
    methods.append(("规则法", "enabled", rule_det))

    if if_enabled:
        if_flags = pd.Series(np.where(ml_scores["if_anomaly_label"].astype(int) == 1,
                                      "iforest", ""))
        methods.append(("Isolation Forest", "enabled", _method_frame(base, if_flags)))
    else:
        if_flags = empty.copy()
        methods.append(("Isolation Forest", if_status, None))

    if lstm_enabled:
        lstm_flags = pd.Series(np.where(ml_scores["lstm_anomaly_label"].astype(int) == 1,
                                        "lstm_ae", ""))
        methods.append(("LSTM-AE", "enabled", _method_frame(base, lstm_flags)))
    else:
        lstm_flags = empty.copy()
        methods.append(("LSTM-AE", lstm_status, None))

    if if_enabled:
        combo = rule_flags.where(rule_flags != "", if_flags)
        methods.append(("规则法 + Isolation Forest", "enabled", _method_frame(base, combo)))
    else:
        methods.append(("规则法 + Isolation Forest", if_status, None))

    if lstm_enabled:
        combo = rule_flags.where(rule_flags != "", lstm_flags)
        methods.append(("规则法 + LSTM-AE", "enabled", _method_frame(base, combo)))
    else:
        methods.append(("规则法 + LSTM-AE", lstm_status, None))

    if if_enabled and lstm_enabled:
        combo_ml = if_flags.where(if_flags != "", lstm_flags)
        combo_all = rule_flags.where(rule_flags != "", combo_ml)
        methods.append(("规则法 + IF + LSTM-AE", "enabled", _method_frame(base, combo_all)))
    else:
        missing = []
        if not if_enabled:
            missing.append("IF")
        if not lstm_enabled:
            missing.append("LSTM-AE")
        methods.append(("规则法 + IF + LSTM-AE",
                        "skipped: " + "/".join(missing) + " unavailable", None))

    for name, status, det in methods:
        rows.append(_evaluate_method(name, status, det, labels, truth))

    result = pd.DataFrame(rows)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(save_path, index=False, encoding="utf-8-sig")
    plot_method_comparison(result)
    plot_ml_scores(rule_det, ml_scores)
    return result


def plot_method_comparison(result: pd.DataFrame,
                           path=C.FIG_DIR / "fig7_method_comparison.png"):
    enabled = result[result["status"] == "enabled"].copy()
    if enabled.empty:
        enabled = result.copy()
    labels = [METHOD_LABELS.get(name, name.replace(" + ", "+\n")) for name in enabled["method"]]
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.4))

    bars = axes[0].bar(labels, enabled["f1"].fillna(0), color="#4472c4")
    axes[0].set_ylabel("F1 (%)")
    axes[0].set_title("(a) 异常检测 F1", fontsize=12, pad=8)
    axes[0].set_ylim(0, max(100, float(enabled["f1"].fillna(0).max()) + 5))
    axes[0].tick_params(axis="x", labelsize=9)
    C.add_bar_labels(axes[0], bars, fmt="{:.1f}", dy=3, fontsize=8.5)

    bars = axes[1].bar(labels, enabled["total_rainfall_error_pct"].fillna(0),
                       color="#70ad47")
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].set_ylabel("清洗后总降雨量误差 (%)")
    axes[1].set_title("(b) 累计雨量误差", fontsize=12, pad=8)
    axes[1].tick_params(axis="x", labelsize=9)
    C.add_bar_labels(axes[1], bars, fmt="{:.2f}", dy=3, fontsize=8.5)

    C.style_axes(axes)
    C.set_suptitle(fig, "图7  方法对比：检测指标与防灾累计量误差", y=0.965)
    C.finish_figure(fig, path, rect=[0, 0.02, 1, 0.93], w_pad=2.0)
    plt.close(fig)


def plot_ml_scores(rule_det: pd.DataFrame,
                   ml_scores: pd.DataFrame | None,
                   path=C.FIG_DIR / "fig8_ml_anomaly_scores.png"):
    t = pd.to_datetime(rule_det["timestamp"])
    raw = rule_det["rainfall_mm"]
    fig, axes = plt.subplots(3, 1, figsize=(14, 8.4), sharex=True)

    axes[0].plot(t, raw, color="#888888", lw=0.8, label="原始雨量")
    axes[0].scatter(t[rule_det["is_anomaly"]], raw[rule_det["is_anomaly"]].fillna(0),
                    s=16, color="#d62728", label="规则异常")
    axes[0].set_ylabel("10min雨量(mm)")
    axes[0].set_title("(a) 原始雨量与规则异常", fontsize=12, pad=8)
    axes[0].legend(loc="upper right", fontsize=9)

    if ml_scores is not None and "if_anomaly_score" in ml_scores.columns:
        axes[1].plot(t, ml_scores["if_anomaly_score"], color="#4472c4", lw=0.8)
        hit = ml_scores["if_anomaly_label"].fillna(0).astype(int) == 1
        axes[1].scatter(t[hit], ml_scores.loc[hit, "if_anomaly_score"],
                        s=14, color="#d62728")
    else:
        axes[1].text(0.5, 0.5, "Isolation Forest skipped",
                     ha="center", va="center", transform=axes[1].transAxes)
    axes[1].set_ylabel("IF score")
    axes[1].set_title("(b) Isolation Forest 异常分数", fontsize=12, pad=8)

    if (ml_scores is not None and "lstm_reconstruction_error" in ml_scores.columns
            and not ml_scores["lstm_reconstruction_error"].isna().all()):
        axes[2].plot(t, ml_scores["lstm_reconstruction_error"],
                     color="#70ad47", lw=0.8)
        threshold = ml_scores["lstm_threshold"].dropna()
        if not threshold.empty:
            axes[2].axhline(float(threshold.iloc[0]), color="#d62728",
                            ls="--", lw=1.0, label="阈值")
        hit = ml_scores["lstm_anomaly_label"].fillna(0).astype(int) == 1
        axes[2].scatter(t[hit], ml_scores.loc[hit, "lstm_reconstruction_error"],
                        s=14, color="#d62728")
        axes[2].legend(loc="upper right", fontsize=9)
    else:
        axes[2].text(0.5, 0.5, "torch not available or sample too small, LSTM-AE skipped",
                     ha="center", va="center", transform=axes[2].transAxes)
    axes[2].set_ylabel("LSTM error")
    axes[2].set_title("(c) LSTM-AE 重构误差", fontsize=12, pad=8)
    axes[2].set_xlabel(C.time_axis_label(t))
    C.format_date_axis(axes[2], t)

    C.style_axes(axes)
    C.set_suptitle(fig, "图8  学习型异常分数时间序列", y=0.965)
    C.finish_figure(fig, path, rect=[0, 0.01, 1, 0.94], h_pad=1.2)
    plt.close(fig)


if __name__ == "__main__":
    from data_quality import load_raw_rain, regularize_timeaxis
    from anomaly_detection import detect_anomalies
    from feature_engineering import build_features
    from ml_anomaly import run_ml_anomaly

    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    rule = detect_anomalies(reg)
    features = build_features(reg)
    scores, _ = run_ml_anomaly(features, rule)
    truth = pd.read_csv(C.TRUTH_CSV, parse_dates=["timestamp"])
    comp = run_method_comparison(reg, rule, scores, truth, raw)
    print(comp)
