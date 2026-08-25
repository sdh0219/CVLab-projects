from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset


def read_rgb(path, image_size=128):
    raw = np.fromfile(str(path), dtype=np.uint8)  # 兼容 Windows 中文路径
    bgr = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"无法读取图像: {path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return cv2.resize(rgb, (image_size, image_size), interpolation=cv2.INTER_AREA)


class FireDataset(Dataset):
    def __init__(self, samples, image_size=128, augment=False):
        self.samples = samples
        self.image_size = image_size
        self.augment = augment

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        path, label = self.samples[index]
        image = read_rgb(path, self.image_size)
        if self.augment:
            if np.random.random() < 0.5:
                image = np.ascontiguousarray(image[:, ::-1])
            # 亮度与对比度扰动，降低对单一光照的依赖。
            alpha = np.random.uniform(0.85, 1.15)
            beta = np.random.uniform(-12, 12)
            image = np.clip(image.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)
        tensor = torch.from_numpy(image.copy()).permute(2, 0, 1).float() / 255.0
        # ImageNet 常用均值/标准差归一化。
        mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
        return (tensor - mean) / std, torch.tensor(label, dtype=torch.float32), str(path)


def discover_samples(data_root):
    samples = []
    for folder, label in (("normal", 0), ("fire", 1)):
        for path in sorted((Path(data_root) / folder).glob("*")):
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                samples.append((path, label))
    return samples


def stratified_split(samples, validation_per_class=2, seed=42):
    rng = np.random.default_rng(seed)
    train, validation = [], []
    for label in (0, 1):
        group = [sample for sample in samples if sample[1] == label]
        rng.shuffle(group)
        validation.extend(group[:validation_per_class])
        train.extend(group[validation_per_class:])
    rng.shuffle(train)
    return train, validation

