import math
import torch
from torch import nn


class TimeEmbedding(nn.Module):
    def __init__(self, dim=32): super().__init__(); self.dim = dim
    def forward(self, t):
        half = self.dim // 2; scale = math.log(10000) / max(half - 1, 1)
        frequencies = torch.exp(torch.arange(half, device=t.device) * -scale)
        angles = t.float().unsqueeze(1) * frequencies.unsqueeze(0)
        return torch.cat([angles.sin(), angles.cos()], dim=1)


class Block(nn.Module):
    def __init__(self, in_ch, out_ch, time_dim=32):
        super().__init__(); self.time = nn.Linear(time_dim, out_ch)
        self.conv1 = nn.Conv2d(in_ch, out_ch, 3, padding=1); self.conv2 = nn.Conv2d(out_ch, out_ch, 3, padding=1)
        self.norm1 = nn.GroupNorm(4, out_ch); self.norm2 = nn.GroupNorm(4, out_ch); self.act = nn.SiLU()
    def forward(self, x, time):
        x = self.act(self.norm1(self.conv1(x)))
        x = x + self.time(time).unsqueeze(-1).unsqueeze(-1)
        return self.act(self.norm2(self.conv2(x)))


class ConditionalDenoiser(nn.Module):
    """输入 x_t 与有雨条件图，预测添加到清晰图的高斯噪声。"""
    def __init__(self):
        super().__init__(); self.time_embedding = TimeEmbedding(32)
        self.enc1 = Block(6, 16); self.enc2 = Block(16, 32); self.middle = Block(32, 32)
        self.pool = nn.MaxPool2d(2); self.up2 = nn.ConvTranspose2d(32, 32, 2, 2)
        self.dec2 = Block(64, 16); self.up1 = nn.ConvTranspose2d(16, 16, 2, 2)
        self.dec1 = Block(32, 16); self.out = nn.Conv2d(16, 3, 1)
    def forward(self, xt, condition, t):
        te = self.time_embedding(t); e1 = self.enc1(torch.cat([xt, condition], 1), te)
        e2 = self.enc2(self.pool(e1), te); middle = self.middle(self.pool(e2), te)
        d2 = self.dec2(torch.cat([self.up2(middle), e2], 1), te)
        d1 = self.dec1(torch.cat([self.up1(d2), e1], 1), te)
        return self.out(d1)

