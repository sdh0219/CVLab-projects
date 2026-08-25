from pathlib import Path
import random

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from data_utils import SequenceDataset, check_hourly_continuity, load_water_levels
from model import WaterLevelRNN

ROOT = Path(".")
SEQUENCE_LENGTH = 24


def evaluate(model, loader, criterion, device):
    model.eval()
    losses, predictions, targets = [], [], []
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            pred = model(x)
            losses.append(criterion(pred, y).item() * len(y))
            predictions.extend(pred.cpu().numpy())
            targets.extend(y.cpu().numpy())
    return sum(losses) / len(targets), np.asarray(predictions), np.asarray(targets)


def main():
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    timestamps, levels = load_water_levels(ROOT / "data" / "water_level_hourly_2024.csv")
    gaps = check_hourly_continuity(timestamps)
    if gaps:
        raise RuntimeError(f"数据存在 {len(gaps)} 个非小时间隔，请先补齐")

    n = len(levels)
    train_end, val_end = int(n * 0.70), int(n * 0.85)
    mean, std = float(levels[:train_end].mean()), float(levels[:train_end].std())
    normalized = (levels - mean) / std

    # 后两段向前多保留 24 小时，仅作为首个目标的历史输入。
    train_values = normalized[:train_end]
    val_values = normalized[train_end - SEQUENCE_LENGTH : val_end]
    test_values = normalized[val_end - SEQUENCE_LENGTH :]
    train_loader = DataLoader(SequenceDataset(train_values, SEQUENCE_LENGTH), batch_size=64, shuffle=True)
    val_loader = DataLoader(SequenceDataset(val_values, SEQUENCE_LENGTH), batch_size=128)
    test_loader = DataLoader(SequenceDataset(test_values, SEQUENCE_LENGTH), batch_size=128)

    model = WaterLevelRNN(hidden_size=32).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    history = {"train": [], "validation": []}
    best_loss, best_epoch = float("inf"), 0

    for epoch in range(1, 31):
        model.train()
        running = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            running += loss.item() * len(y)
        train_loss = running / len(train_loader.dataset)
        val_loss, _, _ = evaluate(model, val_loader, criterion, device)
        history["train"].append(train_loss); history["validation"].append(val_loss)
        if val_loss < best_loss:
            best_loss, best_epoch = val_loss, epoch
            torch.save({
                "model_state": model.state_dict(), "hidden_size": 32,
                "sequence_length": SEQUENCE_LENGTH, "mean": mean, "std": std,
                "last_timestamp": timestamps[-1].isoformat(),
            }, ROOT / "rnn_model.pt")
        if epoch == 1 or epoch % 5 == 0:
            print(f"Epoch {epoch:02d}/30 | train MSE={train_loss:.6f} | val MSE={val_loss:.6f}")

    checkpoint = torch.load(ROOT / "rnn_model.pt", map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state"])
    test_loss, pred_norm, target_norm = evaluate(model, test_loader, criterion, device)
    predictions = pred_norm * std + mean
    targets = target_norm * std + mean
    mae = float(np.mean(np.abs(predictions - targets)))
    rmse = float(np.sqrt(np.mean((predictions - targets) ** 2)))
    print(f"\n数据量: {n} 条 | 设备: {device} | 最佳轮次: {best_epoch}")
    print(f"测试集 MAE: {mae:.4f} 米 | RMSE: {rmse:.4f} 米 | 标准化MSE: {test_loss:.6f}")

    test_times = timestamps[val_end:]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    axes[0].plot(history["train"], label="train")
    axes[0].plot(history["validation"], label="validation")
    axes[0].set(title="RNN training loss", xlabel="Epoch", ylabel="MSE")
    axes[0].legend(); axes[0].grid(alpha=0.3)
    show = min(24 * 7, len(targets))
    axes[1].plot(test_times[-show:], targets[-show:], label="observed")
    axes[1].plot(test_times[-show:], predictions[-show:], label="one-step prediction")
    axes[1].set(title="Last 7 days of test set", xlabel="GMT time", ylabel="Water level (m, MLLW)")
    axes[1].legend(); axes[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(ROOT / "training_and_test.png", dpi=160)


if __name__ == "__main__":
    main()

