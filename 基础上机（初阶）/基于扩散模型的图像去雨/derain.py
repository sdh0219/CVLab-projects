import argparse
from pathlib import Path
import cv2
import numpy as np
import torch
from dataset import read_rgb
from diffusion import GaussianDiffusion
from model import ConditionalDenoiser


def main():
    parser=argparse.ArgumentParser(description="条件扩散模型图像去雨"); parser.add_argument("image")
    parser.add_argument("--output",default="derained_output.jpg"); parser.add_argument("--seed",type=int,default=42); args=parser.parse_args()
    torch.manual_seed(args.seed); c=torch.load("diffusion_derain.pt",map_location="cpu",weights_only=True)
    model=ConditionalDenoiser(); model.load_state_dict(c["model_state"]); model.eval(); diffusion=GaussianDiffusion(c["steps"])
    rgb=read_rgb(args.image,c["image_size"]); condition=torch.from_numpy(rgb).permute(2,0,1).float().unsqueeze(0)*2-1
    restored=diffusion.sample(model,condition)[0]; output=((restored+1)/2).permute(1,2,0).numpy().clip(0,1)
    bgr=cv2.cvtColor((output*255).astype(np.uint8),cv2.COLOR_RGB2BGR); suffix=Path(args.output).suffix or ".jpg"
    ok,encoded=cv2.imencode(suffix,bgr); encoded.tofile(args.output) if ok else (_ for _ in ()).throw(RuntimeError("编码失败"))
    print(f"扩散模型去雨结果已保存: {args.output}")


if __name__ == "__main__": main()

