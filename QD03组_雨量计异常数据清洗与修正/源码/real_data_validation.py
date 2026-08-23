# -*- coding: utf-8 -*-
"""
real_data_validation.py —— 真实/类真实无真值数据迁移验证。

若 data/real/raw_real_rainfall.csv 存在，则读取用户真实 CSV；
若不存在，则基于现有多传感器样例生成 simulated-realistic 展示数据，
并在报告中明确标注，不计算 precision/recall/F1。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import config as C
from anomaly_detection import detect_anomalies, detection_counts
from cleaning import clean_pipeline
from data_quality import quality_report, regularize_timeaxis
from quality_flags import build_quality_flags, FLAG_NAMES


def infer_time_frequency(df: pd.DataFrame) -> str:
    """真实数据频率可能不是 10min，按时间戳间隔自动推断。"""
    ts = pd.to_datetime(df["timestamp"]).sort_values().drop_duplicates()
    inferred = pd.infer_freq(ts)
    if inferred:
        return inferred
    diffs = ts.diff().dropna()
    if diffs.empty:
        return C.FREQ
    minutes = max(1, int(round(diffs.median().total_seconds() / 60)))
    return f"{minutes}min"


def interval_minutes(freq: str) -> int:
    """把频率字符串转为分钟数，用于真实数据阈值适配。"""
    try:
        delta = pd.to_timedelta(freq)
        minutes = int(round(delta.total_seconds() / 60))
        return max(1, minutes)
    except Exception:
        digits = "".join(ch for ch in str(freq) if ch.isdigit())
        return int(digits) if digits else 10


def load_or_make_real_like_data() -> tuple[pd.DataFrame, str]:
    if C.REAL_RAW_CSV.exists():
        df = pd.read_csv(C.REAL_RAW_CSV, parse_dates=["timestamp"])
        missing = {"timestamp", "rainfall_mm"} - set(df.columns)
        if missing:
            raise ValueError(f"真实 CSV 缺少必需字段: {sorted(missing)}")
        if "source_type" in df.columns:
            source_values = df["source_type"].dropna().astype(str)
            if not source_values.empty:
                source = source_values.iloc[0]
                if source in {"simulated-realistic", "real-public-3rww"}:
                    return df, source
        return df, "real-user-provided"

    if C.RAW_MULTI_CSV.exists():
        df = pd.read_csv(C.RAW_MULTI_CSV, parse_dates=["timestamp"])
        keep = [
            "timestamp", "station_id", "rainfall_mm",
            "water_level_m", "temperature_c", "humidity_pct",
        ]
        keep = [c for c in keep if c in df.columns]
        df = df[keep].copy()
    else:
        rng = np.random.default_rng(C.RANDOM_SEED)
        ts = pd.date_range("2024-07-01", periods=7 * 24 * 6, freq=C.FREQ)
        rainfall = rng.gamma(0.5, 1.0, len(ts))
        rainfall[rng.random(len(ts)) < 0.86] = 0
        df = pd.DataFrame({
            "timestamp": ts,
            "station_id": "REAL-LIKE-001",
            "rainfall_mm": np.round(rainfall, 1),
        })
        df.loc[rng.choice(len(df), 8, replace=False), "rainfall_mm"] = np.nan
        df.loc[rng.choice(len(df), 3, replace=False), "rainfall_mm"] = 999.0

    df["source_type"] = "simulated-realistic"
    C.REAL_RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    # 保存一份展示用输入，便于复现实验，但明确标注为 simulated-realistic。
    df.to_csv(C.REAL_RAW_CSV, index=False, encoding="utf-8-sig")
    return df, "simulated-realistic"


def run_real_data_validation(save_path=C.REAL_PROCESSED_CSV) -> tuple[pd.DataFrame, dict]:
    raw, source_type = load_or_make_real_like_data()
    freq = infer_time_frequency(raw)
    minutes = interval_minutes(freq)
    threshold_scale = minutes / 10.0
    reg, reg_info = regularize_timeaxis(raw, freq=freq)
    before = quality_report(reg)
    det = detect_anomalies(
        reg,
        max_per_interval=C.RAIN_MAX_PER_INTERVAL * threshold_scale,
        plausible_threshold=C.RAIN_PLAUSIBLE_PER_INTERVAL * threshold_scale,
    )
    cleaned, clean_log = clean_pipeline(det)
    after_df = cleaned[["timestamp"]].copy()
    after_df["rainfall_mm"] = cleaned["rainfall_corrected"]
    after = quality_report(after_df)
    qc = build_quality_flags(cleaned, save_path=save_path)
    qc["source_type"] = source_type
    qc.to_csv(save_path, index=False, encoding="utf-8-sig")

    summary = {
        "source_type": source_type,
        "station_id": str(raw["station_id"].dropna().iloc[0]) if "station_id" in raw.columns and raw["station_id"].notna().any() else "",
        "source_name": str(raw["source_name"].dropna().iloc[0]) if "source_name" in raw.columns and raw["source_name"].notna().any() else "",
        "source_url": str(raw["source_url"].dropna().iloc[0]) if "source_url" in raw.columns and raw["source_url"].notna().any() else "",
        "original_unit": str(raw["original_unit"].dropna().iloc[0]) if "original_unit" in raw.columns and raw["original_unit"].notna().any() else "",
        "inferred_frequency": freq,
        "interval_minutes": minutes,
        "scaled_physical_upper_bound_mm": C.RAIN_MAX_PER_INTERVAL * threshold_scale,
        "rows_after_regularization": int(len(reg)),
        "timeaxis": reg_info,
        "quality_before": before,
        "quality_after_corrected": after,
        "anomaly_counts": detection_counts(det),
        "cleaning_log": clean_log,
        "quality_flag_distribution": qc["quality_flag_name"].value_counts().to_dict(),
    }
    plot_real_data_qc(cleaned, qc, source_type)
    write_real_validation_summary(summary)
    return qc, summary


def plot_real_data_qc(cleaned: pd.DataFrame,
                      qc: pd.DataFrame,
                      source_type: str,
                      path=C.FIG_DIR / "fig13_real_data_qc.png"):
    t = pd.to_datetime(cleaned["timestamp"])
    freq = infer_time_frequency(cleaned)
    fig, axes = plt.subplots(2, 1, figsize=(13.8, 8.2), sharex=False)

    axes[0].plot(t, cleaned["rainfall_mm"], color="#bbbbbb", lw=0.8, label="原始雨量")
    axes[0].plot(t, cleaned["rainfall_corrected"], color="#2ca02c", lw=1.2, label="QC后雨量")
    hit = cleaned["is_anomaly"].fillna(False)
    axes[0].scatter(t[hit], cleaned.loc[hit, "rainfall_mm"].fillna(0),
                    s=18, color="#d62728", label="规则异常")
    axes[0].set_title(f"图13  真实/类真实数据迁移验证 ({source_type})", fontsize=13, pad=10)
    axes[0].set_ylabel(f"{freq}雨量(mm)")
    axes[0].set_xlabel(C.time_axis_label(t))
    axes[0].legend(loc="upper right")
    C.format_date_axis(axes[0], t)

    counts = qc["quality_flag_name"].value_counts().reindex(FLAG_NAMES.values(), fill_value=0)
    bars = axes[1].bar(counts.index, counts.values,
                       color=["#2ca02c", "#ffbf00", "#4472c4", "#9467bd", "#d62728"])
    axes[1].set_title("质量标识分布", fontsize=12, pad=8)
    axes[1].set_ylabel("样本点数")
    axes[1].set_xlabel("质量标识")
    axes[1].tick_params(axis="x", labelsize=9)
    C.add_bar_labels(axes[1], bars)

    C.style_axes(axes)
    C.finish_figure(fig, path, rect=[0, 0.02, 1, 0.97], h_pad=1.6)
    plt.close(fig)


def write_real_validation_summary(summary: dict,
                                  path=C.REAL_VALIDATION_SUMMARY_MD):
    source = summary["source_type"]
    before = summary["quality_before"]
    after = summary["quality_after_corrected"]
    counts = summary["anomaly_counts"]
    lines = [
        "# 真实/类真实数据迁移验证摘要",
        "",
        f"- 数据来源标识：**{source}**。",
        f"- 站点：**{summary.get('station_id', '') or '未提供'}**。",
        f"- 推断时间分辨率：**{summary.get('inferred_frequency', C.FREQ)}**。",
        f"- 本项目按该分辨率缩放物理上限阈值，本次上限为 **{summary.get('scaled_physical_upper_bound_mm', C.RAIN_MAX_PER_INTERVAL):.1f} mm/interval**。",
        "- 本部分不使用逐点真值标签，因此不计算 precision、recall、F1。",
        "- 目的在于展示规则 QC、质量标识和报告输出能否迁移到无真值场景。",
    ]
    if source == "real-public-3rww":
        lines.extend([
            f"- 在线公开数据源：{summary.get('source_name', '3 Rivers Wet Weather')}。",
            f"- 原始单位：{summary.get('original_unit', 'inch per interval')}，已换算为 `rainfall_mm`。",
            "- 来源页面说明 Rain Gauge CSV 为 ALCOSAN QA/QC 后发布的数据。",
            f"- 下载地址：{summary.get('source_url', '')}",
        ])
    lines.extend([
        "",
        "## 数据质量变化",
        "",
        f"- 规整后样本数：{summary['rows_after_regularization']}；",
        f"- 清洗前缺失率：{before['缺失率(%)']}%，清洗后缺失率：{after['缺失率(%)']}%；",
        f"- 清洗前最大值：{before['最大值']} mm，清洗后最大值：{after['最大值']} mm；",
        f"- 清洗前累计雨量：{before['总降雨量(mm)']} mm，清洗后累计雨量：{after['总降雨量(mm)']} mm；",
        f"- 规则可疑点计数：{counts}。",
        "",
        "## 说明",
        "",
        "若数据来源为 simulated-realistic，表示当前目录没有用户提供的真实 CSV，程序使用项目样例生成类真实流程展示数据。",
        "若数据来源为 real-public-3rww，表示程序使用 3 Rivers Wet Weather 公开雨量计下载数据；该数据没有本项目逐点异常真值，因此只做无真值 QC 迁移验证。",
        "真实公开数据来自官方 QA/QC 后 CSV，本项目检出的 spurious/stuck 仅表示在课程规则下建议复核的可疑点，不等同于官方数据错误。",
        "真实业务迁移仍需结合站点元数据、当地极端降雨阈值和人工复核流程重新校准。",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    qc_df, info = run_real_data_validation()
    print(info)
    print(f"真实/类真实 QC 输出: {C.REAL_PROCESSED_CSV}")
