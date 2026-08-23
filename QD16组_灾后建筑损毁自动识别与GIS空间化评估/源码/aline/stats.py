# -*- coding: utf-8 -*-
"""
损毁统计：把像素级预测聚合为逐栋建筑级结果。
流程：连通域分析 -> 每栋建筑取众数损毁等级 -> 按等级统计数量与面积 -> 出 CSV + 柱状图。
用法:  python stats.py
"""
import os, glob, csv
import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

import config as C

# ---- 中文字体自适应：有 CJK 字体用中文标签，否则退回英文，避免方块乱码 ----
_CJK_LABELS = ["背景", "完好", "轻微损毁", "严重损毁", "完全损毁"]
_EN_LABELS = ["background", "no-damage", "minor", "major", "destroyed"]


def _pick_font():
    for name in ["Noto Sans CJK SC", "Noto Sans CJK JP", "WenQuanYi Zen Hei",
                 "Microsoft YaHei", "SimHei", "Source Han Sans SC"]:
        try:
            font_manager.findfont(name, fallback_to_default=False)
            return name
        except Exception:
            continue
    return None


_FONT = _pick_font()
if _FONT:
    plt.rcParams["font.sans-serif"] = [_FONT]
    plt.rcParams["axes.unicode_minus"] = False
    LABELS = _CJK_LABELS
else:
    LABELS = _EN_LABELS

# 柱状图配色（RGB 0~1），与等级对应
BAR_COLORS = [(0, 0.7, 0), (0.86, 0.86, 0), (1, 0.47, 0), (0.9, 0, 0)]  # 完好/轻/重/毁


def analyze_one(dmg_mask, min_area_px=15):
    """对单张损毁掩膜做连通域级聚合。
    返回 {cls: {'count': n, 'area_px': px}}，cls in 1..4。"""
    result = {c: {"count": 0, "area_px": 0} for c in range(1, C.NUM_DAMAGE)}
    building = (dmg_mask > 0).astype(np.uint8)
    n, labels = cv2.connectedComponents(building, connectivity=8)
    for comp in range(1, n):
        comp_mask = labels == comp
        area = int(comp_mask.sum())
        if area < min_area_px:
            continue
        vals = dmg_mask[comp_mask]
        vals = vals[vals > 0]
        if vals.size == 0:
            continue
        cls = int(np.bincount(vals).argmax())  # 众数等级
        result[cls]["count"] += 1
        result[cls]["area_px"] += area
    return result


def main():
    npys = sorted(glob.glob(os.path.join(C.PRED_DIR, "*_dmg.npy")))
    if not npys:
        print("未找到预测结果，请先运行 inference.py")
        return

    total = {c: {"count": 0, "area_px": 0} for c in range(1, C.NUM_DAMAGE)}
    per_image_rows = []
    for path in npys:
        base = os.path.basename(path).replace("_dmg.npy", "")
        dmg = np.load(path)
        r = analyze_one(dmg)
        for c in range(1, C.NUM_DAMAGE):
            total[c]["count"] += r[c]["count"]
            total[c]["area_px"] += r[c]["area_px"]
            per_image_rows.append([base, LABELS[c], r[c]["count"],
                                   round(r[c]["area_px"] * C.GSD_M ** 2, 2)])

    # ---- 写 CSV ----
    csv_path = os.path.join(C.STATS_DIR, "damage_stats.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["image", "damage_level", "building_count", "area_m2"])
        w.writerows(per_image_rows)
        w.writerow([])
        w.writerow(["==汇总==", "", "", ""])
        for c in range(1, C.NUM_DAMAGE):
            area_m2 = round(total[c]["area_px"] * C.GSD_M ** 2, 2)
            w.writerow(["TOTAL", LABELS[c], total[c]["count"], area_m2])

    # ---- 柱状图：数量 + 面积 双子图 ----
    levels = LABELS[1:]
    counts = [total[c]["count"] for c in range(1, C.NUM_DAMAGE)]
    areas = [round(total[c]["area_px"] * C.GSD_M ** 2, 1) for c in range(1, C.NUM_DAMAGE)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.bar(levels, counts, color=BAR_COLORS)
    ax1.set_title("各损毁等级建筑数量" if _FONT else "Building count by damage level")
    ax1.set_ylabel("数量(栋)" if _FONT else "count")
    for i, v in enumerate(counts):
        ax1.text(i, v, str(v), ha="center", va="bottom")

    ax2.bar(levels, areas, color=BAR_COLORS)
    ax2.set_title("各损毁等级损毁面积" if _FONT else "Damaged area by level")
    ax2.set_ylabel("面积(m²)" if _FONT else "area (m2)")
    for i, v in enumerate(areas):
        ax2.text(i, v, str(v), ha="center", va="bottom")

    fig.tight_layout()
    chart_path = os.path.join(C.STATS_DIR, "damage_barchart.png")
    fig.savefig(chart_path, dpi=150)
    plt.close(fig)

    # ---- 控制台汇总 ----
    print("==== 损毁统计汇总 ====")
    for c in range(1, C.NUM_DAMAGE):
        area_m2 = total[c]["area_px"] * C.GSD_M ** 2
        print(f"  {LABELS[c]:>6}: {total[c]['count']:>3} 栋, 面积 {area_m2:>10.1f} m²")
    print(f"CSV  -> {csv_path}")
    print(f"柱状图 -> {chart_path}  (中文字体: {_FONT or '未找到, 已用英文'})")


if __name__ == "__main__":
    main()
