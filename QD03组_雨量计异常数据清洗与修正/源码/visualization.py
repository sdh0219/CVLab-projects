# -*- coding: utf-8 -*-
"""
visualization.py —— 生成全部分析图表（报告与 PPT 共用）。

产出图（保存到 output/figures/）：
  fig1_raw_with_anomalies.png  原始序列 + 异常点彩色标记（全量 + 放大双面板）
  fig2_quality_dashboard.png   数据质量统计仪表板（完整率、异常构成、清洗前后）
  fig3_before_after.png        清洗前后对比（暴雨事件放大，原始/清洗/真值三线）
  fig4_cumulative.png          累计雨量对比（原始 vs 清洗 vs 真值）——防灾关键图
  fig5_smoothing_zoom.png      滑动窗口平滑效果（暴雨峰值放大）
  fig6_detection_metrics.png   异常检测评估（混淆矩阵 + 分类型召回 + P/R/F1）
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from config import (
    setup_matplotlib, FIG_DIR, ANOMALY_COLORS, ANOMALY_CN,
    RAIN_MAX_PER_INTERVAL, style_axes, format_date_axis, time_axis_label,
    add_bar_labels, set_suptitle, finish_figure,
)

setup_matplotlib()


def _anomaly_legend():
    return [Patch(facecolor=ANOMALY_COLORS[k], label=ANOMALY_CN[k]) for k in ANOMALY_COLORS]


def fig_raw_with_anomalies(cleaned: pd.DataFrame, save=True):
    """图1：原始序列 + 异常点标记（上：全量含尖峰；下：放大到正常量级）。"""
    t = cleaned["timestamp"]
    raw = cleaned["rainfall_mm"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7.2), sharex=True)

    # 上：全量（含 999 尖峰），用以暴露超量程异常
    ax1.plot(t, raw, color="#bbbbbb", lw=0.8, zorder=1, label="原始雨量")
    for k, c in ANOMALY_COLORS.items():
        if k == "missing":
            continue
        m = cleaned["flag"] == k
        ax1.scatter(t[m], raw[m], s=22, color=c, zorder=3, label=ANOMALY_CN[k])
    ax1.set_title("(a) 全量视图：超量程尖峰清晰可见", fontsize=12, pad=8)
    ax1.set_ylabel("10min 雨量 (mm)")
    ax1.legend(loc="upper right", ncol=3, fontsize=9)

    # 下：放大到 [-6, 25]，看清正常降雨、负值、卡滞、虚假翻斗
    ax2.plot(t, raw, color="#888888", lw=0.9, zorder=1, label="原始雨量")
    for k, c in ANOMALY_COLORS.items():
        if k == "missing":
            continue
        m = cleaned["flag"] == k
        ax2.scatter(t[m], raw[m], s=22, color=c, zorder=3)
    # 缺失点用底部灰色竖线标出
    miss = cleaned["flag"] == "missing"
    ax2.scatter(t[miss], np.full(miss.sum(), -5.0), s=8, color=ANOMALY_COLORS["missing"],
                marker="|", label="缺失值(置底显示)")
    ax2.axhline(0, color="k", lw=0.6)
    ax2.set_ylim(-6, 25)
    ax2.set_title("(b) 正常量级放大：负值、卡滞、虚假翻斗和缺失", fontsize=12, pad=8)
    ax2.set_ylabel("10min 雨量 (mm)")
    ax2.set_xlabel(time_axis_label(t))
    ax2.legend(loc="upper right", ncol=2, fontsize=9)
    style_axes((ax1, ax2))
    format_date_axis(ax2, t)
    set_suptitle(fig, "图1  原始雨量计数据与异常点标记", y=0.975)
    fig.tight_layout(rect=[0, 0.01, 1, 0.94], h_pad=1.6)
    if save:
        fig.savefig(FIG_DIR / "fig1_raw_with_anomalies.png")
    plt.close(fig)


def fig_quality_dashboard(cleaned: pd.DataFrame, q_before: dict, q_after: dict, save=True):
    """图2：数据质量仪表板。"""
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.2))

    # (a) 异常类型计数
    vc = cleaned.loc[cleaned["is_anomaly"], "flag"].value_counts()
    types = [k for k in ANOMALY_COLORS if k in vc.index]
    counts = [int(vc[k]) for k in types]
    colors = [ANOMALY_COLORS[k] for k in types]
    ax = axes[0, 0]
    bars = ax.bar([ANOMALY_CN[k] for k in types], counts, color=colors)
    ax.set_title("(a) 检出异常类型分布", fontsize=12, pad=8)
    ax.set_ylabel("点数")
    add_bar_labels(ax, bars)

    # (b) 异常构成饼图
    ax = axes[0, 1]
    ax.pie(counts, labels=[ANOMALY_CN[k] for k in types], colors=colors,
           autopct="%1.1f%%", startangle=90, textprops={"fontsize": 9})
    ax.set_title("(b) 异常构成占比", fontsize=12, pad=8)

    # (c) 完整率/有效率：清洗前后
    ax = axes[1, 0]
    cats = ["完整率(%)", "有效降雨\n可用率(%)"]
    n = q_before["总样本数"]
    before_vals = [q_before["完整率(%)"],
                   round(100 * (n - q_before["缺失值数"] - q_before["负值数"]
                                - q_before["超量程数(>40mm/10min)"] - q_before["疑似卡滞点数"]) / n, 2)]
    after_vals = [100.0, round(100 * (n - int(cleaned["filled_longgap"].sum())) / n, 2)]
    x = np.arange(len(cats))
    w = 0.35
    ax.bar(x - w/2, before_vals, w, label="清洗前", color="#d62728")
    ax.bar(x + w/2, after_vals, w, label="清洗后", color="#2ca02c")
    ax.set_xticks(x); ax.set_xticklabels(cats)
    ax.set_ylim(0, 108); ax.set_ylabel("百分比 (%)")
    ax.set_title("(c) 数据可用性：清洗前 vs 清洗后", fontsize=12, pad=8)
    ax.legend()
    for i, (bv, av) in enumerate(zip(before_vals, after_vals)):
        ax.text(i - w/2, bv + 1, f"{bv}", ha="center", fontsize=9)
        ax.text(i + w/2, av + 1, f"{av}", ha="center", fontsize=9)

    # (d) 关键统计量对比表
    ax = axes[1, 1]
    ax.axis("off")
    rows = [
        ["指标", "清洗前", "清洗后/真值"],
        ["总样本数", f'{q_before["总样本数"]}', f'{q_after["总样本数"]}'],
        ["缺失值数", f'{q_before["缺失值数"]}', f'{q_after["缺失值数"]}'],
        ["负值数", f'{q_before["负值数"]}', f'{q_after["负值数"]}'],
        ["超量程数", f'{q_before["超量程数(>40mm/10min)"]}', f'{q_after["超量程数(>40mm/10min)"]}'],
        ["最大值(mm)", f'{q_before["最大值"]}', f'{q_after["最大值"]}'],
        ["总降雨量(mm)", f'{q_before["总降雨量(mm)"]}', f'{q_after["总降雨量(mm)"]}'],
    ]
    tbl = ax.table(cellText=rows, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(10); tbl.scale(1, 1.6)
    for j in range(3):
        tbl[0, j].set_facecolor("#4472c4")
        tbl[0, j].set_text_props(color="w", fontweight="bold")
    ax.set_title("(d) 关键质量指标对比", fontsize=12, pad=18)

    style_axes((axes[0, 0], axes[1, 0]))
    set_suptitle(fig, "图2  雨量计数据质量统计仪表板", y=0.975)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    if save:
        fig.savefig(FIG_DIR / "fig2_quality_dashboard.png")
    plt.close(fig)


def _pick_storm_window(truth_rain: pd.Series, t: pd.Series, half=90):
    """选取真值降雨最强的时段中心，返回放大窗口的起止索引。"""
    center = int(truth_rain.rolling(13, center=True, min_periods=1).sum().idxmax())
    lo = max(0, center - half)
    hi = min(len(t), center + half)
    return lo, hi


def fig_before_after(cleaned: pd.DataFrame, truth: pd.Series, save=True):
    """图3：清洗前后对比（暴雨事件放大）。"""
    t = cleaned["timestamp"]
    lo, hi = _pick_storm_window(truth, t)
    sl = slice(lo, hi)

    fig, ax = plt.subplots(figsize=(13.5, 5.4))
    ax.plot(t[sl], cleaned["rainfall_mm"].iloc[sl], color="#d62728", lw=1.0,
            marker="x", ms=4, alpha=0.7, label="原始(含异常)")
    ax.plot(t[sl], cleaned["rainfall_corrected"].iloc[sl], color="#2ca02c", lw=1.8,
            marker="o", ms=3, label="清洗后(corrected)")
    ax.plot(t[sl], truth.iloc[sl], color="#1f77b4", lw=1.2, ls="--",
            label="真值(truth)")
    # 标出该窗口内的异常点
    win = cleaned.iloc[sl]
    for k, c in ANOMALY_COLORS.items():
        m = win["flag"] == k
        if m.any():
            ax.scatter(win["timestamp"][m], win["rainfall_mm"][m].fillna(0),
                       s=55, edgecolor="k", facecolor=c, zorder=5, label=f"异常:{ANOMALY_CN[k]}")
    ax.set_title("图3  清洗前后对比：暴雨事件放大", fontsize=13, pad=10)
    ax.set_xlabel("时间"); ax.set_ylabel("10min 雨量 (mm)")
    ax.legend(loc="upper right", fontsize=9, ncol=2)
    style_axes(ax)
    format_date_axis(ax, t[sl], max_ticks=6, date_fmt="%m-%d\n%H:%M")
    fig.tight_layout()
    if save:
        fig.savefig(FIG_DIR / "fig3_before_after.png")
    plt.close(fig)


def fig_cumulative(cleaned: pd.DataFrame, truth: pd.Series, save=True):
    """图4：累计雨量对比（防灾关键图）。原始尖峰使累计量灾难性偏大。"""
    t = cleaned["timestamp"]
    time_label = time_axis_label(t)
    raw_cum = cleaned["rainfall_mm"].clip(lower=0).fillna(0).cumsum()
    cor_cum = cleaned["rainfall_corrected"].cumsum()
    smo_cum = cleaned["rainfall_smoothed"].cumsum()
    truth_cum = truth.cumsum()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.2, 5.4))
    ax1.plot(t, raw_cum, color="#d62728", lw=1.6, label=f"原始 (末值 {raw_cum.iloc[-1]:.0f} mm)")
    ax1.plot(t, truth_cum, color="#1f77b4", lw=1.6, ls="--", label=f"真值 (末值 {truth_cum.iloc[-1]:.0f} mm)")
    ax1.set_title("(a) 原始累计量显著虚高", fontsize=12, fontweight="normal", pad=10)
    ax1.set_ylabel("累计雨量 (mm)"); ax1.set_xlabel(time_label)
    ax1.legend(loc="upper left", fontsize=9)

    ax2.plot(t, cor_cum, color="#2ca02c", lw=1.8, label=f"清洗后 (末值 {cor_cum.iloc[-1]:.1f} mm)")
    ax2.plot(t, smo_cum, color="#ff7f0e", lw=1.2, label=f"平滑后 (末值 {smo_cum.iloc[-1]:.1f} mm)")
    ax2.plot(t, truth_cum, color="#1f77b4", lw=1.6, ls="--", label=f"真值 (末值 {truth_cum.iloc[-1]:.1f} mm)")
    ax2.set_title("(b) 清洗后累计量接近真值", fontsize=12, fontweight="normal", pad=10)
    ax2.set_ylabel("累计雨量 (mm)"); ax2.set_xlabel(time_label)
    ax2.legend(loc="upper left", fontsize=9)

    for ax in (ax1, ax2):
        style_axes(ax)
        format_date_axis(ax, t)

    set_suptitle(fig, "图4  累计雨量对比：异常尖峰抬高累计量，清洗后回归真值", y=0.965)
    fig.tight_layout(rect=[0, 0.01, 1, 0.94], w_pad=2.6)
    if save:
        fig.savefig(FIG_DIR / "fig4_cumulative.png")
    plt.close(fig)


def fig_smoothing_zoom(cleaned: pd.DataFrame, truth: pd.Series, save=True):
    """图5：滑动窗口平滑效果（暴雨峰值放大）。"""
    t = cleaned["timestamp"]
    lo, hi = _pick_storm_window(truth, t, half=60)
    sl = slice(lo, hi)
    fig, ax = plt.subplots(figsize=(13.5, 5.2))
    ax.plot(t[sl], cleaned["rainfall_corrected"].iloc[sl], color="#2ca02c", lw=1.2,
            marker="o", ms=3, alpha=0.6, label="清洗后(未平滑)")
    ax.plot(t[sl], cleaned["rainfall_smoothed"].iloc[sl], color="#ff7f0e", lw=2.2,
            label="滑动窗口平滑后")
    ax.plot(t[sl], truth.iloc[sl], color="#1f77b4", lw=1.0, ls="--", label="真值")
    ax.set_title("图5  暴雨峰值放大：滑动窗口平滑效果", fontsize=13, pad=10)
    ax.set_xlabel("时间"); ax.set_ylabel("10min 雨量 (mm)")
    ax.legend(loc="upper right", fontsize=10)
    style_axes(ax)
    format_date_axis(ax, t[sl], max_ticks=6, date_fmt="%m-%d\n%H:%M")
    fig.tight_layout()
    if save:
        fig.savefig(FIG_DIR / "fig5_smoothing_zoom.png")
    plt.close(fig)


def fig_detection_metrics(eval_res: dict, save=True):
    """图6：异常检测评估（混淆矩阵 + 分类型召回 + 总体指标）。"""
    det = eval_res["异常检测评估"]
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.8))

    # (a) 混淆矩阵
    cm = det["混淆矩阵"]
    mat = np.array([[cm["TN"], cm["FP"]], [cm["FN"], cm["TP"]]])
    ax = axes[0]
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["预测正常", "预测异常"])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["实际正常", "实际异常"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(mat[i, j]), ha="center", va="center",
                    color="white" if mat[i, j] > mat.max()/2 else "black", fontsize=13, fontweight="bold")
    ax.set_title("(a) 混淆矩阵", fontsize=12, pad=8)
    ax.grid(False)

    # (b) 分类型召回率
    ax = axes[1]
    pt = det["分类型召回"]
    types = list(pt.keys())
    recalls = [pt[k]["召回率(%)"] for k in types]
    colors = [ANOMALY_COLORS[k] for k in types]
    bars = ax.bar([ANOMALY_CN[k] for k in types], recalls, color=colors)
    ax.set_ylim(0, 112); ax.set_ylabel("召回率 (%)")
    ax.set_title("(b) 各异常类型召回率", fontsize=12, pad=8)
    for b, r in zip(bars, recalls):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+1, f"{r}", ha="center", fontsize=9)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")

    # (c) 总体指标
    ax = axes[2]
    names = ["精确率", "召回率", "F1", "准确率"]
    vals = [det["精确率(%)"], det["召回率(%)"], det["F1(%)"], det["准确率(%)"]]
    bars = ax.barh(names, vals, color="#4472c4")
    ax.set_xlim(0, 108); ax.set_xlabel("百分比 (%)")
    ax.set_title("(c) 总体检测指标", fontsize=12, pad=8)
    for b, v in zip(bars, vals):
        ax.text(b.get_width()+1, b.get_y()+b.get_height()/2, f"{v}", va="center", fontsize=10)

    style_axes(axes)
    axes[0].grid(False)
    set_suptitle(fig, "图6  异常检测效果评估（以注入真值为金标准）", y=0.965)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    if save:
        fig.savefig(FIG_DIR / "fig6_detection_metrics.png")
    plt.close(fig)


def make_all_figures(cleaned, truth_rain, q_before, q_after, eval_res):
    fig_raw_with_anomalies(cleaned)
    fig_quality_dashboard(cleaned, q_before, q_after)
    fig_before_after(cleaned, truth_rain)
    fig_cumulative(cleaned, truth_rain)
    fig_smoothing_zoom(cleaned, truth_rain)
    fig_detection_metrics(eval_res)
    print(f"全部图表已保存到 {FIG_DIR}")
