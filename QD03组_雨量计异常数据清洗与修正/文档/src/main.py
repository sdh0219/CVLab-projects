# -*- coding: utf-8 -*-
"""
main.py —— 雨量计异常数据清洗与纠正：一键主流程。

依次执行：
  1. （如缺数据）生成数据集
  2. 读取原始数据 -> 时间轴规整 -> 清洗前质量统计
  3. 多规则异常检测
  4. 异常修正（掩膜 -> 插值 -> 物理约束 -> 滑动窗口平滑）
  5. 清洗后质量统计
  6. 对照真值评估（检测 P/R/F1、修正 MAE/RMSE、总降雨量误差）
  7. 保存：清洗后数据、异常标记明细、质量与评估报告、汇总
  8. 生成全部图表

运行：python src/main.py
"""
import json
import argparse
import pandas as pd

import config as C
from data_quality import (load_raw_rain, regularize_timeaxis,
                          quality_report, save_report)
from anomaly_detection import detect_anomalies, detection_counts
from cleaning import clean_pipeline
from evaluation import evaluate
from visualization import make_all_figures


def ensure_data_exists():
    """确保合成数据存在，供各模式复用。"""
    if not C.RAW_RAIN_CSV.exists():
        print("[data] 未发现原始数据，正在生成 ...")
        import generate_data
        generate_data.main()


def load_regularized_inputs():
    ensure_data_exists()
    raw = load_raw_rain()
    reg, reg_info = regularize_timeaxis(raw)
    return raw, reg, reg_info


def load_feature_frame(reg: pd.DataFrame) -> pd.DataFrame:
    """在雨量规整表上合并可选多传感器字段，用于学习型特征。"""
    frame = reg.copy()
    if C.RAW_MULTI_CSV.exists():
        multi = pd.read_csv(C.RAW_MULTI_CSV, parse_dates=["timestamp"])
        multi = multi.drop_duplicates(subset=["timestamp"], keep="first").set_index("timestamp")
        idx = pd.DatetimeIndex(frame["timestamp"])
        for col in ["water_level", "water_level_m", "humidity", "humidity_pct",
                    "temperature", "temperature_c"]:
            if col in multi.columns and col not in frame.columns:
                frame[col] = multi.reindex(idx)[col].reset_index(drop=True)
    return frame


