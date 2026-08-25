from pathlib import Path
import random
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from dataset import RainDataset, discover_images
from diffusion import GaussianDiffusion
from model import ConditionalDenoiser

ROOT = Path(".")


def main():
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    paths = discover_images(ROOT / "data/clear"); order = np.random.default_rng(42).permutation(len(paths))
    val_paths = [paths[i] for i in order[:4]]; train_paths = [paths[i] for i in order[4:]]
    train_loader = DataLoader(RainDataset(train_paths, variants=10, training=True), batch_size=8, shuffle=True)
    val_loader = DataLoader(RainDataset(val_paths, variants=3, training=False), batch_size=6)
    model = ConditionalDenoiser().to(device); diffusion = GaussianDiffusion(steps=40, device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0005); criterion = nn.MSELoss()
    history, best, best_epoch = [], float("inf"), 0
    for epoch in range(1, 21):
        model.train(); total = count = 0
        for rainy, clean, _ in train_loader:
            rainy, clean = rainy.to(device), clean.to(device); t = torch.randint(0, diffusion.steps, (len(clean),), device=device)
            noise = torch.randn_like(clean); xt = diffusion.q_sample(clean, t, noise)
            optimizer.zero_grad(); loss = criterion(model(xt, rainy, t), noise); loss.backward(); optimizer.step()
            total += loss.item() * len(clean); count += len(clean)
        train_loss = total / count; history.append(train_loss)
        if train_loss < best:
            best, best_epoch = train_loss, epoch
            torch.save({"model_state": model.state_dict(), "image_size":64, "steps":40}, ROOT / "diffusion_derain.pt")
        if epoch == 1 or epoch % 5 == 0: print(f"Epoch {epoch:02d}/20 | noise prediction MSE={train_loss:.6f}")

    checkpoint = torch.load(ROOT / "diffusion_derain.pt", map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state"]); model.eval()
    rainy, clean, _ = val_loader.dataset[0]
    restored = diffusion.sample(model, rainy.unsqueeze(0).to(device))[0].cpu()
    to_image = lambda x: ((x.clamp(-1, 1) + 1) / 2).permute(1, 2, 0).numpy()
    rainy_img, clean_img, restored_img = to_image(rainy), to_image(clean), to_image(restored)
    mse = float(np.mean((restored_img-clean_img)**2)); psnr = 10*np.log10(1/max(mse,1e-12))
    print(f"\n设备: {device} | 最佳轮次: {best_epoch} | 噪声MSE: {best:.6f} | 示例PSNR: {psnr:.2f} dB")
    fig, axes = plt.subplots(1,3,figsize=(11,4))
    for ax,img,title in zip(axes,(rainy_img,restored_img,clean_img),("Rainy input","Diffusion derained","Clear target")):
        ax.imshow(img); ax.set_title(title); ax.axis("off")
    fig.tight_layout(); fig.savefig(ROOT/"derain_comparison.png",dpi=160)
    plt.figure(figsize=(7,4)); plt.plot(history); plt.xlabel("Epoch"); plt.ylabel("Noise MSE"); plt.title("Diffusion training loss")
    plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(ROOT/"training_loss.png",dpi=160)


if __name__ == "__main__": main()

