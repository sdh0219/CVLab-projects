# -*- coding: utf-8 -*-
"""
warning_impact.py —— 清洗前后数据对下游预警阈值触发的影响分析。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import config as C


def _rain_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").clip(lower=0).fillna(0)


def _event_count(trigger: pd.Series) -> int:
    trigger = trigger.fillna(False).astype(bool)
    return int((trigger & ~trigger.shift(fill_value=False)).sum())


def _rolling_trigger(series: pd.Series, window: int, threshold: float) -> tuple[pd.Series, pd.Series]:
    roll = _rain_series(series).rolling(window, min_periods=1).sum()
    return roll, roll >= threshold


def run_warning_impact(cleaned: pd.DataFrame,
                       truth_rain: pd.Series,
                       save_path=C.WARNING_IMPACT_CSV) -> pd.DataFrame:
    methods = {
        "raw": cleaned["rainfall_mm"],
        "corrected": cleaned["rainfall_corrected"],
        "smoothed": cleaned["rainfall_smoothed"],
        "truth": truth_rain,
    }
    rows = []
    truth_triggers = {}
    for threshold_name, cfg in C.WARNING_THRESHOLDS.items():
        truth_roll, truth_hit = _rolling_trigger(methods["truth"], cfg["window"], cfg["threshold_mm"])
        truth_triggers[threshold_name] = truth_hit
        for method, series in methods.items():
            roll, hit = _rolling_trigger(series, cfg["window"], cfg["threshold_mm"])
            false_alarm = hit & ~truth_hit
            missed = ~hit & truth_hit
            rows.append({
                "threshold": threshold_name,
                "threshold_label": cfg["label"],
                "window_points": cfg["window"],
                "threshold_mm": cfg["threshold_mm"],
                "method": method,
                "trigger_samples": int(hit.sum()),
                "trigger_events": _event_count(hit),
                "false_alarm_samples": int(false_alarm.sum()),
                "false_alarm_events": _event_count(false_alarm),
                "missed_alarm_samples": int(missed.sum()),
                "missed_alarm_events": _event_count(missed),
                "max_rolling_rainfall": round(float(roll.max()), 2),
            })

    result = pd.DataFrame(rows)
    raw_false = (result[result["method"] == "raw"]
                 .set_index("threshold")["false_alarm_samples"])
    result["false_alarm_reduction_vs_raw_pct"] = np.nan
    for idx, row in result.iterrows():
        base = raw_false.get(row["threshold"], np.nan)
        if pd.notna(base) and base > 0:
            reduction = 100 * (base - row["false_alarm_samples"]) / base
            result.loc[idx, "false_alarm_reduction_vs_raw_pct"] = round(reduction, 2)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(save_path, index=False, encoding="utf-8-sig")
    plot_warning_impact(result)
    plot_warning_timeline(cleaned, truth_rain)
    write_warning_summary(result)
    return result


def plot_warning_impact(result: pd.DataFrame,
                        path=C.FIG_DIR / "fig11_warning_impact.png"):
    pivot = result.pivot_table(index="threshold", columns="method",
                               values="trigger_events", aggfunc="first")
    pivot = pivot.reindex(C.WARNING_THRESHOLDS.keys())
    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    pivot[["raw", "corrected", "smoothed", "truth"]].plot(
        kind="bar", ax=ax, color=["#d62728", "#2ca02c", "#ff7f0e", "#1f77b4"]
    )
    ax.set_title("图11  清洗前后预警触发事件数对比", fontsize=13, pad=10)
    ax.set_xlabel("预警阈值")
    ax.set_ylabel("触发事件数")
    ax.legend(["原始", "清洗后", "平滑后", "真值"], loc="upper right")
    ax.tick_params(axis="x", rotation=0)
    for container in ax.containers:
        ax.bar_label(container, fontsize=8, padding=2)
    C.style_axis(ax)
    C.finish_figure(fig, path, rect=[0.02, 0.03, 1, 0.95])
    plt.close(fig)


def plot_warning_timeline(cleaned: pd.DataFrame,
                          truth_rain: pd.Series,
                          path=C.FIG_DIR / "fig12_warning_timeline.png"):
    cfg = C.WARNING_THRESHOLDS["1h"]
    t = pd.to_datetime(cleaned["timestamp"])
    raw_roll, _ = _rolling_trigger(cleaned["rainfall_mm"], cfg["window"], cfg["threshold_mm"])
    cor_roll, _ = _rolling_trigger(cleaned["rainfall_corrected"], cfg["window"], cfg["threshold_mm"])
    smo_roll, _ = _rolling_trigger(cleaned["rainfall_smoothed"], cfg["window"], cfg["threshold_mm"])
    tru_roll, _ = _rolling_trigger(truth_rain, cfg["window"], cfg["threshold_mm"])

    center = int(tru_roll.idxmax()) if len(tru_roll) else 0
    lo = max(0, center - 180)
    hi = min(len(t), center + 180)
    sl = slice(lo, hi)

    fig, ax = plt.subplots(figsize=(13.8, 5.3))
    ax.plot(t[sl], raw_roll.iloc[sl], color="#d62728", lw=1.0, label="原始1h累计")
    ax.plot(t[sl], cor_roll.iloc[sl], color="#2ca02c", lw=1.5, label="清洗后1h累计")
    ax.plot(t[sl], smo_roll.iloc[sl], color="#ff7f0e", lw=1.0, label="平滑后1h累计")
    ax.plot(t[sl], tru_roll.iloc[sl], color="#1f77b4", lw=1.3, ls="--", label="真值1h累计")
    ax.axhline(cfg["threshold_mm"], color="black", lw=1.0, ls=":", label="1h阈值")
    ax.set_title("图12  预警时间线：清洗如何改变阈值触发", fontsize=13, pad=10)
    ax.set_xlabel("时间")
    ax.set_ylabel("1h累计雨量(mm)")
    ax.legend(loc="upper right", fontsize=9)
    C.style_axis(ax)
    C.format_date_axis(ax, t[sl], max_ticks=6, date_fmt="%m-%d\n%H:%M")
    C.finish_figure(fig, path, rect=[0.02, 0.03, 1, 0.95])
    plt.close(fig)


def write_warning_summary(result: pd.DataFrame,
                          path=C.WARNING_IMPACT_SUMMARY_MD):
    raw_false = int(result.loc[result["method"].eq("raw"), "false_alarm_samples"].sum())
    corrected_false = int(result.loc[result["method"].eq("corrected"), "false_alarm_samples"].sum())
    smoothed_missed = int(result.loc[result["method"].eq("smoothed"), "missed_alarm_samples"].sum())
    reduction = 100 * (raw_false - corrected_false) / raw_false if raw_false else 0.0
    lines = [
        "# 预警影响分析摘要",
        "",
        "本分析将原始污染数据、清洗后 corrected 数据、平滑后 smoothed 数据与真值序列分别输入",
        "10min、1h、3h、24h 累计雨量阈值，用于模拟暴雨、山洪和地质灾害监测预警中的阈值触发。",
        "",
        f"- 原始污染数据的误报样本数合计为 {raw_false}；",
        f"- corrected 数据的误报样本数合计为 {corrected_false}，相对原始数据减少约 {reduction:.1f}%；",
        f"- smoothed 数据的漏报样本数合计为 {smoothed_missed}，提示平滑可能削弱峰值，应作为辅助输出而非主结果；",
        "- 规则清洗的业务价值不只体现在 F1/MAE/RMSE，也体现在减少异常尖峰造成的错误预警、恢复累计雨量阈值判断的可信度。",
        "",
        "本结果仍属于课程实践验证，真实业务部署还需要结合本地预警标准、邻近站点、雷达估测和人工复核流程进行再校准。",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    from data_quality import load_raw_rain, regularize_timeaxis
    from anomaly_detection import detect_anomalies
    from cleaning import clean_pipeline

    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    det = detect_anomalies(reg)
    cleaned, _ = clean_pipeline(det)
    truth_df = pd.read_csv(C.TRUTH_CSV, parse_dates=["timestamp"])
    truth = truth_df.set_index("timestamp").reindex(pd.DatetimeIndex(cleaned["timestamp"]))["rainfall_mm"].reset_index(drop=True)
    res = run_warning_impact(cleaned, truth)
    print(res)
