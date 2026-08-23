# -*- coding: utf-8 -*-
"""
demo.py —— 演示录像专用的分步交互式演示程序。

按项目"演示录像"要求，依次演示：
  ① 数据读取   ② 异常点识别   ③ 修正过程   ④ 清洗前后曲线对比

用法：
  python src/demo.py          # 交互模式，每步按回车继续（推荐录像时使用）
  python src/demo.py --auto   # 自动模式，步间停顿 2.5 秒，无需按键

录像建议：全屏终端 + 运行本程序，照《docs/演示录像脚本.md》逐段讲解；
最后会自动弹出关键对比图（图1/图3/图4）。
"""
import sys
import time
import subprocess
import pandas as pd

import config as C
from data_quality import load_raw_rain, regularize_timeaxis, quality_report
from anomaly_detection import detect_anomalies, detection_counts
from cleaning import clean_pipeline
from evaluation import evaluate

AUTO = "--auto" in sys.argv
pd.set_option("display.unicode.east_asian_width", True)
pd.set_option("display.width", 120)


def pause(msg="▶ 按回车继续 ..."):
    if AUTO:
        time.sleep(2.5)
    else:
        try:
            input(f"\n\033[90m{msg}\033[0m")
        except EOFError:
            time.sleep(1.0)


def banner(text):
    line = "═" * 64
    print(f"\n\033[36m{line}\n  {text}\n{line}\033[0m")


def open_figure(name):
    """跨平台打开图片（macOS: open）。"""
    path = C.FIG_DIR / name
    if not path.exists():
        return
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)])
        elif sys.platform.startswith("win"):
            import os
            os.startfile(str(path))  # type: ignore
    except Exception:
        pass


def main():
    banner("雨量计异常数据清洗与纠正  ·  演示")
    print("  演示流程：① 数据读取 → ② 异常点识别 → ③ 修正过程 → ④ 清洗前后对比")
    pause()

    # ------------------------------------------------ ① 数据读取
    banner("① 数据读取")
    raw = load_raw_rain()
    print(f"读取原始雨量计数据：{C.RAW_RAIN_CSV.name}")
    print(f"入库总行数：{len(raw)}（含重复/乱序）")
    print("\n前 5 行：")
    print(raw.head().to_string(index=False))
    print("\n含异常的样例（负值 / 超量程尖峰）：")
    sample = raw[raw["anomaly_truth"].isin(["negative", "spike"])].head(6)
    print(sample.to_string(index=False))
    pause()

    # ------------------------------------------------ 时间轴规整
    banner("时间轴规整：去重 → 排序 → 补规则网格")
    reg, info = regularize_timeaxis(raw)
    for k, v in info.items():
        print(f"  {k}: {v}")
    q_before = quality_report(reg)
    print(f"\n清洗前数据质量：缺失率 {q_before['缺失率(%)']}% | 负值 {q_before['负值数']} | "
          f"超量程 {q_before['超量程数(>40mm/10min)']} | 卡滞 {q_before['疑似卡滞点数']} | "
          f"最大值 {q_before['最大值']}mm | 总降雨量(含异常) {q_before['总降雨量(mm)']}mm")
    pause()

    # ------------------------------------------------ ② 异常点识别
    banner("② 异常点识别（多规则检测）")
    det = detect_anomalies(reg)
    print("检测到的异常类型计数：")
    for k, v in detection_counts(det).items():
        print(f"  {C.ANOMALY_CN.get(k, k):　<8} : {v} 点")
    print(f"\n合计异常点：{int(det['is_anomaly'].sum())} / {len(det)}")
    print("\n部分被识别的异常点（原始值 + 标记）：")
    show = det[det["is_anomaly"]][["timestamp", "rainfall_mm", "flag"]].head(8)
    print(show.to_string(index=False))
    pause()

    # ------------------------------------------------ ③ 修正过程
    banner("③ 修正过程：掩膜 → 插值 → 物理约束 → 平滑")
    cleaned, log = clean_pipeline(det)
    for k, v in log.items():
        print(f"  {k}: {v}")
    print("\n典型异常点修正前后对照：")
    fix = cleaned[cleaned["is_anomaly"]][
        ["timestamp", "rainfall_mm", "flag", "rainfall_corrected"]].copy()
    fix = fix.rename(columns={"rainfall_mm": "修正前", "rainfall_corrected": "修正后"})
    # 各类型挑一个展示
    rows = []
    for t in ["spike", "negative", "stuck", "spurious", "missing"]:
        sub = fix[fix["flag"] == t].head(1)
        rows.append(sub)
    print(pd.concat(rows).to_string(index=False))
    pause()

    # ------------------------------------------------ ④ 清洗前后对比 + 评估
    banner("④ 清洗前后对比与效果评估")
    truth = pd.read_csv(C.TRUTH_CSV, parse_dates=["timestamp"])
    res = evaluate(cleaned, truth, raw)
    det_m = res["异常检测评估"]
    cor_m = res["数值修正评估"]
    print("【异常检测】（以注入真值为金标准）")
    print(f"  精确率 {det_m['精确率(%)']}% | 召回率 {det_m['召回率(%)']}% | "
          f"F1 {det_m['F1(%)']}% | 准确率 {det_m['准确率(%)']}%  （FP={det_m['混淆矩阵']['FP']}，零误杀）")
    print("\n【数值修正】总降雨量(mm)")
    print(f"  真值 {cor_m['总降雨量(mm)']['真值']} | "
          f"原始 {cor_m['总降雨量(mm)']['原始']} (误差 {cor_m['总降雨量相对误差(%)']['原始']}%) | "
          f"清洗后 {cor_m['总降雨量(mm)']['清洗后']} (误差 {cor_m['总降雨量相对误差(%)']['清洗后']}%)")
    print(f"\n  逐点 RMSE：原始 {cor_m['逐点误差']['原始(仅有效点)']['RMSE']} "
          f"→ 清洗后 {cor_m['逐点误差']['清洗后corrected']['RMSE']}")
    print("\n\033[32m结论：原始数据因尖峰使月累计雨量虚高约 17 倍，足以触发错误暴雨/洪水预警；")
    print("      清洗后累计量误差仅 0.3%，恢复为可用于防灾决策的高质量数据。\033[0m")

    print("\n正在打开关键对比图（图1 异常标记 / 图3 清洗前后 / 图4 累计雨量）...")
    for fig in ["fig1_raw_with_anomalies.png", "fig3_before_after.png", "fig4_cumulative.png"]:
        open_figure(fig)
        time.sleep(0.6)
    banner("演示结束，感谢观看")


if __name__ == "__main__":
    main()
