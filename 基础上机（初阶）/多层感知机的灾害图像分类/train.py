from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from features import FEATURE_NAMES, extract_features
from mlp import MLP

ROOT = Path(".")
DATA = ROOT / "data"


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
    model = MLP(input_size=3, hidden1=8, hidden2=4, learning_rate=0.03)
    model.fit(x, y, epochs=1500, batch_size=4)
    probability = model.predict_proba(x)
    prediction = (probability >= 0.5).astype(int)
    model.save(ROOT / "mlp_model.json")

    print(f"网络结构: 3 -> 8(ReLU) -> 4(ReLU) -> 1(Sigmoid)")
    print(f"样本数: {len(y)}（火灾 {int(y.sum())} / 非火灾 {int((y == 0).sum())}）")
    print(f"训练集准确率: {(prediction == y).mean():.2%}")
    print(f"最终二元交叉熵: {model.history[-1]:.6f}")
    print("输入特征:", FEATURE_NAMES)
    for path, actual, pred, prob in zip(paths, y, prediction, probability):
        print(f"{path.name:25s} 真实={actual} 预测={pred} 火灾概率={prob:.2%}")

    plt.figure(figsize=(7, 4))
    plt.plot(model.history)
    plt.xlabel("Epoch")
    plt.ylabel("Binary cross-entropy")
    plt.title("MLP training loss")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(ROOT / "training_loss.png", dpi=160)
    print("模型已保存: mlp_model.json")


if __name__ == "__main__":
    main()

