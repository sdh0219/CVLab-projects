# -*- coding: utf-8 -*-
"""
evaluation.py —— 清洗效果量化评估（利用合成数据的逐点真值）。

两类指标：
  1. 异常检测质量：以注入的真值标签为金标准，计算
     - 逐点（是否异常的二分类）精确率/召回率/F1；
     - 分类型召回率（各异常类型被检出的比例）。
  2. 数值修正质量：以干净真值序列为金标准，计算清洗前/后的
     - MAE、RMSE（逐点误差）；
     - 总降雨量误差（防灾应用最关心的累计量）。
"""
import numpy as np
import pandas as pd


def detection_metrics(detected_flag: pd.Series, truth_label: pd.Series) -> dict:
    """二分类（异常/正常）检测指标 + 分类型召回率。"""
    pred = (detected_flag.fillna("") != "").to_numpy()
    true = (truth_label.fillna("") != "").to_numpy()

    tp = int(np.sum(pred & true))
    fp = int(np.sum(pred & ~true))
    fn = int(np.sum(~pred & true))
    tn = int(np.sum(~pred & ~true))

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn)

    # 分类型召回率
    per_type = {}
    for t in ["missing", "negative", "spike", "stuck", "spurious"]:
        m = (truth_label == t).to_numpy()
        n_t = int(m.sum())
        hit = int(np.sum(m & pred))
        per_type[t] = {
            "注入数": n_t,
            "检出数": hit,
            "召回率(%)": round(100 * hit / n_t, 1) if n_t else None,
        }

    return {
        "混淆矩阵": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "精确率(%)": round(100 * precision, 2),
        "召回率(%)": round(100 * recall, 2),
        "F1(%)": round(100 * f1, 2),
        "准确率(%)": round(100 * accuracy, 2),
        "分类型召回": per_type,
    }


def _err(pred: np.ndarray, truth: np.ndarray) -> tuple[float, float]:
    diff = pred - truth
    mae = float(np.nanmean(np.abs(diff)))
    rmse = float(np.sqrt(np.nanmean(diff ** 2)))
    return round(mae, 4), round(rmse, 4)


def correction_metrics(raw: pd.Series, corrected: pd.Series,
                       smoothed: pd.Series, truth: pd.Series) -> dict:
    """数值修正误差：清洗前 vs 清洗后 vs 真值。"""
    truth_v = truth.to_numpy(dtype=float)
    # 原始序列含 NaN，逐点误差对比时把 NaN 视为缺失（用真值不可得，单独统计有效点）
    raw_v = raw.to_numpy(dtype=float)
    valid = ~np.isnan(raw_v)

    mae_raw, rmse_raw = _err(raw_v[valid], truth_v[valid])
    mae_cor, rmse_cor = _err(corrected.to_numpy(dtype=float), truth_v)
    mae_smo, rmse_smo = _err(smoothed.to_numpy(dtype=float), truth_v)

    total_truth = float(truth_v[truth_v > 0].sum())
    total_raw = float(np.nansum(raw_v[raw_v > 0]))
    total_cor = float(corrected[corrected > 0].sum())
    total_smo = float(smoothed[smoothed > 0].sum())

    def perr(x):
        return round(100 * (x - total_truth) / total_truth, 2)

    return {
        "逐点误差": {
            "原始(仅有效点)": {"MAE": mae_raw, "RMSE": rmse_raw},
            "清洗后corrected": {"MAE": mae_cor, "RMSE": rmse_cor},
            "平滑后smoothed": {"MAE": mae_smo, "RMSE": rmse_smo},
        },
        "总降雨量(mm)": {
            "真值": round(total_truth, 1),
            "原始": round(total_raw, 1),
            "清洗后": round(total_cor, 1),
            "平滑后": round(total_smo, 1),
        },
        "总降雨量相对误差(%)": {
            "原始": perr(total_raw),
            "清洗后": perr(total_cor),
            "平滑后": perr(total_smo),
        },
    }


def evaluate(cleaned: pd.DataFrame, truth_df: pd.DataFrame,
             raw_labels: pd.DataFrame) -> dict:
    """汇总评估。
      cleaned    : 含 flag/rainfall_mm/rainfall_corrected/rainfall_smoothed；
      truth_df   : 干净真值，含 rainfall_mm（真实雨量）；
      raw_labels : 原始数据，含 anomaly_truth（逐点真值标签）。
    两份真值均按 timestamp 对齐到 cleaned 的规则时间网格。
    """
    idx = pd.DatetimeIndex(cleaned["timestamp"])

    # 真实雨量（清洗目标值）
    truth_aligned = truth_df.copy().set_index("timestamp").reindex(idx)
    # 逐点真值标签（异常检测金标准）：原始数据去重后按时间对齐
    labels = (raw_labels.copy()
              .drop_duplicates(subset=["timestamp"], keep="first")
              .set_index("timestamp")["anomaly_truth"]
              .reindex(idx))

    det = detection_metrics(cleaned["flag"], labels.reset_index(drop=True))
    cor = correction_metrics(
        cleaned["rainfall_mm"], cleaned["rainfall_corrected"],
        cleaned["rainfall_smoothed"],
        truth_aligned["rainfall_mm"].reset_index(drop=True),
    )
    return {"异常检测评估": det, "数值修正评估": cor}


if __name__ == "__main__":
    import json
    from data_quality import load_raw_rain, regularize_timeaxis
    from anomaly_detection import detect_anomalies
    from cleaning import clean_pipeline
    from config import TRUTH_CSV

    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    det = detect_anomalies(reg)
    cleaned, _ = clean_pipeline(det)
    truth = pd.read_csv(TRUTH_CSV, parse_dates=["timestamp"])
    res = evaluate(cleaned, truth, raw)
    print(json.dumps(res, ensure_ascii=False, indent=2))
