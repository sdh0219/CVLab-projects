from pathlib import Path
import random

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from dataset import HazeDataset, discover_images
from model import DehazeGenerator, PatchDiscriminator

ROOT = Path(".")


def validate(generator, loader, device):
    generator.eval(); total = 0.0
    with torch.no_grad():
        for hazy, clear, _ in loader:
            hazy, clear = hazy.to(device), clear.to(device)
            total += nn.functional.l1_loss(generator(hazy), clear).item() * len(hazy)
    return total / len(loader.dataset)


def main():
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    paths = discover_images(ROOT / "data" / "clear")
    rng = np.random.default_rng(42); order = rng.permutation(len(paths)); val_count = 4
    val_paths = [paths[i] for i in order[:val_count]]; train_paths = [paths[i] for i in order[val_count:]]
    train_loader = DataLoader(HazeDataset(train_paths, image_size=96, variants=10, training=True), batch_size=8, shuffle=True)
    val_loader = DataLoader(HazeDataset(val_paths, image_size=96, variants=5, training=False), batch_size=10)

    generator, discriminator = DehazeGenerator().to(device), PatchDiscriminator().to(device)
    optimizer_g = torch.optim.Adam(generator.parameters(), lr=0.0002, betas=(0.5, 0.999))
    optimizer_d = torch.optim.Adam(discriminator.parameters(), lr=0.0002, betas=(0.5, 0.999))
    adversarial, reconstruction = nn.BCEWithLogitsLoss(), nn.L1Loss()
    history = {"generator": [], "discriminator": [], "validation_l1": []}
    best_val, best_epoch = float("inf"), 0

    for epoch in range(1, 21):
        generator.train(); discriminator.train(); sum_g = sum_d = count = 0
        for hazy, clear, _ in train_loader:
            hazy, clear = hazy.to(device), clear.to(device); batch = len(hazy)
            # 1. 判别器：真实配对为1，生成配对为0。
            optimizer_d.zero_grad(); fake = generator(hazy).detach()
            real_logits = discriminator(hazy, clear); fake_logits = discriminator(hazy, fake)
            loss_d = 0.5 * (adversarial(real_logits, torch.ones_like(real_logits)) +
                            adversarial(fake_logits, torch.zeros_like(fake_logits)))
            loss_d.backward(); optimizer_d.step()
            # 2. 生成器：欺骗判别器，同时保持与清晰目标的L1一致性。
            optimizer_g.zero_grad(); fake = generator(hazy); fake_logits = discriminator(hazy, fake)
            loss_g_gan = adversarial(fake_logits, torch.ones_like(fake_logits))
            loss_g_l1 = reconstruction(fake, clear)
            loss_g = loss_g_gan + 50.0 * loss_g_l1
            loss_g.backward(); optimizer_g.step()
            sum_g += loss_g.item() * batch; sum_d += loss_d.item() * batch; count += batch
        val_l1 = validate(generator, val_loader, device)
        history["generator"].append(sum_g / count); history["discriminator"].append(sum_d / count)
        history["validation_l1"].append(val_l1)
        if val_l1 < best_val:
            best_val, best_epoch = val_l1, epoch
            torch.save({"generator_state": generator.state_dict(), "image_size": 96}, ROOT / "gan_dehaze_generator.pt")
        if epoch == 1 or epoch % 5 == 0:
            print(f"Epoch {epoch:02d}/20 | G={sum_g/count:.4f} | D={sum_d/count:.4f} | val L1={val_l1:.4f}")

    checkpoint = torch.load(ROOT / "gan_dehaze_generator.pt", map_location=device, weights_only=True)
    generator.load_state_dict(checkpoint["generator_state"]); generator.eval()
    hazy, clear, _ = val_loader.dataset[0]
    with torch.no_grad(): restored = generator(hazy.unsqueeze(0).to(device))[0].cpu().clamp(0, 1)
    mse = nn.functional.mse_loss(restored, clear).item(); psnr = 10 * np.log10(1 / max(mse, 1e-12))
    print(f"\n设备: {device} | 最佳轮次: {best_epoch} | 验证L1: {best_val:.4f} | 示例PSNR: {psnr:.2f} dB")

    fig, axes = plt.subplots(1, 3, figsize=(11, 4))
    for axis, image, title in zip(axes, (hazy, restored, clear), ("Synthetic haze", "GAN dehazed", "Clear target")):
        axis.imshow(image.permute(1, 2, 0).numpy()); axis.set_title(title); axis.axis("off")
    fig.tight_layout(); fig.savefig(ROOT / "gan_dehaze_comparison.png", dpi=160)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(history["generator"], label="generator"); axes[0].plot(history["discriminator"], label="discriminator")
    axes[0].set(title="GAN losses", xlabel="Epoch"); axes[0].legend(); axes[0].grid(alpha=0.3)
    axes[1].plot(history["validation_l1"]); axes[1].set(title="Validation L1", xlabel="Epoch"); axes[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(ROOT / "training_curves.png", dpi=160)


if __name__ == "__main__": main()

