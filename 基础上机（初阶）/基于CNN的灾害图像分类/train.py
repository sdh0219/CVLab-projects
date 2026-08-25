from pathlib import Path
import random

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from dataset import FireDataset, discover_samples, stratified_split
from model import FireCNN

ROOT = Path(".")


def metrics(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    with torch.no_grad():
        for images, labels, _ in loader:
            images, labels = images.to(device), labels.to(device)
            logits = model(images)
            total_loss += criterion(logits, labels).item() * len(labels)
            correct += ((torch.sigmoid(logits) >= 0.5) == labels.bool()).sum().item()
            total += len(labels)
    return total_loss / total, correct / total


def main():
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    samples = discover_samples(ROOT / "data")
    if sum(label == 0 for _, label in samples) < 3 or sum(label == 1 for _, label in samples) < 3:
        raise RuntimeError("每个类别至少需要 3 张图像")
    train_samples, val_samples = stratified_split(samples, validation_per_class=2)
    train_loader = DataLoader(FireDataset(train_samples, augment=True), batch_size=4, shuffle=True)
    train_eval_loader = DataLoader(FireDataset(train_samples), batch_size=4)
    val_loader = DataLoader(FireDataset(val_samples), batch_size=4)

    model = FireCNN().to(device)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}
    best_val_loss = float("inf")
    best_epoch = 0

    for epoch in range(1, 81):
        model.train()
        for images, labels, _ in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
        train_loss, train_acc = metrics(model, train_eval_loader, criterion, device)
        val_loss, val_acc = metrics(model, val_loader, criterion, device)
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["train_acc"].append(train_acc)
        history["val_acc"].append(val_acc)
        if val_loss < best_val_loss:
            best_val_loss, best_epoch = val_loss, epoch
            torch.save({"model_state": model.state_dict(), "image_size": 128}, ROOT / "cnn_model.pt")
        if epoch == 1 or epoch % 10 == 0:
            print(f"Epoch {epoch:02d}/80 | train loss={train_loss:.4f}, acc={train_acc:.2%} | "
                  f"val loss={val_loss:.4f}, acc={val_acc:.2%}")

    checkpoint = torch.load(ROOT / "cnn_model.pt", map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state"])
    train_loss, train_acc = metrics(model, train_eval_loader, criterion, device)
    val_loss, val_acc = metrics(model, val_loader, criterion, device)
    print(f"\n设备: {device} | 训练 {len(train_samples)} 张 | 验证 {len(val_samples)} 张")
    print(f"最佳轮次: {best_epoch} | 训练准确率: {train_acc:.2%} | 验证准确率: {val_acc:.2%}")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(history["train_loss"], label="train")
    axes[0].plot(history["val_loss"], label="validation")
    axes[0].set(title="Loss", xlabel="Epoch", ylabel="BCE")
    axes[0].legend(); axes[0].grid(alpha=0.3)
    axes[1].plot(history["train_acc"], label="train")
    axes[1].plot(history["val_acc"], label="validation")
    axes[1].set(title="Accuracy", xlabel="Epoch", ylabel="Accuracy", ylim=(0, 1.05))
    axes[1].legend(); axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ROOT / "training_curves.png", dpi=160)


if __name__ == "__main__":
    main()

