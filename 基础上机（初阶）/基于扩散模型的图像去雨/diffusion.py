import torch


class GaussianDiffusion:
    def __init__(self, steps=40, device="cpu"):
        self.steps, self.device = steps, torch.device(device)
        self.betas = torch.linspace(1e-4, 0.02, steps, device=self.device)
        self.alphas = 1.0 - self.betas; self.alpha_bars = torch.cumprod(self.alphas, dim=0)

    def q_sample(self, x0, t, noise):
        ab = self.alpha_bars[t].view(-1, 1, 1, 1)
        return ab.sqrt() * x0 + (1 - ab).sqrt() * noise

    @torch.no_grad()
    def sample(self, model, condition):
        # 从高斯噪声开始，在有雨图条件下逐步反向去噪。
        # 图像到图像恢复：从“有雨条件图的扩散状态”开始，
        # 而不是纯随机噪声，以保留场景的主要结构。
        start_step = min(9, self.steps - 1)
        start_t = torch.full((len(condition),), start_step, device=condition.device, dtype=torch.long)
        x = self.q_sample(condition, start_t, torch.randn_like(condition))
        for step in reversed(range(start_step + 1)):
            t = torch.full((len(x),), step, device=x.device, dtype=torch.long)
            predicted_noise = model(x, condition, t)
            alpha, alpha_bar, beta = self.alphas[step], self.alpha_bars[step], self.betas[step]
            mean = (x - beta / torch.sqrt(1 - alpha_bar) * predicted_noise) / torch.sqrt(alpha)
            x = mean + (torch.sqrt(beta) * torch.randn_like(x) if step > 0 else 0)
        return x.clamp(-1, 1)
