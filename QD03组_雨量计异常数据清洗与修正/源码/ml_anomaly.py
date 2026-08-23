# -*- coding: utf-8 -*-
"""
ml_anomaly.py —— 学习型异常检测辅助模块。

包含：
  1. Isolation Forest 基线；
  2. LSTM AutoEncoder 重构误差检测。

注意：本模块只提供异常分数与辅助标签，不做未来水位预测，也不替代
规则 QC 的主方法。若 sklearn 或 torch 不可用，会自动跳过对应模型。
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass

import numpy as np
import pandas as pd

import config as C


@dataclass
class MLRunInfo:
    isolation_forest_status: str
    lstm_ae_status: str
    lstm_threshold: float | None = None
    train_sequences: int = 0


def _numeric_matrix(features: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    numeric = features.select_dtypes(include=[np.number]).copy()
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    for col in numeric.columns:
        med = numeric[col].median()
        numeric[col] = numeric[col].fillna(0.0 if pd.isna(med) else med)
    cols = list(numeric.columns)
    x = numeric.to_numpy(dtype=np.float32)
    if x.size == 0:
        raise ValueError("学习型异常检测没有可用数值特征")
    mean = x.mean(axis=0, keepdims=True)
    std = x.std(axis=0, keepdims=True)
    std[std == 0] = 1.0
    return (x - mean) / std, cols


def run_isolation_forest(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, str]:
    """返回 (score, label, status)。score 越大越异常。"""
    try:
        from sklearn.ensemble import IsolationForest
    except Exception as exc:  # pragma: no cover - 依赖可选
        return (
            np.full(x.shape[0], np.nan),
            np.zeros(x.shape[0], dtype=int),
            f"skipped: sklearn not available ({exc})",
        )

    try:
        model = IsolationForest(
            n_estimators=160,
            contamination=C.IF_CONTAMINATION,
            random_state=C.RANDOM_SEED,
            n_jobs=-1,
        )
        pred = model.fit_predict(x)
        score = -model.decision_function(x)
        label = (pred == -1).astype(int)
        return score.astype(float), label, "enabled"
    except Exception as exc:
        return (
            np.full(x.shape[0], np.nan),
            np.zeros(x.shape[0], dtype=int),
            f"skipped: isolation forest failed ({exc})",
        )


def _make_sequences(x: np.ndarray, window: int) -> np.ndarray:
    return np.stack([x[i:i + window] for i in range(len(x) - window + 1)], axis=0)


def run_lstm_autoencoder(x: np.ndarray,
                         rule_normal_mask: np.ndarray | None = None
                         ) -> tuple[np.ndarray, np.ndarray, str, float | None, int]:
    """LSTM-AE 辅助检测，返回 error、label、status、threshold、训练序列数。"""
    if os.environ.get("RAIN_GAUGE_SKIP_TORCH") == "1":
        return (
            np.full(x.shape[0], np.nan),
            np.zeros(x.shape[0], dtype=int),
            "skipped: torch disabled in self-contained EXE",
            None,
            0,
        )
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except Exception as exc:  # pragma: no cover - 依赖可选
        return (
            np.full(x.shape[0], np.nan),
            np.zeros(x.shape[0], dtype=int),
            f"skipped: torch not available, LSTM-AE skipped ({exc})",
            None,
            0,
        )

    window = int(C.LSTM_WINDOW_SIZE)
    if len(x) < max(window + 1, C.LSTM_MIN_TRAIN_SEQUENCES):
        return (
            np.full(x.shape[0], np.nan),
            np.zeros(x.shape[0], dtype=int),
            "skipped: sample size too small for LSTM-AE",
            None,
            0,
        )

    random.seed(C.RANDOM_SEED)
    np.random.seed(C.RANDOM_SEED)
    torch.manual_seed(C.RANDOM_SEED)

    seq = _make_sequences(x, window)
    if rule_normal_mask is None:
        train_mask = np.ones(len(seq), dtype=bool)
    else:
        normal = np.asarray(rule_normal_mask, dtype=bool)
        train_mask = np.array([
            bool(normal[i:i + window].all()) for i in range(len(seq))
        ])

    train_seq = seq[train_mask]
    if len(train_seq) < C.LSTM_MIN_TRAIN_SEQUENCES:
        return (
            np.full(x.shape[0], np.nan),
            np.zeros(x.shape[0], dtype=int),
            f"skipped: normal sequences too few ({len(train_seq)})",
            None,
            int(len(train_seq)),
        )

    class LSTMAutoEncoder(nn.Module):
        def __init__(self, n_features: int, hidden_dim: int):
            super().__init__()
            self.encoder = nn.LSTM(n_features, hidden_dim, batch_first=True)
            self.decoder = nn.LSTM(hidden_dim, hidden_dim, batch_first=True)
            self.output = nn.Linear(hidden_dim, n_features)

        def forward(self, batch):
            _, (h, _) = self.encoder(batch)
            repeated = h[-1].unsqueeze(1).repeat(1, batch.size(1), 1)
            decoded, _ = self.decoder(repeated)
            return self.output(decoded)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LSTMAutoEncoder(x.shape[1], C.LSTM_HIDDEN_DIM).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=C.LSTM_LEARNING_RATE)
    loss_fn = nn.MSELoss()

    loader = DataLoader(
        TensorDataset(torch.tensor(train_seq, dtype=torch.float32)),
        batch_size=C.LSTM_BATCH_SIZE,
        shuffle=True,
    )
    model.train()
    for _ in range(int(C.LSTM_EPOCHS)):
        for (batch,) in loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            recon = model(batch)
            loss = loss_fn(recon, batch)
            loss.backward()
            optimizer.step()

    def reconstruction_error(batch_seq: np.ndarray) -> np.ndarray:
        errs = []
        eval_loader = DataLoader(
            TensorDataset(torch.tensor(batch_seq, dtype=torch.float32)),
            batch_size=C.LSTM_BATCH_SIZE,
            shuffle=False,
        )
        model.eval()
        with torch.no_grad():
            for (batch,) in eval_loader:
                batch = batch.to(device)
                recon = model(batch)
                err = ((recon - batch) ** 2).mean(dim=(1, 2)).cpu().numpy()
                errs.append(err)
        return np.concatenate(errs)

    all_seq_err = reconstruction_error(seq)
    train_err = all_seq_err[train_mask]
    threshold = float(np.quantile(train_err, C.LSTM_THRESHOLD_QUANTILE))

    point_err = np.full(len(x), np.nan)
    point_err[window - 1:] = all_seq_err
    point_err[:window - 1] = all_seq_err[0]
    label = (point_err > threshold).astype(int)
    return point_err, label, "enabled", threshold, int(len(train_seq))


def run_ml_anomaly(features: pd.DataFrame,
                   rule_df: pd.DataFrame | None = None,
                   save_path=C.ML_SCORES_CSV) -> tuple[pd.DataFrame, MLRunInfo]:
    """运行学习型异常检测并保存逐点分数。"""
    x, feature_cols = _numeric_matrix(features)
    scores = pd.DataFrame({"timestamp": pd.to_datetime(features["timestamp"])})
    scores["n_features"] = len(feature_cols)

    if_score, if_label, if_status = run_isolation_forest(x)
    scores["if_anomaly_score"] = if_score
    scores["if_anomaly_label"] = if_label
    scores["if_status"] = if_status

    normal_mask = None
    if rule_df is not None and "is_anomaly" in rule_df.columns:
        normal_mask = ~rule_df["is_anomaly"].fillna(False).to_numpy(dtype=bool)

    lstm_err, lstm_label, lstm_status, threshold, train_n = run_lstm_autoencoder(
        x, normal_mask,
    )
    scores["lstm_reconstruction_error"] = lstm_err
    scores["lstm_anomaly_label"] = lstm_label
    scores["lstm_status"] = lstm_status
    scores["lstm_threshold"] = threshold

    save_path.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(save_path, index=False, encoding="utf-8-sig")
    info = MLRunInfo(if_status, lstm_status, threshold, train_n)
    return scores, info


if __name__ == "__main__":
    from data_quality import load_raw_rain, regularize_timeaxis
    from anomaly_detection import detect_anomalies
    from feature_engineering import build_features

    raw = load_raw_rain()
    reg, _ = regularize_timeaxis(raw)
    det = detect_anomalies(reg)
    feats = build_features(reg)
    scores, info = run_ml_anomaly(feats, det)
    print(info)
    print(f"模型分数已保存: {C.ML_SCORES_CSV}")
