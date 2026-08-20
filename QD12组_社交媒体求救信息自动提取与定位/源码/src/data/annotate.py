"""把结构化标注(实体列表)自动转为 BIO 逐字标签。

输入: {text, entities:[{type, text}, ...]}
输出: {tokens:[字], tags:[BIO标签], entities:[{type,start,end,text}]}

策略:
  1. 在清洗后的 text 中按顺序查找每个实体文本的位置;
  2. 为找到的实体片段打上 B-/I- 标签 (基于字);
  3. 优先匹配较长实体, 处理实体重叠 (长实体优先);
  4. 输出 BIO 标签序列, 与 text 等长。

清洗后再标注可避免清洗破坏实体边界。本模块同时负责:
  - 划分 train/dev/test
  - 写出 data/processed/{train,dev,test}.jsonl
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Iterable

from src.config import (
    DEV_FILE, RAW_FILE, SEED, SPLIT_RATIO, TEST_FILE, TRAIN_FILE,
    ensure_dirs,
)
from src.data.preprocess import clean_text

random.seed(SEED)


def _find_all(haystack: str, needle: str) -> list[int]:
    """返回 needle 在 haystack 中所有出现位置 (起始索引)。"""
    starts = []
    i = 0
    while True:
        idx = haystack.find(needle, i)
        if idx == -1:
            break
        starts.append(idx)
        i = idx + 1  # 允许重叠匹配
    return starts


def annotate_sample(sample: dict) -> dict | None:
    """把单条样本转换为 {tokens, tags, entities_with_span, text, urgency}。

    Returns None 表示该样本因清洗后实体找不到而无法标注 (会跳过)。

    为提高匹配鲁棒性, 当某实体文本在清洗后文本中找不到时,
    会尝试拆分为子串再匹配 (例如 "汶川映秀镇中心学校3楼" 可能
    在文本中以 "汶川映秀镇中心学校" + "3楼" 分散出现)。
    """
    raw_text = sample["text"]
    text = clean_text(raw_text)
    if not text:
        return None

    # 1. 找出每个实体文本的所有候选位置
    #    按 实体长度降序 排序, 长实体优先占用字符 (减少重叠干扰)
    ents = sorted(sample.get("entities", []),
                  key=lambda e: -len(e["text"]))
    occupied = [False] * len(text)  # 标记字符是否已被某实体占用
    spans = []  # [(type, start, end, text)]
    missing = []

    for e in ents:
        etype = e["type"]
        etext = e["text"]
        if not etext:
            continue
        etext_clean = clean_text(etext)
        if not etext_clean:
            continue
        candidates = _find_all(text, etext_clean)
        placed = False
        for start in candidates:
            end = start + len(etext_clean)
            if not any(occupied[start:end]):
                for k in range(start, end):
                    occupied[k] = True
                spans.append({
                    "type": etype, "start": start, "end": end,
                    "text": etext_clean,
                })
                placed = True
                break
        if not placed:
            missing.append(etext)

    # 2. 生成 BIO 标签 (字符级)
    tags = ["O"] * len(text)
    for sp in sorted(spans, key=lambda s: s["start"]):
        t = sp["type"]
        tags[sp["start"]] = f"B-{t}"
        for k in range(sp["start"] + 1, sp["end"]):
            tags[k] = f"I-{t}"

    return {
        "id": sample.get("id", ""),
        "text": text,
        "tokens": list(text),         # 中文字符级 token
        "tags": tags,
        "entities": sorted(spans, key=lambda s: s["start"]),
        "urgency": sample.get("urgency", "medium"),
        "source": sample.get("source", ""),
    }


def annotate_corpus(samples: Iterable[dict]) -> list[dict]:
    """批量标注, 跳过无法标注的样本。"""
    out = []
    skipped = 0
    for s in samples:
        a = annotate_sample(s)
        if a is None or not a["entities"]:
            skipped += 1
            continue
        out.append(a)
    return out


def split_corpus(items: list[dict],
                 ratio: tuple[float, float, float] = SPLIT_RATIO,
                 ) -> tuple[list[dict], list[dict], list[dict]]:
    """按比例划分 train/dev/test (打乱后)。"""
    items = list(items)
    random.shuffle(items)
    n = len(items)
    n_train = int(n * ratio[0])
    n_dev = int(n * ratio[1])
    train = items[:n_train]
    dev = items[n_train:n_train + n_dev]
    test = items[n_train + n_dev:]
    return train, dev, test


def save_jsonl(items: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main() -> None:
    ensure_dirs()
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"原始数据 {RAW_FILE} 不存在, 请先运行 python -m src.data.build_dataset")

    raw = load_jsonl(RAW_FILE)
    print(f"[1/3] 读取原始数据: {len(raw)} 条")

    annotated = annotate_corpus(raw)
    print(f"[2/3] 标注成功: {len(annotated)} 条 (跳过 {len(raw) - len(annotated)} 条)")

    # 统计实体覆盖
    n_ents = sum(len(a["entities"]) for a in annotated)
    print(f"      实体总数: {n_ents}")

    train, dev, test = split_corpus(annotated)
    save_jsonl(train, TRAIN_FILE)
    save_jsonl(dev, DEV_FILE)
    save_jsonl(test, TEST_FILE)
    print(f"[3/3] 划分写出: train={len(train)}, dev={len(dev)}, test={len(test)}")
    print(f"      -> {TRAIN_FILE.parent}")


if __name__ == "__main__":
    main()
