import cv2
import matplotlib.pyplot as plt
import numpy as np
from dataset import read_rgb

rainy = read_rgb("examples/rainy_input.jpg", 64)
restored = read_rgb("examples/derained_output.jpg", 64)
clear = read_rgb("data/clear/clear_01.jpg", 64)
psnr = lambda a, b: 10*np.log10(1/max(float(np.mean((a-b)**2)), 1e-12))
before, after = psnr(rainy, clear), psnr(restored, clear)
fig, axes = plt.subplots(1,3,figsize=(11,4))
for ax,img,title in zip(axes,(rainy,restored,clear),(f"Rainy input\nPSNR {before:.2f} dB",f"Diffusion derained\nPSNR {after:.2f} dB","Clear reference")):
    ax.imshow(img); ax.set_title(title); ax.axis("off")
fig.tight_layout(); fig.savefig("derain_comparison.png",dpi=180)
print(f"去雨前PSNR: {before:.2f} dB | 去雨后PSNR: {after:.2f} dB")
