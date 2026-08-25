from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from features import FEATURE_NAMES, extract_features
from perceptron import Perceptron

# 使用 cwd 规避部分旧版 Windows Python 对中文 __file__ 的乱码问题。
# install_and_train.bat 会先切换到项目目录。
ROOT = Path(".")
DATA = ROOT / "data"
MODEL = ROOT / "model.json"


def collect_dataset():
    rows, labels, paths = [], [], []
    for folder, label in (("normal", 0), ("fire", 1)):
        for path in sorted((DATA / folder).glob("*")):
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                rows.append(extract_features(path))
                labels.append(label)
                paths.append(path)
    if len(set(labels)) != 2:
        raise RuntimeError("data/fire 和 data/normal 中都必须有图像")
    return np.vstack(rows), np.asarray(labels), paths


def main():
    x, y, paths = collect_dataset()
    model = Perceptron(learning_rate=0.1, max_epochs=200).fit(x, y)
    prediction = model.predict(x)
    model.save(MODEL)

    print(f"样本数: {len(y)}（火灾 {int(y.sum())} / 非火灾 {int((y == 0).sum())}）")
    print(f"训练集准确率: {(prediction == y).mean():.2%}")
    print("特征权重:", dict(zip(FEATURE_NAMES, np.round(model.weights, 4))))
    for path, actual, pred in zip(paths, y, prediction):
        print(f"{path.name:25s} 真实={actual} 预测={pred}")

    plt.figure(figsize=(7, 4))
    plt.plot(range(1, len(model.history) + 1), model.history, marker="o")
    plt.xlabel("Epoch")
    plt.ylabel("Misclassified samples")
    plt.title("Perceptron training process")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(ROOT / "training_curve.png", dpi=160)
    print(f"模型已保存: {MODEL}")


if __name__ == "__main__":
    main()
