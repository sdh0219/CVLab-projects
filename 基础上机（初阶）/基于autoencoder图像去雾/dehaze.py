import argparse
from pathlib import Path

import cv2
import numpy as np
import torch

from dataset import read_rgb
from model import DehazeAutoencoder


def save_rgb(path, rgb):
    bgr = cv2.cvtColor((np.clip(rgb, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(Path(path).suffix or ".jpg", bgr)
    if not ok: raise RuntimeError("图像编码失败")
    encoded.tofile(str(path))


def main():
    parser = argparse.ArgumentParser(description="Autoencoder 图像去雾")
    parser.add_argument("image", help="待去雾图像")
    parser.add_argument("--output", default="dehazed_output.jpg", help="输出路径")
    args = parser.parse_args()
    checkpoint = torch.load("autoencoder_dehaze.pt", map_location="cpu", weights_only=True)
    model = DehazeAutoencoder(); model.load_state_dict(checkpoint["model_state"]); model.eval()
    rgb = read_rgb(args.image, checkpoint.get("image_size", 96))
    tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().unsqueeze(0)
    with torch.no_grad(): output = model(tensor)[0].permute(1, 2, 0).numpy()
    save_rgb(args.output, output); print(f"去雾结果已保存: {args.output}")


if __name__ == "__main__":
    main()

