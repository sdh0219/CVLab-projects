"""纯 PyTorch 实现的线性链 CRF (Conditional Random Field)。

用于 BERT 之上, 约束标签转移, 提升实体边界的合法性。

核心参数 (均为可学习):
    start_transitions[C]  : 从起始状态到各 tag 的分数
    end_transitions[C]    : 从各 tag 到结束状态的分数
    transitions[C, C]     : 从 tag i 转移到 tag j 的分数

接口:
    crf = CRF(num_tags=9, batch_first=True)
    emissions = bert(...)                       # [B, T, C]
    log_likelihood = crf(emissions, tags, mask) # [B], 越大越好
    best_paths = crf.decode(emissions, mask)    # list[list[int]]

参考: "Bidirectional LSTM-CRF Models for Sequence Tagging" (Lample et al., 2016)
"""
from __future__ import annotations

import torch
import torch.nn as nn


class CRF(nn.Module):
    """线性链 CRF。batch_first=True 时输入张量第 0 维是 batch。"""

    def __init__(self, num_tags: int, batch_first: bool = True):
        super().__init__()
        self.num_tags = num_tags
        self.batch_first = batch_first
        self.start_transitions = nn.Parameter(torch.empty(num_tags))
        self.end_transitions = nn.Parameter(torch.empty(num_tags))
        self.transitions = nn.Parameter(torch.empty(num_tags, num_tags))
        self.reset_parameters()

    def reset_parameters(self) -> None:
        """均匀初始化转移参数。"""
        nn.init.uniform_(self.start_transitions, -0.1, 0.1)
        nn.init.uniform_(self.end_transitions, -0.1, 0.1)
        nn.init.uniform_(self.transitions, -0.1, 0.1)

    # ------------------------------------------------------------------
    # 内部计算
    # ------------------------------------------------------------------
    def _ensure_batch_first(self, emissions, tags, mask):
        """若非 batch_first, 把 [T, B, ...] 转成 [B, T, ...]。"""
        if not self.batch_first:
            emissions = emissions.transpose(0, 1).contiguous()
            tags = tags.transpose(0, 1).contiguous()
            if mask is not None:
                mask = mask.transpose(0, 1).contiguous()
        if mask is None:
            mask = torch.ones_like(tags, dtype=torch.float)
        return emissions, tags, mask.float()

    def _compute_score(self, emissions: torch.Tensor,
                       tags: torch.LongTensor,
                       mask: torch.Tensor) -> torch.Tensor:
        """gold 序列的分数 (分子)。返回 [B]。"""
        B = emissions.size(0)
        # 起始转移 + 第一个 token 的发射
        score = self.start_transitions[tags[:, 0]] \
            + emissions[torch.arange(B), 0, tags[:, 0]]
        # 逐 token 累加转移 + 发射 (padding 位置不计入)
        for t in range(1, emissions.size(1)):
            emit = emissions[torch.arange(B), t, tags[:, t]]
            trans = self.transitions[tags[:, t - 1], tags[:, t]]
            score = score + mask[:, t] * (trans + emit)
        # 末尾转移 (取每个样本最后一个有效 tag)
        seq_lens = mask.sum(dim=1).long() - 1
        last_tags = tags[torch.arange(B), seq_lens]
        return score + self.end_transitions[last_tags]

    def _compute_partition(self, emissions: torch.Tensor,
                           mask: torch.Tensor) -> torch.Tensor:
        """配分函数 (分母), 前向算法。返回 [B]。

        alpha[t][j] = 截至位置 t, 且该位置标签为 j 的所有路径分数之和 (log 域)。
        """
        alpha = self.start_transitions.unsqueeze(0) + emissions[:, 0]
        for t in range(1, emissions.size(1)):
            # scores[b, i, j] = alpha[b, i] + trans[i, j] + emit[b, j]
            scores = alpha.unsqueeze(2) + self.transitions.unsqueeze(0) \
                + emissions[:, t].unsqueeze(1)
            new_alpha = torch.logsumexp(scores, dim=1)
            m = mask[:, t].unsqueeze(1)
            alpha = torch.where(m.bool(), new_alpha, alpha)
        alpha = alpha + self.end_transitions.unsqueeze(0)
        return torch.logsumexp(alpha, dim=1)

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def forward(self, emissions: torch.Tensor,
                tags: torch.LongTensor,
                mask: torch.Tensor | None = None) -> torch.Tensor:
        """返回对数似然 num - logZ (per-sample, [B]); 损失 = -forward().mean()。"""
        emissions, tags, mask = self._ensure_batch_first(emissions, tags, mask)
        num = self._compute_score(emissions, tags, mask)
        logZ = self._compute_partition(emissions, mask)
        return num - logZ

    @torch.no_grad()
    def decode(self, emissions: torch.Tensor,
               mask: torch.Tensor | None = None) -> list[list[int]]:
        """Viterbi 解码, 返回每个样本的最优标签序列 (不含 padding)。"""
        if not self.batch_first:
            emissions = emissions.transpose(0, 1).contiguous()
            if mask is not None:
                mask = mask.transpose(0, 1).contiguous()
        B, T, _ = emissions.shape
        if mask is None:
            mask = torch.ones(B, T, dtype=torch.float, device=emissions.device)
        mask = mask.float()

        results: list[list[int]] = []
        for b in range(B):
            seq_len = int(mask[b].sum().item())
            emit = emissions[b, :seq_len].unsqueeze(0)
            alpha = self.start_transitions.unsqueeze(0) + emit[:, 0]
            backpointers: list[torch.Tensor] = []
            for t in range(1, seq_len):
                scores = alpha.unsqueeze(2) + self.transitions.unsqueeze(0) \
                    + emit[:, t].unsqueeze(1)
                best, idx = scores.max(dim=1)
                alpha = best
                backpointers.append(idx.squeeze(0))
            alpha = alpha + self.end_transitions.unsqueeze(0)
            # 回溯最优路径
            best_last = int(alpha.argmax(dim=1).item())
            path = [best_last]
            for bp in reversed(backpointers):
                best_last = int(bp[best_last].item())
                path.append(best_last)
            path.reverse()
            results.append(path)
        return results
