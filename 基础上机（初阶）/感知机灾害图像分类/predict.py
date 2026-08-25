import argparse
from pathlib import Path

import numpy as np

from features import FEATURE_NAMES, extract_features
from perceptron import Perceptron

# 与 train.py 一致，以当前项目目录为根路径，兼容 Windows 中文路径。
ROOT = Path(".")


def main():
    parser = argparse.ArgumentParser(description="感知机火灾图像二分类")
    parser.add_argument("image", help="待检测图像路径")
    args = parser.parse_args()
    model = Perceptron.load(ROOT / "model.json")
    features = extract_features(args.image).reshape(1, -1)
    score = float(model.decision_function(features)[0])
    label = int(score >= 0)
    print("特征:", dict(zip(FEATURE_NAMES, np.round(features[0], 4))))
    print(f"判别结果: {'火灾' if label else '非火灾'} (y_hat={label}, z={score:.4f})")


if __name__ == "__main__":
    main()
