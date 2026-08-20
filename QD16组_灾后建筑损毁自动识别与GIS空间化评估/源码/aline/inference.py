# -*- coding: utf-8 -*-
"""
推理脚本：对测试集逐张预测，保存损毁掩膜(.png 索引图)与叠加可视化图。
产物存于 outputs/predictions/，供 stats.py 统计与 PPT 配图使用。
用法:  python inference.py
"""
import os, glob
import numpy as np
import cv2
import torch

import config as C
from models.siamese_unet import SiameseUNet
from data.dataset import MEAN, STD
from utils import colorize_damage, overlay


def load_model(device):
    model = SiameseUNet(pretrained=False).to(device)
    ckpt = os.path.join(C.CKPT_DIR, "best.pth")
    state = torch.load(ckpt, map_location=device)
    model.load_state_dict(state["model"])
    model.eval()
    print(f"已加载权重 {ckpt} (epoch {state.get('epoch')}, F1 {state.get('macro_f1'):.4f})")
    return model


def preprocess(path):
    img = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (C.IMG_SIZE, C.IMG_SIZE))
    x = (img.astype(np.float32) / 255.0 - MEAN) / STD
    return torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0)


@torch.no_grad()
def main():
    device = torch.device(C.DEVICE if torch.cuda.is_available() else "cpu")
    model = load_model(device)

    img_dir = C.TEST_DIR
    pres = []
    for root_, _, files in os.walk(img_dir):
        for f in files:
            if f.endswith("_pre_disaster.png"):
                pres.append(os.path.join(root_, f))
    pres = sorted(pres)
    print(f"待推理样本: {len(pres)}")

    for pre_path in pres:
        base = os.path.basename(pre_path).replace("_pre_disaster.png", "")
        post_path = pre_path.replace("_pre_disaster.png", "_post_disaster.png")
        if not os.path.exists(post_path):
            continue

        pre = preprocess(pre_path).to(device)
        post = preprocess(post_path).to(device)
        loc_logits, dmg_logits = model(pre, post)
        loc = loc_logits.argmax(1)[0].cpu().numpy().astype(np.uint8)
        dmg = dmg_logits.argmax(1)[0].cpu().numpy().astype(np.uint8)
        # 用定位结果约束损毁：非建筑区域强制为背景，减少噪声
        dmg = np.where(loc > 0, dmg, 0).astype(np.uint8)

        # 1) 保存索引掩膜（供统计）
        np.save(os.path.join(C.PRED_DIR, base + "_dmg.npy"), dmg)
        cv2.imwrite(os.path.join(C.PRED_DIR, base + "_dmg_mask.png"), dmg)
        # 2) 保存彩色损毁图
        cv2.imwrite(os.path.join(C.PRED_DIR, base + "_dmg_color.png"), colorize_damage(dmg))
        # 3) 保存叠加图（灾后影像 + 损毁着色）
        post_bgr = cv2.resize(cv2.imread(post_path), (C.IMG_SIZE, C.IMG_SIZE))
        cv2.imwrite(os.path.join(C.PRED_DIR, base + "_overlay.png"), overlay(post_bgr, dmg))

    print(f"推理完成，结果存至 {C.PRED_DIR}")


if __name__ == "__main__":
    main()
