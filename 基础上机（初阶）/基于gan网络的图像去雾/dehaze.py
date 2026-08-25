import argparse
from pathlib import Path
import cv2
import numpy as np
import torch
from dataset import read_rgb
from model import DehazeGenerator


def main():
    parser = argparse.ArgumentParser(description="GAN 图像去雾")
    parser.add_argument("image"); parser.add_argument("--output", default="gan_dehazed_output.jpg")
    args = parser.parse_args()
    checkpoint = torch.load("gan_dehaze_generator.pt", map_location="cpu", weights_only=True)
    model = DehazeGenerator(); model.load_state_dict(checkpoint["generator_state"]); model.eval()
    rgb = read_rgb(args.image, checkpoint.get("image_size", 96))
    tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().unsqueeze(0)
    with torch.no_grad(): output = model(tensor)[0].permute(1, 2, 0).numpy().clip(0, 1)
    bgr = cv2.cvtColor((output * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
    suffix = Path(args.output).suffix or ".jpg"; ok, encoded = cv2.imencode(suffix, bgr)
    if not ok: raise RuntimeError("编码失败")
    encoded.tofile(args.output); print(f"GAN去雾结果已保存: {args.output}")


if __name__ == "__main__": main()

