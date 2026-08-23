# -*- coding: utf-8 -*-
"""
ablation.py —— 规则清洗管线消融实验。

评估各条规则对检测 F1 与累计雨量误差的贡献，并比较 corrected 与
smoothed 作为最终输出时的差异。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import config as C
from anomaly_detection import detect_statistical_spikes, detect_spurious_tips
from cleaning import clean_pipeline
from data_quality import detect_stuck_runs
from evaluation import detection_metrics


_PRIORITY = {"missing": 5, "spike": 4, "negative": 3, "stuck": 2, "spurious": 1, "": 0}
VARIANT_LABELS = {
    "full rule pipeline": "完整\n规则",
    "no MAD spike detection": "无MAD\n尖峰",
    "no stuck detection": "无卡滞\n检测",
    "no spurious tip detection": "无虚假\n翻斗",
    "no physical upper-bound check": "无物理\n上限",
    "no smoothing": "不平滑",
    "corrected only": "corrected\n输出",
    "smoothed output": "smoothed\n输出",
}


def _assign(flags: np.ndarray, mask: np.ndarray, label: str):
    for i in np.where(mask)[0]:
        if _PRIORITY[label] > _PRIORITY[flags[i]]:
            flags[i] = label


def detect_with_options(df: pd.DataFrame,
                        use_mad: bool = True,
                        use_stuck: bool = True,
                        use_spurious: bool = True,
                        use_upper_bound: bool = True,
                        col: str = "rainfall_mm") -> pd.DataFrame:
    out = df.copy()
    s = out[col]
    flags = np.array([""] * len(out), dtype=object)
    _assign(flags, s.isna().to_numpy(), "missing")
    _assign(flags, (s < 0).to_numpy(), "negative")
    if use_upper_bound:
        _assign(flags, (s > C.RAIN_MAX_PER_INTERVAL).to_numpy(), "spike")
    if use_mad:
        _assign(flags, detect_statistical_spikes(s), "spike")
    if use_stuck:
        _assign(flags, detect_stuck_runs(s, C.STUCK_MIN_REPEAT), "stuck")
    if use_spurious:
        _assign(flags, detect_spurious_tips(s), "spurious")
    out["flag"] = flags
    out["is_anomaly"] = out["flag"] != ""
    return out


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


def _series_errors(series: pd.Series, truth: pd.Series) -> tuple[float, float, float]:
    pred = series.to_numpy(dtype=float)
    truth_v = truth.to_numpy(dtype=float)
    diff = pred - truth_v
    mae = float(np.nanmean(np.abs(diff)))
    rmse = float(np.sqrt(np.nanmean(diff ** 2)))
    total_truth = float(np.nansum(truth_v[truth_v > 0]))
    total_pred = float(np.nansum(pred[pred > 0]))
    total_err = 100 * (total_pred - total_truth) / total_truth if total_truth else np.nan
    return round(mae, 4), round(rmse, 4), round(total_err, 2)


def run_ablation(reg: pd.DataFrame,
                 truth_df: pd.DataFrame,
                 raw_labels: pd.DataFrame,
                 save_path=C.ABLATION_RESULTS_CSV) -> pd.DataFrame:
    idx = pd.DatetimeIndex(reg["timestamp"])
    labels = _truth_labels(raw_labels, idx)
    truth = _truth_rain(truth_df, idx)

    variants = [
        ("full rule pipeline", "none", dict(), "rainfall_corrected"),
        ("no MAD spike detection", "MAD spike", dict(use_mad=False), "rainfall_corrected"),
        ("no stuck detection", "stuck", dict(use_stuck=False), "rainfall_corrected"),
        ("no spurious tip detection", "spurious tip", dict(use_spurious=False), "rainfall_corrected"),
        ("no physical upper-bound check", "upper bound", dict(use_upper_bound=False), "rainfall_corrected"),
        ("no smoothing", "smoothing", dict(), "rainfall_corrected"),
        ("corrected only", "output choice", dict(), "rainfall_corrected"),
        ("smoothed output", "output choice", dict(), "rainfall_smoothed"),
    ]

    rows = []
    for name, disabled, kwargs, final_col in variants:
        det = detect_with_options(reg, **kwargs)
        cleaned, _ = clean_pipeline(det)
        det_m = detection_metrics(cleaned["flag"], labels)
        mae, rmse, total_err = _series_errors(cleaned[final_col], truth)
        cm = det_m["混淆矩阵"]
        rows.append({
            "variant": name,
            "disabled_component": disabled,
            "final_output": final_col.replace("rainfall_", ""),
            "precision": det_m["精确率(%)"],
            "recall": det_m["召回率(%)"],
            "f1": det_m["F1(%)"],
            "accuracy": det_m["准确率(%)"],
            "fp": cm["FP"],
            "fn": cm["FN"],
            "mae": mae,
            "rmse": rmse,
            "total_rainfall_error_pct": total_err,
            "anomaly_count": int(cleaned["is_anomaly"].sum()),
        })

    result = pd.DataFrame(rows)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(save_path, index=False, encoding="utf-8-sig")
    plot_ablation_f1(result)
    plot_ablation_rainfall_error(result)
    return result


def plot_ablation_f1(result: pd.DataFrame,
                     path=C.FIG_DIR / "fig9_ablation_f1.png"):
    labels = [VARIANT_LABELS.get(v, v) for v in result["variant"]]
    fig, ax = plt.subplots(figsize=(12.2, 5.2))
    bars = ax.bar(labels, result["f1"], color="#4472c4")
    ax.set_ylabel("F1 (%)")
    ax.set_xlabel("消融变体")
    ax.set_title("图9  规则组件消融：异常检测 F1", fontsize=13, pad=10)
    ax.set_ylim(0, max(100, float(result["f1"].max()) + 5))
    ax.tick_params(axis="x", labelsize=9)
    C.add_bar_labels(ax, bars, fmt="{:.1f}", dy=3, fontsize=8.5)
    C.style_axis(ax)
    C.finish_figure(fig, path, rect=[0.02, 0.03, 1, 0.95])
    plt.close(fig)


def plot_ablation_rainfall_error(result: pd.DataFrame,
                                 path=C.FIG_DIR / "fig10_ablation_rainfall_error.png"):
    labels = [VARIANT_LABELS.get(v, v) for v in result["variant"]]
    fig, ax = plt.subplots(figsize=(12.2, 5.2))
    bars = ax.bar(labels, result["total_rainfall_error_pct"], color="#70ad47")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("累计雨量误差 (%)")
    ax.set_xlabel("消融变体")
    ax.set_title("图10  规则组件消融：累计雨量误差", fontsize=13, pad=10)
    ax.tick_params(axis="x", labelsize=9)
    C.add_bar_labels(ax, bars, fmt="{:.2f}", dy=3, fontsize=8.5)
    C.style_axis(ax)
    C.finish_figure(fig, path, rect=[0.02, 0.03, 1, 0.95])
    plt.close(fig)


if __name__ == "__main__":
    from data_quality import load_raw_rain, regularize_timeaxis

    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    truth = pd.read_csv(C.TRUTH_CSV, parse_dates=["timestamp"])
    res = run_ablation(reg, truth, raw)
    print(res)