def run():
    C.setup_matplotlib()
    print("=" * 64)
    print(" 雨量计异常数据清洗与纠正 —— 主流程")
    print("=" * 64)

    # 1. 确保数据存在
    if not C.RAW_RAIN_CSV.exists():
        print("[1] 未发现原始数据，正在生成 ...")
        import generate_data
        generate_data.main()
    else:
        print("[1] 已发现原始数据，跳过生成。")

    # 2. 读取 + 规整 + 清洗前质量
    raw = load_raw_rain()
    print(f"[2] 读取原始入库数据：{len(raw)} 行")
    reg, reg_info = regularize_timeaxis(raw)
    print(f"    时间轴规整：去重 {reg_info['重复时间戳行数']} 行，"
          f"乱序={reg_info['时间戳是否乱序']}，规整后 {reg_info['规整后行数(规则网格)']} 行")
    q_before = quality_report(reg)
    q_before["_时间轴规整"] = reg_info
    save_report(q_before, C.QUALITY_BEFORE_JSON)
    print(f"    清洗前：缺失率 {q_before['缺失率(%)']}%，"
          f"负值 {q_before['负值数']}，超量程 {q_before['超量程数(>40mm/10min)']}，"
          f"卡滞 {q_before['疑似卡滞点数']}，总降雨量(含异常) {q_before['总降雨量(mm)']}mm")

    # 3. 异常检测
    det = detect_anomalies(reg)
    print(f"[3] 异常检测：{detection_counts(det)}，合计 {int(det['is_anomaly'].sum())} 点")

    # 4. 清洗修正
    cleaned, clean_log = clean_pipeline(det)
    print(f"[4] 清洗修正：插值 {clean_log['插值填补点数']} 点，"
          f"长缺口保守置0 {clean_log['长缺口保守置0点数']} 点，"
          f"清洗后总降雨量 {clean_log['清洗后总降雨量(mm)']}mm")

    # 5. 清洗后质量（基于 corrected 列）
    after = cleaned[["timestamp"]].copy()
    after["rainfall_mm"] = cleaned["rainfall_corrected"]
    q_after = quality_report(after)
    save_report(q_after, C.QUALITY_AFTER_JSON)
    print(f"[5] 清洗后：缺失率 {q_after['缺失率(%)']}%，负值 {q_after['负值数']}，"
          f"超量程 {q_after['超量程数(>40mm/10min)']}，最大值 {q_after['最大值']}mm")

    # 6. 评估
    truth_df = pd.read_csv(C.TRUTH_CSV, parse_dates=["timestamp"])
    eval_res = evaluate(cleaned, truth_df, raw)
    save_report(eval_res, C.EVAL_JSON)
    det_m = eval_res["异常检测评估"]
    cor_m = eval_res["数值修正评估"]
    print(f"[6] 评估：检测 精确率 {det_m['精确率(%)']}% / 召回率 {det_m['召回率(%)']}% "
          f"/ F1 {det_m['F1(%)']}%")
    print(f"    总降雨量 真值 {cor_m['总降雨量(mm)']['真值']}mm，"
          f"原始 {cor_m['总降雨量(mm)']['原始']}mm（误差 {cor_m['总降雨量相对误差(%)']['原始']}%），"
          f"清洗后 {cor_m['总降雨量(mm)']['清洗后']}mm（误差 {cor_m['总降雨量相对误差(%)']['清洗后']}%）")

    # 7. 保存清洗后数据与标记明细
    out_cols = ["timestamp", "station_id", "rainfall_mm", "flag",
                "rainfall_corrected", "rainfall_smoothed", "filled_longgap"]
    out = cleaned.copy()
    if "station_id" not in out.columns:
        out["station_id"] = "RG-001"
    out[out_cols].rename(columns={
        "rainfall_mm": "rainfall_raw_mm",
    }).to_csv(C.CLEANED_CSV, index=False, encoding="utf-8-sig")
    # 标记明细（仅异常点）
    flags = cleaned.loc[cleaned["is_anomaly"], ["timestamp", "rainfall_mm", "flag",
                                                "rainfall_corrected"]]
    flags.rename(columns={"rainfall_mm": "rainfall_raw_mm",
                          "rainfall_corrected": "rainfall_fixed_mm"}
                 ).to_csv(C.FLAG_CSV, index=False, encoding="utf-8-sig")
    print(f"[7] 已保存清洗后数据 -> {C.CLEANED_CSV.name}，异常标记明细 -> {C.FLAG_CSV.name}")

    # 8. 汇总文本
    truth_rain = (truth_df.set_index("timestamp")
                  .reindex(pd.DatetimeIndex(cleaned["timestamp"]))["rainfall_mm"]
                  .reset_index(drop=True))
    _write_summary(reg_info, q_before, q_after, det, clean_log, eval_res)

    # 9. 图表
    print("[8] 生成图表 ...")
    make_all_figures(cleaned, truth_rain, q_before, q_after, eval_res)

    print("=" * 64)
    print(" 全部完成。产物见 data/cleaned, output/figures, output/reports")
    print("=" * 64)
    return cleaned, q_before, q_after, eval_res


