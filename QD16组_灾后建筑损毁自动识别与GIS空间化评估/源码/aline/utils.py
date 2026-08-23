# -*- coding: utf-8 -*-
"""通用工具：掩膜上色、评价指标。"""
import numpy as np
import torch

import config as C


def colorize_damage(mask):
    """损毁等级掩膜 (HxW, 0~4) -> BGR 彩图，供 OpenCV 保存。"""
    h, w = mask.shape
    out = np.zeros((h, w, 3), np.uint8)
    for cls, color in C.DAMAGE_COLORS_BGR.items():
        out[mask == cls] = color
    return out


def overlay(image_bgr, mask, alpha=0.5):
    """把彩色损毁掩膜叠到原影像上。image_bgr 为 uint8 BGR。"""
    cmap = colorize_damage(mask)
    blend = image_bgr.copy()
    fg = mask > 0
    blend[fg] = (alpha * cmap[fg] + (1 - alpha) * image_bgr[fg]).astype(np.uint8)
    return blend


@torch.no_grad()
def confusion_update(conf, pred, target, n_cls):
    """累加混淆矩阵。pred/target 为 (N,H,W) long 张量。"""
    k = (target >= 0) & (target < n_cls)
    idx = n_cls * target[k].long() + pred[k].long()
    binc = torch.bincount(idx, minlength=n_cls ** 2)
    conf += binc.reshape(n_cls, n_cls)
    return conf


def f1_from_conf(conf):
    """逐类 F1 与宏平均（忽略背景类 0）。conf: (C,C) tensor。"""
    conf = conf.float()
    tp = torch.diag(conf)
    fp = conf.sum(0) - tp
    fn = conf.sum(1) - tp
    f1 = 2 * tp / (2 * tp + fp + fn + 1e-6)
    iou = tp / (tp + fp + fn + 1e-6)
    macro_f1 = f1[1:].mean().item()  # 忽略背景
    return f1.tolist(), iou.tolist(), macro_f1
