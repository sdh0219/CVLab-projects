"""BERT NER 模型: bert-base-chinese + Linear (+ 可选 CRF)。

结构:
    输入字符 → BERT(12 层 Transformer) → Dropout → Linear(768→9) → [CRF] → BIO 标签

    - 不带 CRF: 损失 = CrossEntropy(ignore_index=-100); 推理 = argmax
    - 带   CRF: 损失 = CRF 负对数似然;        推理 = Viterbi 解码
"""
from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn

from src.config import (
    BERT_MODEL_NAME, ID2TAG, NUM_TAGS, USE_CRF,
)
from src.models.crf import CRF


class BertNER(nn.Module):
    """BERT + 线性分类头 (+ 可选 CRF)。"""

    def __init__(self, num_tags: int = NUM_TAGS,
                 model_name: str = BERT_MODEL_NAME,
                 use_crf: bool = USE_CRF):
        super().__init__()
        from transformers import AutoModel

        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(0.1)
        self.classifier = nn.Linear(self.bert.config.hidden_size, num_tags)
        self.use_crf = use_crf
        self.num_tags = num_tags
        if use_crf:
            self.crf = CRF(num_tags, batch_first=True)

    # ------------------------------------------------------------------
    # 前向
    # ------------------------------------------------------------------
    def emit(self, input_ids, attention_mask,
             token_type_ids=None) -> torch.Tensor:
        """BERT + 分类头, 返回每个位置的发射分数 [B, T, num_tags]。"""
        kwargs = {"input_ids": input_ids, "attention_mask": attention_mask}
        if token_type_ids is not None:
            kwargs["token_type_ids"] = token_type_ids
        hidden = self.bert(**kwargs).last_hidden_state
        return self.classifier(self.dropout(hidden))

    def loss(self, input_ids, attention_mask, labels,
             token_type_ids=None) -> torch.Tensor:
        """训练损失。labels 中 -100 表示忽略位置 ([CLS]/[SEP]/[PAD])。"""
        emissions = self.emit(input_ids, attention_mask, token_type_ids)

        if self.use_crf:
            # CRF 不接受 -100: 临时替换为有效标签, 并用 mask 屏蔽这些位置
            crf_labels = labels.clone()
            crf_labels[crf_labels == -100] = 0
            mask = (labels != -100).float()
            log_likelihood = self.crf(emissions, crf_labels, mask=mask)
            return -log_likelihood.mean()

        loss_fn = nn.CrossEntropyLoss(ignore_index=-100)
        B, T, C = emissions.shape
        return loss_fn(emissions.view(-1, C), labels.view(-1))

    # ------------------------------------------------------------------
    # 推理
    # ------------------------------------------------------------------
    @torch.no_grad()
    def decode(self, input_ids, attention_mask,
               token_type_ids=None) -> list[list[int]]:
        """返回每个样本的标签 id 序列 (已去除 [CLS]/[SEP]/[PAD])。

        与 gold labels 对齐: labels 中 [CLS]/[SEP]/[PAD] 位置均为 -100,
        因此本方法也跳过位置 0 ([CLS]) 和最后一个有效位置 ([SEP])。
        """
        emissions = self.emit(input_ids, attention_mask, token_type_ids)
        B = emissions.size(0)

        if self.use_crf:
            raw = self.crf.decode(emissions, attention_mask.float())
            # CRF decode 返回含 [CLS]/[SEP] 的序列, 去掉首尾
            return [seq[1:-1] if len(seq) >= 2 else seq for seq in raw]

        preds = emissions.argmax(dim=-1)
        results = []
        for i in range(B):
            L = int(attention_mask[i].sum().item())
            # 跳过位置 0 ([CLS]) 和位置 L-1 ([SEP])
            results.append(preds[i, 1:L - 1].tolist())
        return results

    # ------------------------------------------------------------------
    # 保存 / 加载
    # ------------------------------------------------------------------
    def save(self, path: str | Path) -> None:
        """保存模型权重。tokenizer 由调用方负责保存。"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        torch.save(self.state_dict(), path / "pytorch_model.bin")

    @classmethod
    def load(cls, path: str | Path, map_location="cpu",
             use_crf: bool | None = None) -> "BertNER":
        """从目录加载模型。use_crf 默认取 config.USE_CRF。"""
        if use_crf is None:
            use_crf = USE_CRF
        model = cls(use_crf=use_crf)
        state = torch.load(Path(path) / "pytorch_model.bin",
                           map_location=map_location, weights_only=True)
        model.load_state_dict(state)
        model.eval()
        return model


# ======================================================================
# BIO 解码工具
# ======================================================================
def tags_to_entities(tag_ids: list[int], id2tag: dict = ID2TAG) -> list[dict]:
    """把标签 id 序列解码为实体列表。

    Returns:
        [{"type": "LOC", "start": 4, "end": 9}, ...]
        end 为 exclusive (切片风格), 调用方用 text[start:end] 取实体文本。
    """
    entities: list[dict] = []
    cur: dict | None = None  # 正在拼接的实体: {"type", "start"}

    for i, tid in enumerate(tag_ids):
        tag = id2tag.get(int(tid), "O")
        if tag == "O":
            if cur is not None:
                entities.append({**cur, "end": i})
                cur = None
            continue

        prefix, etype = tag.split("-", 1)
        # 新实体: B- 开头, 或类型变化, 或前一个是 O
        if prefix == "B" or cur is None or cur["type"] != etype:
            if cur is not None:
                entities.append({**cur, "end": i})
            cur = {"type": etype, "start": i}
        # I- 且类型一致: 继续 cur, 无操作

    if cur is not None:
        entities.append({**cur, "end": len(tag_ids)})
    return entities
