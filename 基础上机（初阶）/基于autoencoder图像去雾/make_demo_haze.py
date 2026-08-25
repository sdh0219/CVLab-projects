from pathlib import Path
import cv2
import numpy as np
from dataset import read_rgb, synthesize_haze

image = read_rgb("data/clear/clear_01.jpg", 96)
hazy = synthesize_haze(image, np.random.default_rng(2026))
bgr = cv2.cvtColor((hazy * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
ok, encoded = cv2.imencode(".jpg", bgr)
if not ok: raise RuntimeError("编码失败")
Path("examples").mkdir(exist_ok=True)
encoded.tofile("examples/hazy_demo.jpg")
print("已生成 examples/hazy_demo.jpg")

