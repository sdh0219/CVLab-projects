import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

from data_utils import load_water_levels
from model import WaterLevelRNN


def main():
    parser = argparse.ArgumentParser(description="RNN 递归预测未来水位")
    parser.add_argument("--hours", type=int, default=24, help="预测小时数，默认24")
    args = parser.parse_args()
    if not 1 <= args.hours <= 168:
        raise ValueError("hours 必须在 1 到 168 之间")

    checkpoint = torch.load("rnn_model.pt", map_location="cpu", weights_only=True)
    model = WaterLevelRNN(checkpoint["hidden_size"])
    model.load_state_dict(checkpoint["model_state"]); model.eval()
    timestamps, levels = load_water_levels("data/water_level_hourly_2024.csv")
    mean, std = checkpoint["mean"], checkpoint["std"]
    sequence_length = checkpoint["sequence_length"]
    window = list(((levels[-sequence_length:] - mean) / std).astype(float))
    predictions = []
    with torch.no_grad():
        for _ in range(args.hours):
            x = torch.tensor(window[-sequence_length:], dtype=torch.float32).view(1, sequence_length, 1)
            next_value = float(model(x).item())
            window.append(next_value)
            predictions.append(next_value * std + mean)

    future_times = [timestamps[-1] + timedelta(hours=i) for i in range(1, args.hours + 1)]
    with Path("future_water_level.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file); writer.writerow(["Date Time (GMT)", "Predicted Water Level (m, MLLW)"])
        writer.writerows((time.strftime("%Y-%m-%d %H:%M"), f"{value:.3f}") for time, value in zip(future_times, predictions))
    for time, value in zip(future_times, predictions):
        print(f"{time:%Y-%m-%d %H:%M}  {value:.3f} m")

    history_count = 48
    plt.figure(figsize=(11, 4))
    plt.plot(timestamps[-history_count:], levels[-history_count:], label="observed")
    plt.plot(future_times, predictions, label="RNN recursive forecast", marker=".")
    plt.axvline(timestamps[-1], color="gray", linestyle="--")
    plt.xlabel("GMT time"); plt.ylabel("Water level (m, MLLW)")
    plt.title(f"Future {args.hours}-hour water-level forecast")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig("future_forecast.png", dpi=160)


if __name__ == "__main__":
    main()

