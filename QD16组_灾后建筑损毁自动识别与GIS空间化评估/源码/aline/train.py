# -*- coding: utf-8 -*-
"""
训练脚本：联合优化定位损失 + 损毁分类损失。
用法:  python train.py            # 用 config 默认参数
       python train.py --epochs 50 --batch 8
"""
import os, argparse, time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

import config as C
from data.dataset import XBDDataset
from models.siamese_unet import SiameseUNet
from utils import confusion_update, f1_from_conf
torch.backends.cudnn.benchmark = True


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=C.EPOCHS)
    p.add_argument("--batch", type=int, default=C.BATCH_SIZE)
    p.add_argument("--lr", type=float, default=C.LR)
    p.add_argument("--pretrained", action="store_true", default=C.PRETRAINED)
    p.add_argument("--device", type=str, default=C.DEVICE)
    return p.parse_args()


def main():
    args = parse_args()
    device = torch.device(args.device if torch.cuda.is_available() or args.device == "cpu" else "cpu")
    print(f"设备: {device} | 预训练编码器: {args.pretrained}")

    train_ds = XBDDataset(C.TRAIN_DIR, augment=True)
    val_ds = XBDDataset(C.VAL_DIR, augment=False)
    print(f"训练样本: {len(train_ds)} | 验证样本: {len(val_ds)}")

    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                          num_workers=C.NUM_WORKERS, drop_last=False)
    val_dl = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                        num_workers=C.NUM_WORKERS)

    model = SiameseUNet(pretrained=args.pretrained).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=C.WEIGHT_DECAY)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

    loc_loss_fn = nn.CrossEntropyLoss()
    dmg_w = torch.tensor(C.DAMAGE_CLASS_WEIGHTS, device=device, dtype=torch.float32)
    dmg_loss_fn = nn.CrossEntropyLoss(weight=dmg_w)

    best_f1 = -1.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0 = time.time()
        running = 0.0
        for pre, post, loc, dmg, _ in train_dl:
            pre, post = pre.to(device), post.to(device)
            loc, dmg = loc.to(device), dmg.to(device)
            opt.zero_grad()
            loc_logits, dmg_logits = model(pre, post)
            loss = (C.LOSS_LOC_W * loc_loss_fn(loc_logits, loc)
                    + C.LOSS_DMG_W * dmg_loss_fn(dmg_logits, dmg))
            loss.backward()
            opt.step()
            running += loss.item() * pre.size(0)
        sched.step()
        train_loss = running / len(train_ds)

        # ---- 验证 ----
        model.eval()
        conf = torch.zeros(C.NUM_DAMAGE, C.NUM_DAMAGE, dtype=torch.long, device=device)
        with torch.no_grad():
            for pre, post, loc, dmg, _ in val_dl:
                pre, post = pre.to(device), post.to(device)
                dmg = dmg.to(device)
                _, dmg_logits = model(pre, post)
                pred = dmg_logits.argmax(1)
                conf = confusion_update(conf, pred, dmg, C.NUM_DAMAGE)
        f1, iou, macro_f1 = f1_from_conf(conf.cpu())
        dt = time.time() - t0
        print(f"epoch {epoch:3d} | loss {train_loss:.4f} | "
              f"损毁宏F1 {macro_f1:.4f} | "
              f"各级F1 {[round(x,3) for x in f1]} | {dt:.1f}s")

        if macro_f1 > best_f1:
            best_f1 = macro_f1
            ckpt = os.path.join(C.CKPT_DIR, "best.pth")
            torch.save({"model": model.state_dict(), "epoch": epoch,
                        "macro_f1": best_f1}, ckpt)
    print(f"训练完成，最佳损毁宏F1 = {best_f1:.4f}，权重已存至 {C.CKPT_DIR}/best.pth")


if __name__ == "__main__":
    main()
