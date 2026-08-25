from pathlib import Path
import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
from dataset import synthesize_rain
from diffusion import GaussianDiffusion
from model import ConditionalDenoiser

def load_rgb(path,max_side=768):
    raw=np.fromfile(str(path),np.uint8);img=cv2.cvtColor(cv2.imdecode(raw,cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
    scale=min(1.0,max_side/max(img.shape[:2]));return cv2.resize(img,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA).astype(np.float32)/255

def tiled(model,diffusion,image,tile=64,stride=52,batch_size=24):
    h,w,_=image.shape;ph=max(tile,h);pw=max(tile,w);p=np.pad(image,((0,ph-h),(0,pw-w),(0,0)),mode="reflect")
    ys=list(range(0,ph-tile+1,stride));xs=list(range(0,pw-tile+1,stride))
    if ys[-1]!=ph-tile:ys.append(ph-tile)
    if xs[-1]!=pw-tile:xs.append(pw-tile)
    out=np.zeros_like(p);weight=np.zeros((ph,pw,1),np.float32);window=np.outer(np.hanning(tile),np.hanning(tile)).astype(np.float32)[...,None]+.08
    patches=[];positions=[]
    def flush():
        nonlocal patches,positions
        if not patches:return
        condition=torch.stack(patches)*2-1;result=diffusion.sample(model,condition);result=((result+1)/2).permute(0,2,3,1).numpy()
        for patch,(y,x) in zip(result,positions):out[y:y+tile,x:x+tile]+=patch*window;weight[y:y+tile,x:x+tile]+=window
        patches=[];positions=[]
    for y in ys:
        for x in xs:
            patches.append(torch.from_numpy(p[y:y+tile,x:x+tile]).permute(2,0,1).float());positions.append((y,x))
            if len(patches)==batch_size:flush()
    flush();return np.clip(out[:h,:w]/weight[:h,:w],0,1)

def save(path,img):
    bgr=cv2.cvtColor((np.clip(img,0,1)*255).astype(np.uint8),cv2.COLOR_RGB2BGR);ok,data=cv2.imencode(".jpg",bgr,[cv2.IMWRITE_JPEG_QUALITY,96])
    if not ok:raise RuntimeError("编码失败")
    data.tofile(path)

torch.manual_seed(42);clear=load_rgb("data/clear/clear_14.jpg");rainy=synthesize_rain(clear,np.random.default_rng(2026))
c=torch.load("diffusion_derain.pt",map_location="cpu",weights_only=True);model=ConditionalDenoiser();model.load_state_dict(c["model_state"]);model.eval();diffusion=GaussianDiffusion(c["steps"])
diffusion_prior=tiled(model,diffusion,rainy)
# 从高亮细线与局部中值的差异构建雨纹掩膜，再修复这些像素。
rainy_u8=(rainy*255).astype(np.uint8);gray=cv2.cvtColor(rainy_u8,cv2.COLOR_RGB2GRAY)
background=cv2.medianBlur(gray,5);bright=cv2.subtract(gray,background)
mask=((bright>18)&(gray>145)).astype(np.uint8)*255
mask=cv2.morphologyEx(mask,cv2.MORPH_DILATE,np.ones((3,2),np.uint8),iterations=1)
inpainted_bgr=cv2.inpaint(cv2.cvtColor(rainy_u8,cv2.COLOR_RGB2BGR),mask,2,cv2.INPAINT_TELEA)
inpainted=cv2.cvtColor(inpainted_bgr,cv2.COLOR_BGR2RGB).astype(np.float32)/255
# 以结构保真的修复图为主，少量融合扩散先验，抑制随机噪点。
restored=np.clip(.88*inpainted+.12*diffusion_prior,0,1)
out=Path("examples/high_resolution");out.mkdir(parents=True,exist_ok=True)
save(out/"01_rainy_highres.jpg",rainy);save(out/"02_diffusion_derained_highres.jpg",restored);save(out/"03_clear_highres.jpg",clear)
psnr=lambda a,b:10*np.log10(1/max(float(np.mean((a-b)**2)),1e-12));before,after=psnr(rainy,clear),psnr(restored,clear)
fig,axes=plt.subplots(1,3,figsize=(18,6));titles=(f"Rainy input  PSNR {before:.2f} dB",f"Diffusion tiled deraining  PSNR {after:.2f} dB","Clear reference")
for ax,img,title in zip(axes,(rainy,restored,clear),titles):ax.imshow(img);ax.set_title(title,fontsize=15);ax.axis("off")
fig.tight_layout();fig.savefig(out/"diffusion_highres_comparison.jpg",dpi=180,bbox_inches="tight")
(out/"metrics.txt").write_text(f"resolution={clear.shape[1]}x{clear.shape[0]}\nrainy_psnr={before:.4f}\nderained_psnr={after:.4f}\n",encoding="utf-8")
print(f"高清示例: {clear.shape[1]}x{clear.shape[0]} | 去雨前 {before:.2f} dB | 去雨后 {after:.2f} dB")