def run_ml_mode():
    """只运行学习型异常检测辅助模块。"""
    C.setup_matplotlib()
    print("=" * 64)
    print(" 学习型异常检测辅助流程（IF + LSTM-AE）")
    print("=" * 64)
    raw, reg, _ = load_regularized_inputs()
    rule_det = detect_anomalies(reg)

    from feature_engineering import build_features
    from ml_anomaly import run_ml_anomaly

    features = build_features(load_feature_frame(reg))
    scores, info = run_ml_anomaly(features, rule_det)
    print(f"[ML] Isolation Forest: {info.isolation_forest_status}")
    print(f"[ML] LSTM-AE: {info.lstm_ae_status}")
    if info.lstm_threshold is not None:
        print(f"     LSTM 阈值={info.lstm_threshold:.6f}，训练正常序列={info.train_sequences}")
    print(f"[ML] 输出 -> {C.ML_SCORES_CSV}")
    return scores, info


def run_enhanced():
    """规则法 + 质量标识 + 学习型辅助 + 方法对比 + 预警影响。"""
    cleaned, q_before, q_after, eval_res = run()
    raw, reg, _ = load_regularized_inputs()
    rule_det = detect_anomalies(reg)
    truth_df = pd.read_csv(C.TRUTH_CSV, parse_dates=["timestamp"])
    truth_rain = (truth_df.set_index("timestamp")
                  .reindex(pd.DatetimeIndex(cleaned["timestamp"]))["rainfall_mm"]
                  .reset_index(drop=True))

    print("[enhanced] 构造学习型特征并运行辅助检测 ...")
    from feature_engineering import build_features
    from ml_anomaly import run_ml_anomaly
    from hybrid_qc import build_hybrid_qc
    from quality_flags import build_quality_flags
    from compare_methods import run_method_comparison
    from warning_impact import run_warning_impact

    features = build_features(load_feature_frame(reg))
    ml_scores, ml_info = run_ml_anomaly(features, rule_det)
    print(f"    IF 状态: {ml_info.isolation_forest_status}")
    print(f"    LSTM-AE 状态: {ml_info.lstm_ae_status}")

    print("[enhanced] 融合规则 QC 与学习型检测，输出质量标识 ...")
    hybrid = build_hybrid_qc(cleaned, ml_scores)
    qc = build_quality_flags(cleaned, hybrid)
    print(f"    质量标识 -> {C.CLEANED_QUALITY_CSV}")

    print("[enhanced] 方法对比实验 ...")
    comparison = run_method_comparison(reg, rule_det, ml_scores, truth_df, raw)
    print(f"    方法对比 -> {C.METHOD_COMPARISON_CSV}")

    print("[enhanced] 预警影响分析 ...")
    warning = run_warning_impact(cleaned, truth_rain)
    print(f"    预警影响 -> {C.WARNING_IMPACT_CSV}")
    return {
        "cleaned": cleaned,
        "quality_flags": qc,
        "ml_scores": ml_scores,
        "ml_info": ml_info,
        "hybrid": hybrid,
        "method_comparison": comparison,
        "warning_impact": warning,
    }


def run_ablation_mode():
    C.setup_matplotlib()
    print("=" * 64)
    print(" 规则组件消融实验")
    print("=" * 64)
    raw, reg, _ = load_regularized_inputs()
    truth_df = pd.read_csv(C.TRUTH_CSV, parse_dates=["timestamp"])
    from ablation import run_ablation

    result = run_ablation(reg, truth_df, raw)
    print(f"[ablation] 输出 -> {C.ABLATION_RESULTS_CSV}")
    return result


def run_real_mode():
    C.setup_matplotlib()
    print("=" * 64)
    print(" 真实/类真实数据迁移验证")
    print("=" * 64)
    from real_data_validation import run_real_data_validation

    qc, summary = run_real_data_validation()
    print(f"[real] 数据来源: {summary['source_type']}")
    print(f"[real] 输出 -> {C.REAL_PROCESSED_CSV}")
    print(f"[real] 摘要 -> {C.REAL_VALIDATION_SUMMARY_MD}")
    return qc, summary


def run_all():
    print("=" * 64)
    print(" 增强版全流程：baseline + enhanced + ablation + real")
    print("=" * 64)
    enhanced = run_enhanced()
    ablation = run_ablation_mode()
    real = run_real_mode()
    return {"enhanced": enhanced, "ablation": ablation, "real": real}


