from pathlib import Path
import cv2
import numpy as np
from dataset import read_rgb,synthesize_rain
clean=read_rgb("data/clear/clear_01.jpg",64); rainy=synthesize_rain(clean,np.random.default_rng(2026))
bgr=cv2.cvtColor((rainy*255).astype(np.uint8),cv2.COLOR_RGB2BGR); ok,encoded=cv2.imencode(".jpg",bgr)
if not ok: raise RuntimeError("编码失败")
Path("examples").mkdir(exist_ok=True); encoded.tofile("examples/rainy_input.jpg"); print("已生成有雨测试图")

