"""推理脚本: 输入文本 -> 抽取实体 -> 地理编码 -> 结构化输出。

三种使用方式:
  1. 单条文本快速推理 (演示用):
        python -m src.infer --text "求助! 汶川映秀镇3楼塌了, 有3个人, 急需水"
  2. 批量推理 (对全量原始数据, 导出结构化 CSV):
        python -m src.infer --batch
  3. 交互式推理 (输入一条返回一条):
        python -m src.infer --interactive

输出 CSV 字段:
  id | 原文 | 地点 | 人员 | 灾情 | 需求 | 紧急程度 | 经度 | 纬度 | 匹配地名
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.config import (
    BEST_CKPT_DIR, DEVICE, RAW_FILE, STRUCTURED_CSV, USE_CRF, ensure_dirs,
)


# ---- 模型加载缓存 ----
_MODEL = None
_TOKENIZER = None


def _load_model():
    """加载已训练的 BERT NER 模型 (惰性, 缓存)。"""
    global _MODEL, _TOKENIZER
    if _MODEL is not None:
        return _MODEL, _TOKENIZER
    from transformers import AutoTokenizer
    from src.models.bert_ner import BertNER

    if not (BEST_CKPT_DIR / "pytorch_model.bin").exists():
        raise FileNotFoundError(
            f"未找到训练好的模型 {BEST_CKPT_DIR}, 请先运行 python -m src.train")

    # 读取训练配置中的 use_crf
    cfg_path = BEST_CKPT_DIR / "train_config.json"
    use_crf = USE_CRF
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
        use_crf = cfg.get("use_crf", USE_CRF)

    _TOKENIZER = AutoTokenizer.from_pretrained(str(BEST_CKPT_DIR))
    _MODEL = BertNER.load(BEST_CKPT_DIR, map_location=DEVICE, use_crf=use_crf)
    _MODEL.to(DEVICE)
    _MODEL.eval()
    return _MODEL, _TOKENIZER


def infer_text(text: str) -> dict:
    """对单条文本推理, 返回结构化抽取结果。

    Returns:
        {
            "text": 原文,
            "entities": [{"type","text"}, ...],
            "location": 合并地点,
            "person": 合并人员,
            "disaster": 合并灾情,
            "need": 合并需求,
            "geo": {"lng","lat","matched","source"} 或 None,
        }
    """
    from src.config import MAX_LEN
    from src.models.bert_ner import tags_to_entities
    model, tokenizer = _load_model()

    # 字符级 tokenize (return_tensors 拿不到 word_ids, 需要再调一次无 tensor 版本)
    chars = list(text)
    encoding = tokenizer(chars, is_split_into_words=True,
                         max_length=MAX_LEN, truncation=True,
                         return_tensors="pt")
    encoding = {k: v.to(DEVICE) for k, v in encoding.items()}

    # model.decode 内部已经跳过了 [CLS]/[SEP]/[PAD], 返回的序列长度 = 字符数
    pred_ids = model.decode(encoding["input_ids"], encoding["attention_mask"],
                            encoding.get("token_type_ids"))[0]

    # 关键修复: pred_ids 已经和"原始字符"一一对应 (decode 跳过了特殊符号)
    # 但要处理 BERT 把单个字符拆成多个 sub-token 的情况 (用 word_ids 重建)
    # 注意 decode 返回的长度 = 去掉首尾特殊符号后的 sub-token 数,
    # 需要重新和 word_ids (同样去掉 None) 对齐。
    plain = tokenizer(chars, is_split_into_words=True,
                      max_length=MAX_LEN, truncation=True)
    word_ids = plain.word_ids()
    # 去掉 word_ids 中的 None 位置 ([CLS]/[SEP]/[PAD])
    real_word_ids = [w for w in word_ids if w is not None]
    # 去掉首尾特殊符号对应的 word_id ([CLS] 的 word_id=None 已去掉,
    # [SEP] 的 word_id=None 已去掉; 剩下的就是 [字符] 的 sub-token 序列)
    # 但 [CLS] x1 [SEP] 中, word_ids=[None, 0, 1, 2, ..., n-1, None]
    # real_word_ids = [0, 1, ..., n-1] (每个字符, 若某字符被拆成多 token 则重复)
    # pred_ids 长度应 == len(real_word_ids)
    n_chars = len(chars)
    char_tags = [0] * n_chars   # 默认 O
    prev_wid = None
    for tid, wid in zip(pred_ids, real_word_ids):
        if wid == prev_wid:
            continue            # 同一字符的后续 sub-token, 跳过
        if wid < n_chars:
            char_tags[wid] = int(tid)
        prev_wid = wid

    # BIO 解码为实体
    ents_spans = tags_to_entities(char_tags)
    entities = []
    for sp in ents_spans:
        s, e = sp["start"], sp["end"]
        entities.append({"type": sp["type"], "text": text[s:e]})

    # 分类型聚合
    by_type = {"LOC": [], "PER": [], "DIS": [], "NEED": []}
    for e in entities:
        by_type[e["type"]].append(e["text"])

    # 地理编码 (用所有 LOC 文本组合)
    from src.geo.geocoder import Geocoder
    geo = Geocoder(verbose=False)
    loc_text = "".join(by_type["LOC"]) or text
    geo_result = geo.geocode(loc_text)

    return {
        "text": text,
        "entities": entities,
        "location": " / ".join(by_type["LOC"]),
        "person": " / ".join(by_type["PER"]),
        "disaster": " / ".join(by_type["DIS"]),
        "need": " / ".join(by_type["NEED"]),
        "geo": geo_result,
    }


def infer_urgency(text: str) -> str:
    """简单规则估算紧急程度 (演示用; 真实场景可训练分类模型)。"""
    if any(w in text for w in ["救命", "SOS", "十万火急", "急!!", "急！！",
                                 "撑不住", "急!!!", "急！！！"]):
        return "emergency"
    if any(w in text for w in ["紧急", "急!", "急！", "求救", "求助"]):
        return "high"
    return "medium"


def batch_infer(input_file: Path = RAW_FILE,
                output_file: Path = STRUCTURED_CSV) -> Path:
    """对 jsonl 数据批量推理并导出 CSV。"""
    ensure_dirs()
    samples = []
    with input_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"[1/2] 批量推理 {len(samples)} 条...")
    from tqdm import tqdm
    rows = []
    for s in tqdm(samples, ncols=80):
        r = infer_text(s["text"])
        urgency = s.get("urgency") or infer_urgency(s["text"])
        geo = r["geo"] or {}
        rows.append({
            "id": s.get("id", ""),
            "原文": s["text"],
            "地点": r["location"],
            "人员": r["person"],
            "灾情": r["disaster"],
            "需求": r["need"],
            "紧急程度": urgency,
            "经度": geo.get("lng", ""),
            "纬度": geo.get("lat", ""),
            "匹配地名": (geo.get("matched") or "") + f" [{geo.get('source','未定位')}]",
        })

    print(f"[2/2] 写出 -> {output_file}")
    fieldnames = ["id", "原文", "地点", "人员", "灾情", "需求",
                  "紧急程度", "经度", "纬度", "匹配地名"]
    with output_file.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    n_loc = sum(1 for r in rows if r["经度"] != "")
    print(f"\n[完成] 已结构化 {len(rows)} 条, 成功定位 {n_loc} 条 "
          f"({n_loc/len(rows)*100:.1f}%)")
    return output_file


def print_result(r: dict) -> None:
    print(f"\n原文: {r['text']}")
    print(f"实体: {[(e['type'], e['text']) for e in r['entities']]}")
    print(f"  地点 : {r['location'] or '(无)'}")
    print(f"  人员 : {r['person'] or '(无)'}")
    print(f"  灾情 : {r['disaster'] or '(无)'}")
    print(f"  需求 : {r['need'] or '(无)'}")
    g = r["geo"]
    if g:
        print(f"  定位 : ({g['lng']}, {g['lat']})  匹配={g['matched']}  来源={g['source']}")
    else:
        print(f"  定位 : (未定位)")


def main():
    p = argparse.ArgumentParser(description="NER 推理")
    p.add_argument("--text", type=str, default=None,
                   help="单条文本推理")
    p.add_argument("--batch", action="store_true",
                   help="对全量原始数据批量推理, 导出结构化 CSV")
    p.add_argument("--interactive", action="store_true",
                   help="交互式推理")
    args = p.parse_args()

    if args.batch:
        batch_infer()
        return

    if args.text:
        r = infer_text(args.text)
        print_result(r)
        return

    if args.interactive:
        print("交互式推理 (输入 quit 退出)")
        while True:
            try:
                text = input("\n>> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if text.lower() in ("quit", "exit", "q"):
                break
            if not text:
                continue
            r = infer_text(text)
            print_result(r)
        return

    # 默认: 演示几条样例
    demos = [
        "求助! 汶川映秀镇中心学校3楼塌了,我们一家三口困在里面,缺水和食物,电话13900001234",
        "郑州京广路隧道被淹,水深2米,我们一辆车4个人出不来,求救船只,电话13900001111",
        "新疆伊犁新源县发生6.6级地震,那拉提镇有8位老人需要帐篷和药品",
    ]
    print("="*60)
    print("演示推理 (3 条样本)")
    print("="*60)
    for t in demos:
        r = infer_text(t)
        print_result(r)


if __name__ == "__main__":
    main()
