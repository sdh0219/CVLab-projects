import argparse
from pathlib import Path

import numpy as np

from features import FEATURE_NAMES, extract_features
from mlp import MLP


def main():
    parser = argparse.ArgumentParser(description="MLP 火灾图像二分类")
    parser.add_argument("image", help="待检测图像路径")
    args = parser.parse_args()
    model = MLP.load(Path("mlp_model.json"))
    features = extract_features(args.image).reshape(1, -1)
    probability = float(model.predict_proba(features)[0])
    label = int(probability >= 0.5)
    print("特征:", dict(zip(FEATURE_NAMES, np.round(features[0], 4))))
    print(f"判别结果: {'火灾' if label else '非火灾'}")
    print(f"火灾概率: {probability:.2%} (y_hat={probability:.4f})")


if __name__ == "__main__":
    main()

