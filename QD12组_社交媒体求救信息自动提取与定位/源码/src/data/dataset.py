"""PyTorch Dataset + Collate: 把 BIO 数据转成 BERT 输入张量。

每个样本: 字符级 tokens + BIO tags
-> BERT tokenizer (bert-base-chinese 按字切)
-> input_ids / attention_mask / token_type_ids / label_ids

特殊处理: 标签与 token 严格对齐 (用 word_ids 映射, 特殊符号位置 -100 忽略)。
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
from torch.utils.data import Dataset

from src.config import MAX_LEN, TAG2ID, BERT_MODEL_NAME


class NERDataset(Dataset):
    """字符级 NER 数据集。

    Args:
        path: jsonl 文件路径 (字段: tokens=[字], tags=[BIO])
        tokenizer: HuggingFace tokenizer (None 时按需加载)
        max_len: 最大长度
    """

    def __init__(self, path: str | Path, tokenizer=None, max_len: int = MAX_LEN):
        self.path = Path(path)
        self.max_len = max_len
        self.samples = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.samples.append(json.loads(line))
        if tokenizer is None:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(BERT_MODEL_NAME)
        self.tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict:
        s = self.samples[idx]
        tokens = s["tokens"]              # list[字]
        tags = s["tags"]                  # list[BIO]

        # 把字符级 token 用 tokenizer 编码 (is_split_into_words=True)
        encoding = self.tokenizer(
            tokens,
            is_split_into_words=True,
            max_length=self.max_len,
            truncation=True,
            padding=False,                # collate 时统一 padding
            return_offsets_mapping=False,
        )

        word_ids = encoding.word_ids()
        label_ids = []
        prev_wid = None
        for wid in word_ids:
            if wid is None:
                # [CLS] / [SEP] / [PAD] 位置 -> -100 忽略
                label_ids.append(-100)
            elif wid != prev_wid:
                # 每个原始字的第一个 sub-token 取 B- 标签
                tag = tags[wid]
                label_ids.append(TAG2ID.get(tag, 0))
            else:
                # 同一个字的后续 sub-token, 复用同一标签 (CRF 友好)
                tag = tags[wid]
                label_ids.append(TAG2ID.get(tag, 0))
            prev_wid = wid

        encoding["label_ids"] = label_ids
        return {k: torch.tensor(v, dtype=torch.long) for k, v in encoding.items()}


class Collater:
    """动态 padding collate: 把一个 batch 内的样本对齐到相同长度。"""

    def __init__(self, tokenizer, label_pad_id: int = -100):
        self.tokenizer = tokenizer
        self.label_pad_id = label_pad_id

    def __call__(self, batch: list[dict]) -> dict:
        # 找到本 batch 最大长度
        maxlen = max(len(x["input_ids"]) for x in batch)
        pad_id = self.tokenizer.pad_token_id or 0

        input_ids, attn, type_ids, labels = [], [], [], []
        for x in batch:
            n = len(x["input_ids"])
            pad_n = maxlen - n
            input_ids.append(torch.cat([x["input_ids"],
                                        torch.full((pad_n,), pad_id, dtype=torch.long)]))
            attn.append(torch.cat([x["attention_mask"],
                                   torch.zeros(pad_n, dtype=torch.long)]))
            if "token_type_ids" in x:
                type_ids.append(torch.cat([x["token_type_ids"],
                                           torch.zeros(pad_n, dtype=torch.long)]))
            labels.append(torch.cat([x["label_ids"],
                                     torch.full((pad_n,), self.label_pad_id, dtype=torch.long)]))

        out = {
            "input_ids": torch.stack(input_ids),
            "attention_mask": torch.stack(attn),
            "labels": torch.stack(labels),
        }
        if type_ids:
            out["token_type_ids"] = torch.stack(type_ids)
        return out


if __name__ == "__main__":
    # 自测
    from torch.utils.data import DataLoader
    from src.config import DEV_FILE

    ds = NERDataset(DEV_FILE)
    print(f"样本数: {len(ds)}")
    sample = ds[0]
    print(f"input_ids shape: {sample['input_ids'].shape}")
    print(f"label_ids : {sample['label_ids'].tolist()}")

    loader = DataLoader(ds, batch_size=4, collate_fn=Collater(ds.tokenizer))
    for batch in loader:
        print(f"batch input_ids: {batch['input_ids'].shape}")
        print(f"batch labels  : {batch['labels'].shape}")
        break
