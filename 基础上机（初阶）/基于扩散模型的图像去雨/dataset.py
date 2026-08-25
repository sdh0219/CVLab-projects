from pathlib import Path
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset


def read_rgb(path, size=64):
    raw = np.fromfile(str(path), dtype=np.uint8); bgr = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if bgr is None: raise ValueError(f"无法读取: {path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def synthesize_rain(clean, rng):
    """合成不同方向、长度和密度的雨线，并加入轻微雨幕。"""
    h, w, _ = clean.shape; layer = np.zeros((h, w), np.float32)
    area_scale = max(1.0, np.sqrt((h * w) / (64 * 64)))
    count = int(rng.integers(70, 150) * area_scale); angle = rng.uniform(-0.35, 0.35)
    length = int(rng.integers(7, 15)); dx, dy = int(np.sin(angle) * length), int(np.cos(angle) * length)
    for _ in range(count):
        x, y = int(rng.integers(-10, w + 10)), int(rng.integers(-10, h + 10))
        cv2.line(layer, (x, y), (x + dx, y + dy), float(rng.uniform(0.45, 1.0)), 1)
    layer = cv2.GaussianBlur(layer, (3, 3), 0.7)[..., None]
    veil = rng.uniform(0.02, 0.10)
    rainy = clean * (1.0 - veil) + veil * 0.72 + layer * rng.uniform(0.20, 0.42)
    return np.clip(rainy, 0, 1).astype(np.float32)


class RainDataset(Dataset):
    def __init__(self, paths, size=64, variants=10, training=True, seed=42):
        self.paths, self.size, self.variants, self.training, self.seed = list(paths), size, variants, training, seed
    def __len__(self): return len(self.paths) * self.variants
    def __getitem__(self, index):
        clean = read_rgb(self.paths[index % len(self.paths)], self.size)
        rng = np.random.default_rng(None if self.training else self.seed + index)
        if self.training and rng.random() < 0.5: clean = np.ascontiguousarray(clean[:, ::-1])
        rainy = synthesize_rain(clean, rng)
        to_tensor = lambda x: torch.from_numpy(x.copy()).permute(2, 0, 1).float() * 2 - 1
        return to_tensor(rainy), to_tensor(clean), str(self.paths[index % len(self.paths)])


def discover_images(root):
    return sorted(p for p in Path(root).glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
