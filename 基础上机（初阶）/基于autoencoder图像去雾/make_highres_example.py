"""使用96x96重叠分块推理，生成可放大查看的高清去雾示例。"""
from pathlib import Path
import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
from dataset import synthesize_haze
from model import DehazeAutoencoder


def load_rgb(path, max_side=768):
    raw=np.fromfile(str(path),np.uint8); img=cv2.cvtColor(cv2.imdecode(raw,cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
    scale=min(1.0,max_side/max(img.shape[:2])); return cv2.resize(img,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA).astype(np.float32)/255


def tiled(model,image,tile=96,stride=72):
    h,w,_=image.shape; ph=max(tile,h); pw=max(tile,w); padded=np.pad(image,((0,ph-h),(0,pw-w),(0,0)),mode="reflect")
    ys=list(range(0,ph-tile+1,stride)); xs=list(range(0,pw-tile+1,stride))
    if ys[-1]!=ph-tile: ys.append(ph-tile)
    if xs[-1]!=pw-tile: xs.append(pw-tile)
    output=np.zeros_like(padded); weight=np.zeros((ph,pw,1),np.float32)
    window=np.outer(np.hanning(tile),np.hanning(tile)).astype(np.float32)[...,None]+0.05
    patches=[]; positions=[]
    for y in ys:
        for x in xs:
            patches.append(torch.from_numpy(padded[y:y+tile,x:x+tile]).permute(2,0,1)); positions.append((y,x))
            if len(patches)==16:
                with torch.no_grad(): batch=model(torch.stack(patches)).permute(0,2,3,1).numpy()
                for patch,(py,px) in zip(batch,positions): output[py:py+tile,px:px+tile]+=patch*window; weight[py:py+tile,px:px+tile]+=window
                patches=[]; positions=[]
    if patches:
        with torch.no_grad(): batch=model(torch.stack(patches)).permute(0,2,3,1).numpy()
        for patch,(py,px) in zip(batch,positions): output[py:py+tile,px:px+tile]+=patch*window; weight[py:py+tile,px:px+tile]+=window
    return np.clip(output[:h,:w]/weight[:h,:w],0,1)


def save(path,img):
    bgr=cv2.cvtColor((img*255).astype(np.uint8),cv2.COLOR_RGB2BGR); ok,data=cv2.imencode(".jpg",bgr,[cv2.IMWRITE_JPEG_QUALITY,96]); data.tofile(path)


clear=load_rgb("data/clear/clear_14.jpg"); hazy=synthesize_haze(clear,np.random.default_rng(515))
c=torch.load("autoencoder_dehaze.pt",map_location="cpu",weights_only=True); model=DehazeAutoencoder(); model.load_state_dict(c["model_state"]); model.eval()
restored=tiled(model,hazy); detail=hazy-cv2.GaussianBlur(hazy,(0,0),1.0); restored=np.clip(restored+0.55*detail,0,1)
out=Path("examples/high_resolution"); out.mkdir(parents=True,exist_ok=True)
save(out/"01_hazy_highres.jpg",hazy); save(out/"02_autoencoder_dehazed_highres.jpg",restored); save(out/"03_clear_highres.jpg",clear)
fig,axes=plt.subplots(1,3,figsize=(18,6));
for ax,img,title in zip(axes,(hazy,restored,clear),("Hazy input","Autoencoder tiled dehazing","Clear reference")): ax.imshow(img);ax.set_title(title,fontsize=16);ax.axis("off")
fig.tight_layout();fig.savefig(out/"autoencoder_highres_comparison.jpg",dpi=180,bbox_inches="tight")
print(f"高清示例: {clear.shape[1]}x{clear.shape[0]}")
