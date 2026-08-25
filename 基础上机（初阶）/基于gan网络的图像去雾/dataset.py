from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset


def read_rgb(path, image_size=96):
    raw = np.fromfile(str(path), dtype=np.uint8)
    bgr = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"无法读取图像: {path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return cv2.resize(rgb, (image_size, image_size), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def synthesize_haze(clean, rng):
    """大气散射简化模型 I=J*t+A*(1-t)，加入空间渐变透射率。"""
    height, width, _ = clean.shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    direction = rng.uniform(0, 2 * np.pi)
    gradient = (np.cos(direction) * xx / width + np.sin(direction) * yy / height)
    gradient = (gradient - gradient.min()) / max(float(gradient.max() - gradient.min()), 1e-6)
    base_t = rng.uniform(0.35, 0.75)
    transmission = np.clip(base_t + rng.uniform(-0.18, 0.18) * gradient, 0.25, 0.85)[..., None]
    atmospheric_light = rng.uniform(0.82, 1.0, size=(1, 1, 3)).astype(np.float32)
    hazy = clean * transmission + atmospheric_light * (1.0 - transmission)
    noise = rng.normal(0, 0.008, clean.shape).astype(np.float32)
    return np.clip(hazy + noise, 0, 1).astype(np.float32)


class HazeDataset(Dataset):
    def __init__(self, paths, image_size=96, variants=20, training=True, seed=42):
        self.paths = list(paths)
        self.image_size = image_size
        self.variants = variants
        self.training = training
        self.seed = seed

    def __len__(self):
        return len(self.paths) * self.variants

    def __getitem__(self, index):
        image_index = index % len(self.paths)
        clean = read_rgb(self.paths[image_index], self.image_size)
        # 验证集同一 index 总是同一片雾；训练集每次随机。
        rng = np.random.default_rng(None if self.training else self.seed + index)
        if self.training and rng.random() < 0.5:
            clean = np.ascontiguousarray(clean[:, ::-1])
        hazy = synthesize_haze(clean, rng)
        to_tensor = lambda x: torch.from_numpy(x.copy()).permute(2, 0, 1).float()
        return to_tensor(hazy), to_tensor(clean), str(self.paths[image_index])


def discover_images(root):
    return sorted(path for path in Path(root).glob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png"})

