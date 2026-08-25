"""使用96x96重叠分块推理，生成GAN高清去雾示例。"""
from pathlib import Path
import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
from dataset import synthesize_haze
from model import DehazeGenerator


def load_rgb(path,max_side=768):
    raw=np.fromfile(str(path),np.uint8);img=cv2.cvtColor(cv2.imdecode(raw,cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
    scale=min(1.0,max_side/max(img.shape[:2]));return cv2.resize(img,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA).astype(np.float32)/255


def tiled(model,image,tile=96,stride=72):
    h,w,_=image.shape;ph=max(tile,h);pw=max(tile,w);p=np.pad(image,((0,ph-h),(0,pw-w),(0,0)),mode="reflect")
    ys=list(range(0,ph-tile+1,stride));xs=list(range(0,pw-tile+1,stride))
    if ys[-1]!=ph-tile:ys.append(ph-tile)
    if xs[-1]!=pw-tile:xs.append(pw-tile)
    out=np.zeros_like(p);weight=np.zeros((ph,pw,1),np.float32);window=np.outer(np.hanning(tile),np.hanning(tile)).astype(np.float32)[...,None]+.05
    patches=[];positions=[]
    def flush():
        nonlocal patches,positions
        if not patches:return
        with torch.no_grad():batch=model(torch.stack(patches)).permute(0,2,3,1).numpy()
        for patch,(y,x) in zip(batch,positions):out[y:y+tile,x:x+tile]+=patch*window;weight[y:y+tile,x:x+tile]+=window
        patches=[];positions=[]
    for y in ys:
        for x in xs:
            patches.append(torch.from_numpy(p[y:y+tile,x:x+tile]).permute(2,0,1));positions.append((y,x))
            if len(patches)==12:flush()
    flush();return np.clip(out[:h,:w]/weight[:h,:w],0,1)


def save(path,img):
    bgr=cv2.cvtColor((img*255).astype(np.uint8),cv2.COLOR_RGB2BGR);ok,data=cv2.imencode(".jpg",bgr,[cv2.IMWRITE_JPEG_QUALITY,96]);data.tofile(path)


clear=load_rgb("data/clear/clear_14.jpg");hazy=synthesize_haze(clear,np.random.default_rng(515))
c=torch.load("gan_dehaze_generator.pt",map_location="cpu",weights_only=True);model=DehazeGenerator();model.load_state_dict(c["generator_state"]);model.eval();restored=tiled(model,hazy)
out=Path("examples/high_resolution");out.mkdir(parents=True,exist_ok=True)
save(out/"01_hazy_highres.jpg",hazy);save(out/"02_gan_dehazed_highres.jpg",restored);save(out/"03_clear_highres.jpg",clear)
fig,axes=plt.subplots(1,3,figsize=(18,6))
for ax,img,title in zip(axes,(hazy,restored,clear),("Hazy input","GAN tiled dehazing","Clear reference")):ax.imshow(img);ax.set_title(title,fontsize=16);ax.axis("off")
fig.tight_layout();fig.savefig(out/"gan_highres_comparison.jpg",dpi=180,bbox_inches="tight")
print(f"高清示例: {clear.shape[1]}x{clear.shape[0]}")
