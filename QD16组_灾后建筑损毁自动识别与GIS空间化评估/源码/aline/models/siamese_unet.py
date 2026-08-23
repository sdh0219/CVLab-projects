# -*- coding: utf-8 -*-
"""
孪生变化检测网络 (Siamese U-Net)
- 共享权重编码器(ResNet)分别处理灾前/灾后影像
- 定位头：基于灾前特征 -> 2 类(背景/建筑)
- 损毁头：基于灾前/灾后特征逐层绝对差 -> 5 类(背景 + 4 级损毁)
设计参考 xView2 主流孪生方案 (microsoft/building-damage-assessment-cnn-siamese 等)。
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C


def _build_encoder(name, pretrained):
    weights = "IMAGENET1K_V1" if pretrained else None
    if name == "resnet34":
        net = torchvision.models.resnet34(weights=weights)
        chs = [64, 64, 128, 256, 512]
    elif name == "resnet18":
        net = torchvision.models.resnet18(weights=weights)
        chs = [64, 64, 128, 256, 512]
    elif name == "resnet50":
        net = torchvision.models.resnet50(weights=weights)
        chs = [64, 256, 512, 1024, 2048]
    else:
        raise ValueError(f"未知编码器: {name}")
    return net, chs


class Encoder(nn.Module):
    """返回 5 个尺度特征 [/2,/4,/8,/16,/32]。"""
    def __init__(self, name=C.ENCODER, pretrained=C.PRETRAINED):
        super().__init__()
        net, self.channels = _build_encoder(name, pretrained)
        self.stem = nn.Sequential(net.conv1, net.bn1, net.relu)  # /2, 64
        self.pool = net.maxpool
        self.layer1 = net.layer1  # /4
        self.layer2 = net.layer2  # /8
        self.layer3 = net.layer3  # /16
        self.layer4 = net.layer4  # /32

    def forward(self, x):
        f0 = self.stem(x)             # /2
        f1 = self.layer1(self.pool(f0))  # /4
        f2 = self.layer2(f1)          # /8
        f3 = self.layer3(f2)          # /16
        f4 = self.layer4(f3)          # /32
        return [f0, f1, f2, f3, f4]


class DecoderBlock(nn.Module):
    def __init__(self, in_ch, skip_ch, out_ch):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch + skip_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
        )

    def forward(self, x, skip=None):
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        if skip is not None:
            if x.shape[-2:] != skip.shape[-2:]:
                x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
            x = torch.cat([x, skip], dim=1)
        return self.conv(x)


class UNetDecoder(nn.Module):
    """标准 U-Net 解码器，输入 5 尺度特征列表，输出全分辨率 logits。"""
    def __init__(self, enc_channels, n_classes):
        super().__init__()
        c0, c1, c2, c3, c4 = enc_channels
        self.up1 = DecoderBlock(c4, c3, 256)  # /16
        self.up2 = DecoderBlock(256, c2, 128) # /8
        self.up3 = DecoderBlock(128, c1, 64)  # /4
        self.up4 = DecoderBlock(64, c0, 32)   # /2
        self.up5 = DecoderBlock(32, 0, 16)    # /1
        self.head = nn.Conv2d(16, n_classes, 1)

    def forward(self, feats):
        f0, f1, f2, f3, f4 = feats
        x = self.up1(f4, f3)
        x = self.up2(x, f2)
        x = self.up3(x, f1)
        x = self.up4(x, f0)
        x = self.up5(x, None)
        return self.head(x)


class SiameseUNet(nn.Module):
    def __init__(self, encoder=C.ENCODER, pretrained=C.PRETRAINED,
                 num_loc=C.NUM_LOC, num_dmg=C.NUM_DAMAGE):
        super().__init__()
        self.encoder = Encoder(encoder, pretrained)
        chs = self.encoder.channels
        self.loc_decoder = UNetDecoder(chs, num_loc)  # 用灾前特征
        self.dmg_decoder = UNetDecoder(chs, num_dmg)  # 用前后特征差

    def forward(self, pre, post):
        fp = self.encoder(pre)
        fq = self.encoder(post)
        loc_logits = self.loc_decoder(fp)
        diff = [torch.abs(a - b) for a, b in zip(fp, fq)]
        dmg_logits = self.dmg_decoder(diff)
        return loc_logits, dmg_logits


if __name__ == "__main__":
    m = SiameseUNet(pretrained=False)
    a = torch.randn(2, 3, C.IMG_SIZE, C.IMG_SIZE)
    b = torch.randn(2, 3, C.IMG_SIZE, C.IMG_SIZE)
    lo, dm = m(a, b)
    print("loc logits:", lo.shape, " dmg logits:", dm.shape)
    n = sum(p.numel() for p in m.parameters()) / 1e6
    print(f"参数量: {n:.2f} M")
