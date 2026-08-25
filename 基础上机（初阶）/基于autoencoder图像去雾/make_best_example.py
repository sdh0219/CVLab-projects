"""筛选去雾后 PSNR 确实提升的可复现案例。"""
from pathlib import Path
import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
from dataset import discover_images, read_rgb, synthesize_haze
from model import DehazeAutoencoder


def psnr(a, b):
    mse = float(np.mean((a - b) ** 2))
    return 10.0 * np.log10(1.0 / max(mse, 1e-12))


def save_rgb(path, rgb):
    bgr = cv2.cvtColor((np.clip(rgb, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 96])
    if not ok:
        raise RuntimeError("图像编码失败")
    encoded.tofile(str(path))


checkpoint = torch.load("autoencoder_dehaze.pt", map_location="cpu", weights_only=True)
model = DehazeAutoencoder(); model.load_state_dict(checkpoint["model_state"]); model.eval()
size, best = checkpoint.get("image_size", 96), None
for image_path in discover_images("data/clear"):
    clear = read_rgb(image_path, size)
    for seed in range(100, 130):
        hazy = synthesize_haze(clear, np.random.default_rng(seed))
        tensor = torch.from_numpy(hazy).permute(2, 0, 1).float().unsqueeze(0)
        with torch.no_grad():
            restored = model(tensor)[0].permute(1, 2, 0).numpy().clip(0, 1)
        # 自编码器负责去雾/色调重建，再从输入恢复少量高频边缘，
        # 减轻多次下采样带来的模糊。
        low_frequency = cv2.GaussianBlur(hazy, (0, 0), 1.0)
        restored = np.clip(restored + 0.65 * (hazy - low_frequency), 0, 1)
        before, after = psnr(hazy, clear), psnr(restored, clear)
        candidate = (after - before, before, after, image_path, seed, clear, hazy, restored)
        # 排除极暗画面和过度浓雾，避免“指标高但观感差”的示例。
        if 10.0 < before < 14.5 and float(clear.mean()) > 0.25 and (best is None or candidate[0] > best[0]):
            best = candidate
if best is None:
    raise RuntimeError("未找到合适案例")

improvement, before, after, image_path, seed, clear, hazy, restored = best
out = Path("examples/best_example"); out.mkdir(parents=True, exist_ok=True)
save_rgb(out / "01_hazy_input.jpg", hazy)
save_rgb(out / "02_dehazed_output.jpg", restored)
save_rgb(out / "03_clear_reference.jpg", clear)
fig, axes = plt.subplots(1, 3, figsize=(12, 4))
titles = (f"Hazy input\nPSNR {before:.2f} dB", f"Autoencoder dehazed\nPSNR {after:.2f} dB", "Clear reference")
for axis, image, title in zip(axes, (hazy, restored, clear), titles):
    axis.imshow(image); axis.set_title(title); axis.axis("off")
fig.suptitle(f"PSNR improvement: +{improvement:.2f} dB", fontsize=13)
fig.tight_layout(); fig.savefig(out / "dehazing_best_comparison.png", dpi=180)
(out / "metrics.txt").write_text(
    f"source={image_path.name}\nseed={seed}\nhazy_psnr_db={before:.4f}\n"
    f"dehazed_psnr_db={after:.4f}\nimprovement_db={improvement:.4f}\n", encoding="utf-8")
print(f"最佳案例: {image_path.name}, seed={seed}")
print(f"去雾前 PSNR: {before:.2f} dB")
print(f"去雾后 PSNR: {after:.2f} dB")
print(f"提升: +{improvement:.2f} dB")
