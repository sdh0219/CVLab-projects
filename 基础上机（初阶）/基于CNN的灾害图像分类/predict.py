import argparse
from pathlib import Path

import torch

from dataset import FireDataset
from model import FireCNN


def main():
    parser = argparse.ArgumentParser(description="CNN 火灾图像二分类")
    parser.add_argument("image", help="待检测图像路径")
    args = parser.parse_args()
    checkpoint = torch.load(Path("cnn_model.pt"), map_location="cpu", weights_only=True)
    model = FireCNN()
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    image, _, _ = FireDataset([(Path(args.image), 0)], checkpoint.get("image_size", 128))[0]
    with torch.no_grad():
        probability = torch.sigmoid(model(image.unsqueeze(0))).item()
    label = int(probability >= 0.5)
    print(f"判别结果: {'火灾' if label else '非火灾'}")
    print(f"火灾概率: {probability:.2%} (y_hat={probability:.4f})")


if __name__ == "__main__":
    main()

