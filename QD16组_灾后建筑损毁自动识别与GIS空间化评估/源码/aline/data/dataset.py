# -*- coding: utf-8 -*-
"""
xBD PyTorch Dataset：输出 (pre, post, loc_mask, dmg_mask)。
自动配对灾前/灾后影像，在线栅格化标注掩膜。
"""
import os, sys, glob
import numpy as np
import cv2
import torch
from torch.utils.data import Dataset

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from data.mask_from_json import make_loc_mask, make_damage_mask

# ImageNet 归一化
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


class XBDDataset(Dataset):
    def __init__(self, split_dir, img_size=C.IMG_SIZE, augment=False):
        self.img_size = img_size
        self.augment = augment

        # ---- 递归自动发现：不依赖固定的 images/ labels/ 层级 ----
        # 真 xBD 解压后常见结构: <root>/<train_images_labels_targets>/{images,labels,targets}/
        # 这里走遍整棵目录树，按文件名配对，目录怎么套娃都能找到。
        pre_imgs, json_index = [], {}
        for root_, _, files in os.walk(split_dir):
            for f in files:
                # *_pre_disaster.png 只匹配影像，自动排除 targets 里的 *_pre_disaster_target.png
                if f.endswith("_pre_disaster.png"):
                    pre_imgs.append(os.path.join(root_, f))
                elif f.endswith(".json"):
                    json_index[f] = os.path.join(root_, f)

        self.items = []
        for pre_img in sorted(pre_imgs):
            base = os.path.basename(pre_img).replace("_pre_disaster.png", "")
            post_img = pre_img.replace("_pre_disaster.png", "_post_disaster.png")
            pre_json = json_index.get(base + "_pre_disaster.json")
            post_json = json_index.get(base + "_post_disaster.json")
            if os.path.exists(post_img) and pre_json and post_json:
                self.items.append((pre_img, post_img, pre_json, post_json, base))

        if not self.items:
            raise RuntimeError(
                f"未找到配对样本，请检查目录: {split_dir}\n"
                f"  递归扫描到 灾前影像 {len(pre_imgs)} 张, JSON 标注 {len(json_index)} 个。\n"
                f"  排查: ①路径是否指对(应指向含 images/ labels/ 的那一层或其上级); "
                f"②影像是否为 *_pre_disaster.png / *_post_disaster.png 命名; "
                f"③标注是否为同名 .json。")

    def __len__(self):
        return len(self.items)

    def _load_img(self, path):
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    def __getitem__(self, idx):
        pre_img, post_img, pre_json, post_json, base = self.items[idx]
        pre = self._load_img(pre_img)
        post = self._load_img(post_img)
        loc = make_loc_mask(pre_json)
        dmg = make_damage_mask(post_json)

        s = self.img_size
        if pre.shape[0] != s or pre.shape[1] != s:
            pre = cv2.resize(pre, (s, s), interpolation=cv2.INTER_LINEAR)
            post = cv2.resize(post, (s, s), interpolation=cv2.INTER_LINEAR)
            loc = cv2.resize(loc, (s, s), interpolation=cv2.INTER_NEAREST)
            dmg = cv2.resize(dmg, (s, s), interpolation=cv2.INTER_NEAREST)

        if self.augment:
            if np.random.rand() < 0.5:  # 水平翻转
                pre, post, loc, dmg = [np.ascontiguousarray(a[:, ::-1]) for a in (pre, post, loc, dmg)]
            if np.random.rand() < 0.5:  # 垂直翻转
                pre, post, loc, dmg = [np.ascontiguousarray(a[::-1]) for a in (pre, post, loc, dmg)]

        pre = (pre.astype(np.float32) / 255.0 - MEAN) / STD
        post = (post.astype(np.float32) / 255.0 - MEAN) / STD
        pre = torch.from_numpy(pre.transpose(2, 0, 1))
        post = torch.from_numpy(post.transpose(2, 0, 1))
        loc = torch.from_numpy(loc.astype(np.int64))
        dmg = torch.from_numpy(dmg.astype(np.int64))
        return pre, post, loc, dmg, base
