import os
import random

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.layers import Bidirectional, Dense, Dropout, Input, LSTM
from tensorflow.keras.models import Sequential
from tensorflow.keras.optimizers import Adam

from config import (
    CLEAN_DATA_PATH,
    FORECAST_HORIZON,
    FORECAST_PATH,
    METRICS_PATH,
    MODEL_PATH,
    OUTPUT_DIR,
    PREDICTION_PATH,
    PREDICTION_PLOT_PATH,
    RANDOM_SEED,
    RISK_PLOT_PATH,
    RISK_THRESHOLDS_FT,
    SITE_NAME,
    TEST_RATIO,
    WINDOW_SIZE,
)


os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


def classify_risk(stage_ft: float) -> str:
    if stage_ft >= RISK_THRESHOLDS_FT["major"]:
        return "major"
    if stage_ft >= RISK_THRESHOLDS_FT["moderate"]:
        return "moderate"
    if stage_ft >= RISK_THRESHOLDS_FT["minor"]:
        return "minor"
    if stage_ft >= RISK_THRESHOLDS_FT["action"]:
        return "action"
    return "normal"


def create_sequences(values: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    features = []
    labels = []
    max_start = len(values) - WINDOW_SIZE - FORECAST_HORIZON + 1
    for start in range(max_start):
        end = start + WINDOW_SIZE
        features.append(values[start:end])
        labels.append(target[end : end + FORECAST_HORIZON])
    return np.array(features), np.array(labels)


def build_lstm_model(n_features: int) -> Sequential:
    """构建单向LSTM模型"""
    model = Sequential(
        [
            Input(shape=(WINDOW_SIZE, n_features)),
            LSTM(64, return_sequences=True),
            Dropout(0.2),
            LSTM(32),
            Dropout(0.2),
            Dense(32, activation="relu"),
            Dense(FORECAST_HORIZON),
        ]
    )
    model.compile(optimizer=Adam(learning_rate=0.001), loss="mse")
    return model


def build_bilstm_model(n_features: int) -> Sequential:
    """构建双向LSTM模型"""
    model = Sequential(
        [
            Input(shape=(WINDOW_SIZE, n_features)),
            Bidirectional(LSTM(64, return_sequences=True)),
            Dropout(0.2),
            Bidirectional(LSTM(32)),
            Dropout(0.2),
            Dense(32, activation="relu"),
            Dense(FORECAST_HORIZON),
        ]
    )
    model.compile(optimizer=Adam(learning_rate=0.001), loss="mse")
    return model


def inverse_stage(scaler: MinMaxScaler, scaled_stage: np.ndarray, n_features: int) -> np.ndarray:
    placeholder = np.zeros((len(scaled_stage), n_features))
    placeholder[:, 0] = scaled_stage
    return scaler.inverse_transform(placeholder)[:, 0]


def plot_predictions(result: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 5))
    plt.plot(result["datetime"], result["actual_stage_ft_hour_1"], label="Actual water level", linewidth=1.6)
    plt.plot(result["datetime"], result["pred_stage_ft_hour_1"], label="Predicted water level", linewidth=1.6)
    plt.axhline(RISK_THRESHOLDS_FT["minor"], color="#d97706", linestyle="--", linewidth=1, label="Flood stage")
    plt.title(f"LSTM Water Level Prediction - {SITE_NAME}")
    plt.xlabel("Date")
    plt.ylabel("Gage height (ft)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PREDICTION_PLOT_PATH, dpi=180)
    plt.close()


def plot_risk(history: pd.DataFrame, forecast: pd.DataFrame) -> None:
    recent = history.tail(180).copy()

    plt.figure(figsize=(12, 5))
    plt.plot(recent["datetime"], recent["stage_ft"], label="Observed water level", linewidth=1.5)
    plt.plot(forecast["datetime"], forecast["pred_stage_ft"], marker="o", label="Future forecast", linewidth=1.8)

    colors = {
        "action": "#facc15",
        "minor": "#fb923c",
        "moderate": "#ef4444",
        "major": "#7f1d1d",
    }
    labels = {
        "action": "Action stage",
        "minor": "Minor flood",
        "moderate": "Moderate flood",
        "major": "Major flood",
    }
    for key, threshold in RISK_THRESHOLDS_FT.items():
        plt.axhline(threshold, color=colors[key], linestyle="--", linewidth=1, label=labels[key])

    plt.title("Recent Water Level and 24-Hour Flood Risk Forecast")
    plt.xlabel("Date")
    plt.ylabel("Gage height (ft)")
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(RISK_PLOT_PATH, dpi=180)
    plt.close()


def plot_model_comparison(result_lstm: pd.DataFrame, result_bilstm: pd.DataFrame) -> None:
    """绘制LSTM与BiLSTM模型预测对比图"""
    comparison_path = OUTPUT_DIR / "model_comparison.png"
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # 上图：预测对比
    ax1 = axes[0]
    ax1.plot(result_lstm["datetime"], result_lstm["actual_stage_ft_hour_1"], 
             label="Actual", linewidth=1.6, color="black", alpha=0.7)
    ax1.plot(result_lstm["datetime"], result_lstm["pred_stage_ft_hour_1"], 
             label="LSTM Prediction", linewidth=1.5, color="#3b82f6", alpha=0.8)
    ax1.plot(result_bilstm["datetime"], result_bilstm["pred_stage_ft_hour_1"], 
             label="BiLSTM Prediction", linewidth=1.5, color="#ef4444", alpha=0.8)
    ax1.axhline(RISK_THRESHOLDS_FT["minor"], color="#d97706", linestyle="--", linewidth=1, label="Flood stage")
    ax1.set_title(f"LSTM vs BiLSTM Water Level Prediction - {SITE_NAME}")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Gage height (ft)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 下图：预测误差对比
    ax2 = axes[1]
    error_lstm = result_lstm["actual_stage_ft_hour_1"] - result_lstm["pred_stage_ft_hour_1"]
    error_bilstm = result_bilstm["actual_stage_ft_hour_1"] - result_bilstm["pred_stage_ft_hour_1"]
    
    ax2.plot(result_lstm["datetime"], error_lstm, label="LSTM Error", linewidth=1.2, color="#3b82f6", alpha=0.7)
    ax2.plot(result_bilstm["datetime"], error_bilstm, label="BiLSTM Error", linewidth=1.2, color="#ef4444", alpha=0.7)
    ax2.axhline(0, color="black", linestyle="-", linewidth=0.8)
    ax2.set_title("Prediction Error Comparison")
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Error (ft)")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(comparison_path, dpi=180)
    plt.close()
    print(f"Model comparison plot saved to {comparison_path}")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(CLEAN_DATA_PATH, parse_dates=["datetime"])
    feature_columns = ["stage_ft", "discharge_cfs", "precipitation_mm"]
    missing_features = [column for column in feature_columns if column not in data.columns]
    if missing_features:
        raise ValueError(
            f"Missing required model features: {missing_features}. "
            "Run python src/download_usgs.py to rebuild the hourly dataset with rainfall."
        )

    data = data.dropna(subset=feature_columns).reset_index(drop=True)
    print(f"Model input features: {', '.join(feature_columns)}")

    split_index = int(len(data) * (1 - TEST_RATIO))
    train_features = data.loc[: split_index - 1, feature_columns]
    all_features = data.loc[:, feature_columns]

    feature_scaler = MinMaxScaler()
    feature_scaler.fit(train_features)
    scaled_features = feature_scaler.transform(all_features)
    scaled_stage = scaled_features[:, 0]

    x, y = create_sequences(scaled_features, scaled_stage)
    sequence_dates = data["datetime"].iloc[WINDOW_SIZE : WINDOW_SIZE + len(x)].reset_index(drop=True)

    train_size = int(len(x) * (1 - TEST_RATIO))
    x_train, x_test = x[:train_size], x[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]
    test_dates = sequence_dates.iloc[train_size:].reset_index(drop=True)

    # ==================== 训练LSTM模型 ====================
    print("\n" + "=" * 60)
    print("Training LSTM Model...")
    print("=" * 60)
    lstm_model = build_lstm_model(n_features=len(feature_columns))
    early_stop = EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True)
    lstm_model.fit(
        x_train,
        y_train,
        validation_split=0.15,
        epochs=30,
        batch_size=128,
        callbacks=[early_stop],
        verbose=2,
    )
    lstm_model.save(MODEL_PATH)
    print(f"LSTM model saved to {MODEL_PATH}")

    predictions_lstm_scaled = lstm_model.predict(x_test, verbose=0)

    # ==================== 训练BiLSTM模型 ====================
    bilstm_model_path = OUTPUT_DIR / "bilstm_water_level_model.keras"
    print("\n" + "=" * 60)
    print("Training BiLSTM Model...")
    print("=" * 60)
    bilstm_model = build_bilstm_model(n_features=len(feature_columns))
    bilstm_model.fit(
        x_train,
        y_train,
        validation_split=0.15,
        epochs=30,
        batch_size=128,
        callbacks=[early_stop],
        verbose=2,
    )
    bilstm_model.save(bilstm_model_path)
    print(f"BiLSTM model saved to {bilstm_model_path}")

    predictions_bilstm_scaled = bilstm_model.predict(x_test, verbose=0)

    # ==================== 评估两个模型 ====================
    result_lstm = pd.DataFrame({"datetime": test_dates})
    result_bilstm = pd.DataFrame({"datetime": test_dates})
    metrics_lstm = []
    metrics_bilstm = []
    
    for hour in range(FORECAST_HORIZON):
        actual = inverse_stage(feature_scaler, y_test[:, hour], len(feature_columns))
        pred_lstm = inverse_stage(feature_scaler, predictions_lstm_scaled[:, hour], len(feature_columns))
        pred_bilstm = inverse_stage(feature_scaler, predictions_bilstm_scaled[:, hour], len(feature_columns))

        result_lstm[f"actual_stage_ft_hour_{hour + 1}"] = actual
        result_lstm[f"pred_stage_ft_hour_{hour + 1}"] = pred_lstm
        result_lstm[f"actual_stage_m_hour_{hour + 1}"] = actual * 0.3048
        result_lstm[f"pred_stage_m_hour_{hour + 1}"] = pred_lstm * 0.3048

        result_bilstm[f"actual_stage_ft_hour_{hour + 1}"] = actual
        result_bilstm[f"pred_stage_ft_hour_{hour + 1}"] = pred_bilstm
        result_bilstm[f"actual_stage_m_hour_{hour + 1}"] = actual * 0.3048
        result_bilstm[f"pred_stage_m_hour_{hour + 1}"] = pred_bilstm * 0.3048

        metrics_lstm.append(
            {
                "horizon_hour": hour + 1,
                "MAE_ft": mean_absolute_error(actual, pred_lstm),
                "RMSE_ft": mean_squared_error(actual, pred_lstm) ** 0.5,
                "R2": r2_score(actual, pred_lstm),
            }
        )
        metrics_bilstm.append(
            {
                "horizon_hour": hour + 1,
                "MAE_ft": mean_absolute_error(actual, pred_bilstm),
                "RMSE_ft": mean_squared_error(actual, pred_bilstm) ** 0.5,
                "R2": r2_score(actual, pred_bilstm),
            }
        )

    result_lstm.to_csv(PREDICTION_PATH, index=False, encoding="utf-8")
    result_bilstm.to_csv(OUTPUT_DIR / "prediction_result_bilstm.csv", index=False, encoding="utf-8")
    
    metrics_lstm_df = pd.DataFrame(metrics_lstm)
    metrics_bilstm_df = pd.DataFrame(metrics_bilstm)
    
    metrics_lstm_df.to_csv(METRICS_PATH, index=False, encoding="utf-8")
    metrics_bilstm_df.to_csv(OUTPUT_DIR / "evaluation_metrics_bilstm.csv", index=False, encoding="utf-8")

    # ==================== 模型对比汇总 ====================
    print("\n" + "=" * 60)
    print("Model Comparison Summary")
    print("=" * 60)
    comparison_df = pd.DataFrame({
        "Model": ["LSTM", "BiLSTM"],
        "MAE_ft (avg)": [metrics_lstm_df["MAE_ft"].mean(), metrics_bilstm_df["MAE_ft"].mean()],
        "RMSE_ft (avg)": [metrics_lstm_df["RMSE_ft"].mean(), metrics_bilstm_df["RMSE_ft"].mean()],
        "R2 (avg)": [metrics_lstm_df["R2"].mean(), metrics_bilstm_df["R2"].mean()],
    })
    print(comparison_df.to_string(index=False))
    comparison_df.to_csv(OUTPUT_DIR / "model_comparison_metrics.csv", index=False, encoding="utf-8")

    # ==================== 未来预测（使用LSTM模型） ====================
    latest_window = scaled_features[-WINDOW_SIZE:][None, :, :]
    future_scaled = lstm_model.predict(latest_window, verbose=0)[0]
    future_stage_ft = inverse_stage(feature_scaler, future_scaled, len(feature_columns))
    last_date = data["datetime"].max()
    forecast = pd.DataFrame(
        {
            "datetime": pd.date_range(last_date + pd.Timedelta(hours=1), periods=FORECAST_HORIZON, freq="h"),
            "pred_stage_ft": future_stage_ft,
        }
    )
    forecast["pred_stage_m"] = forecast["pred_stage_ft"] * 0.3048
    forecast["risk_level"] = forecast["pred_stage_ft"].map(classify_risk)
    forecast.to_csv(FORECAST_PATH, index=False, encoding="utf-8")

    # ==================== 生成图表 ====================
    plot_predictions(result_lstm)
    plot_risk(data, forecast)
    plot_model_comparison(result_lstm, result_bilstm)

    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print("\nLSTM Metrics:")
    print(metrics_lstm_df.to_string(index=False))
    print("\nBiLSTM Metrics:")
    print(metrics_bilstm_df.to_string(index=False))
    print(f"\nForecast saved to {FORECAST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
