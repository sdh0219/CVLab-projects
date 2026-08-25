"""提取课件中的三类可解释特征。"""
from pathlib import Path

import cv2
import numpy as np

FEATURE_NAMES = ["火焰色彩比例", "烟雾纹理熵", "边缘方向响应"]


def read_image(path: str | Path) -> np.ndarray:
    raw = np.fromfile(str(path), dtype=np.uint8)  # 支持中文路径
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图像: {path}")
    return image


def extract_features(path: str | Path) -> np.ndarray:
    image = cv2.resize(read_image(path), (256, 256))
    b, g, r = cv2.split(image.astype(np.float32))

    # x1：橙红/亮黄像素占比，是简化的火焰色彩先验。
    fire_mask = (r > 145) & (r > 1.12 * g) & (g > 0.72 * b) & ((r - b) > 45)
    fire_ratio = float(fire_mask.mean())

    # x2：灰度直方图熵，表示亮度分布的离散程度。
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [64], [0, 256]).ravel()
    probability = hist / max(hist.sum(), 1.0)
    entropy = float(-(probability[probability > 0] * np.log2(probability[probability > 0])).sum() / 6.0)

    # x3：Sobel 水平/垂直梯度的不平衡程度，表征边缘方向变化。
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge_response = float(np.mean(np.abs(np.abs(gx) - np.abs(gy))) / 255.0)
    return np.asarray([fire_ratio, entropy, edge_response], dtype=float)