def _write_summary(reg_info, q_before, q_after, det, clean_log, eval_res):
    det_m = eval_res["异常检测评估"]
    cor_m = eval_res["数值修正评估"]
    lines = [
        "雨量计异常数据清洗与纠正 —— 结果汇总",
        "=" * 50,
        f"样本数(规则网格)        : {q_before['总样本数']}",
        f"时间轴规整-去重行数      : {reg_info['重复时间戳行数']}",
        f"时间轴规整-是否乱序      : {reg_info['时间戳是否乱序']}",
        "",
        "[清洗前数据质量]",
        f"  缺失率               : {q_before['缺失率(%)']}%",
        f"  负值 / 超量程 / 卡滞  : {q_before['负值数']} / {q_before['超量程数(>40mm/10min)']} / {q_before['疑似卡滞点数']}",
        f"  最大值 / 总降雨量     : {q_before['最大值']} mm / {q_before['总降雨量(mm)']} mm",
        "",
        f"[异常检测] 检出 {int(det['is_anomaly'].sum())} 点：{detection_counts_str(det)}",
        f"  精确率/召回率/F1     : {det_m['精确率(%)']}% / {det_m['召回率(%)']}% / {det_m['F1(%)']}%",
        "",
        "[清洗修正]",
        f"  掩膜异常 / 插值 / 长缺口置0 : {clean_log['掩膜为缺失的异常点数']} / {clean_log['插值填补点数']} / {clean_log['长缺口保守置0点数']}",
        "",
        "[清洗后数据质量]",
        f"  缺失率 / 负值 / 超量程 : {q_after['缺失率(%)']}% / {q_after['负值数']} / {q_after['超量程数(>40mm/10min)']}",
        f"  最大值               : {q_after['最大值']} mm",
        "",
        "[总降雨量（防灾关键指标）]",
        f"  真值                 : {cor_m['总降雨量(mm)']['真值']} mm",
        f"  原始(含异常)         : {cor_m['总降雨量(mm)']['原始']} mm  (误差 {cor_m['总降雨量相对误差(%)']['原始']}%)",
        f"  清洗后               : {cor_m['总降雨量(mm)']['清洗后']} mm  (误差 {cor_m['总降雨量相对误差(%)']['清洗后']}%)",
        f"  平滑后               : {cor_m['总降雨量(mm)']['平滑后']} mm  (误差 {cor_m['总降雨量相对误差(%)']['平滑后']}%)",
        "",
        "[逐点误差 MAE / RMSE]",
        f"  原始(仅有效点)       : {cor_m['逐点误差']['原始(仅有效点)']['MAE']} / {cor_m['逐点误差']['原始(仅有效点)']['RMSE']}",
        f"  清洗后               : {cor_m['逐点误差']['清洗后corrected']['MAE']} / {cor_m['逐点误差']['清洗后corrected']['RMSE']}",
    ]
    C.SUMMARY_TXT.write_text("\n".join(lines), encoding="utf-8")


def detection_counts_str(det):
    return ", ".join(f"{k}={v}" for k, v in detection_counts(det).items())


def main():
    parser = argparse.ArgumentParser(description="雨量计异常数据清洗与质量控制系统")
    parser.add_argument(
        "--mode",
        choices=["baseline", "enhanced", "ml", "ablation", "real", "all"],
        default="baseline",
        help="运行模式；默认 baseline，保持原有一键流程行为。",
    )
    args = parser.parse_args()

    if args.mode == "baseline":
        run()
    elif args.mode == "enhanced":
        run_enhanced()
    elif args.mode == "ml":
        run_ml_mode()
    elif args.mode == "ablation":
        run_ablation_mode()
    elif args.mode == "real":
        run_real_mode()
    elif args.mode == "all":
        run_all()


if __name__ == "__main__":
    main()
