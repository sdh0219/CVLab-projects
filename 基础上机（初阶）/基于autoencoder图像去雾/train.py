from pathlib import Path
import random

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from dataset import HazeDataset, discover_images
from model import DehazeAutoencoder

ROOT = Path(".")


def evaluate(model, loader, criterion, device):
    model.eval(); total = 0.0
    with torch.no_grad():
        for hazy, clean, _ in loader:
            hazy, clean = hazy.to(device), clean.to(device)
            total += criterion(model(hazy), clean).item() * len(hazy)
    return total / len(loader.dataset)


def main():
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    paths = discover_images(ROOT / "data" / "clear")
    if len(paths) < 5:
        raise RuntimeError("至少需要5张清晰图像")
    rng = np.random.default_rng(42); order = rng.permutation(len(paths))
    val_count = max(2, int(len(paths) * 0.2))
    val_paths = [paths[i] for i in order[:val_count]]
    train_paths = [paths[i] for i in order[val_count:]]
    train_loader = DataLoader(HazeDataset(train_paths, variants=20, training=True), batch_size=16, shuffle=True)
    val_loader = DataLoader(HazeDataset(val_paths, variants=5, training=False), batch_size=10)

    model = DehazeAutoencoder().to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    history = {"train": [], "validation": []}
    best_loss, best_epoch = float("inf"), 0
    for epoch in range(1, 31):
        model.train(); running = 0.0
        for hazy, clean, _ in train_loader:
            hazy, clean = hazy.to(device), clean.to(device)
            optimizer.zero_grad(); output = model(hazy)
            loss = criterion(output, clean); loss.backward(); optimizer.step()
            running += loss.item() * len(hazy)
        train_loss = running / len(train_loader.dataset)
        val_loss = evaluate(model, val_loader, criterion, device)
        history["train"].append(train_loss); history["validation"].append(val_loss)
        if val_loss < best_loss:
            best_loss, best_epoch = val_loss, epoch
            torch.save({"model_state": model.state_dict(), "image_size": 96}, ROOT / "autoencoder_dehaze.pt")
        if epoch == 1 or epoch % 5 == 0:
            print(f"Epoch {epoch:02d}/30 | train MSE={train_loss:.6f} | val MSE={val_loss:.6f}")

    checkpoint = torch.load(ROOT / "autoencoder_dehaze.pt", map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state"]); model.eval()
    hazy, clean, _ = val_loader.dataset[0]
    with torch.no_grad(): output = model(hazy.unsqueeze(0).to(device))[0].cpu().clamp(0, 1)
    mse = nn.functional.mse_loss(output, clean).item()
    psnr = 10 * np.log10(1.0 / max(mse, 1e-12))
    print(f"\n设备: {device} | 清晰训练图: {len(train_paths)} | 清晰验证图: {len(val_paths)}")
    print(f"最佳轮次: {best_epoch} | 验证MSE: {best_loss:.6f} | 示例PSNR: {psnr:.2f} dB")

    fig, axes = plt.subplots(1, 3, figsize=(11, 4))
    for axis, image, title in zip(axes, (hazy, output, clean), ("Synthetic haze", "Autoencoder output", "Clear target")):
        axis.imshow(image.permute(1, 2, 0).numpy()); axis.set_title(title); axis.axis("off")
    fig.tight_layout(); fig.savefig(ROOT / "dehaze_comparison.png", dpi=160)
    plt.figure(figsize=(7, 4)); plt.plot(history["train"], label="train"); plt.plot(history["validation"], label="validation")
    plt.xlabel("Epoch"); plt.ylabel("MSE"); plt.title("Autoencoder training loss")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout(); plt.savefig(ROOT / "training_loss.png", dpi=160)


if __name__ == "__main__":
    main()

