"""条件GAN：U-Net式生成器 + PatchGAN判别器。"""
import torch
from torch import nn


class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1),
            nn.InstanceNorm2d(out_channels), nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1),
            nn.InstanceNorm2d(out_channels), nn.LeakyReLU(0.2, inplace=True),
        )

    def forward(self, x): return self.block(x)


class DehazeGenerator(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc1 = ConvBlock(3, 16)
        self.enc2 = ConvBlock(16, 32)
        self.bottleneck = ConvBlock(32, 64)
        self.pool = nn.MaxPool2d(2)
        self.up2 = nn.ConvTranspose2d(64, 32, 2, stride=2)
        self.dec2 = ConvBlock(64, 32)
        self.up1 = nn.ConvTranspose2d(32, 16, 2, stride=2)
        self.dec1 = ConvBlock(32, 16)
        self.output = nn.Sequential(nn.Conv2d(16, 3, 1), nn.Sigmoid())

    def forward(self, x):
        e1 = self.enc1(x); e2 = self.enc2(self.pool(e1))
        middle = self.bottleneck(self.pool(e2))
        d2 = self.dec2(torch.cat([self.up2(middle), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.output(d1)


class PatchDiscriminator(nn.Module):
    def __init__(self):
        super().__init__()
        # 输入是“有雾图+候选清晰图”的6通道拼接。
        self.net = nn.Sequential(
            nn.Conv2d(6, 16, 4, stride=2, padding=1), nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(16, 32, 4, stride=2, padding=1), nn.InstanceNorm2d(32), nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(32, 64, 4, stride=2, padding=1), nn.InstanceNorm2d(64), nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(64, 1, 3, padding=1),
        )

    def forward(self, hazy, candidate):
        return self.net(torch.cat([hazy, candidate], dim=1))

