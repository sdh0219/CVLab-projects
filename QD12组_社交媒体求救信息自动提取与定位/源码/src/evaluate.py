"""评估指标: 实体级 P/R/F1 + 分标签指标 + 混淆矩阵 + bad case。

使用 seqeval 做严格的实体级评估 (一个实体被判正确当且仅当
类型和边界完全匹配)。

输入: golds/preds 都是 list[list[tag_id]]
输出: {
    "precision", "recall", "f1",                    # 总体
    "per_type": {类型: {"P","R","F1","support"}},   # 分类型
    "support": 实体总数,
}
"""
from __future__ import annotations

import json
from collections import defaultdict

from src.config import ENTITY_TYPES, ID2TAG


def _to_bio_str(tag_ids: list[int]) -> list[str]:
    """把 tag id 列表转为 BIO 字符串列表。"""
    return [ID2TAG.get(int(t), "O") for t in tag_ids]


def extract_entities(tag_strs: list[str]) -> list[tuple[str, int, int]]:
    """从 BIO 字符串序列中抽取实体 (type, start, end)。end exclusive。"""
    ents = []
    cur_type, cur_start = None, -1
    for i, tag in enumerate(tag_strs):
        if tag == "O":
            if cur_type is not None:
                ents.append((cur_type, cur_start, i))
                cur_type = None
        else:
            prefix, etype = tag.split("-", 1)
            if prefix == "B" or cur_type != etype:
                if cur_type is not None:
                    ents.append((cur_type, cur_start, i))
                cur_type, cur_start = etype, i
    if cur_type is not None:
        ents.append((cur_type, cur_start, len(tag_strs)))
    return ents


def compute_metrics(pred_ids: list[list[int]],
                    gold_ids: list[list[int]]) -> dict:
    """计算实体级 P/R/F1。"""
    try:
        from seqeval.metrics import classification_report
        from seqeval.scheme import IOB2
    except ImportError:
        return _fallback_metrics(pred_ids, gold_ids)

    assert len(pred_ids) == len(gold_ids)
    preds_str = [_to_bio_str(p) for p in pred_ids]
    golds_str = [_to_bio_str(g) for g in gold_ids]

    report = classification_report(golds_str, preds_str,
                                   output_dict=True, mode="strict",
                                   scheme=IOB2, zero_division=0)

    # 整体 micro (seqeval 用 'f1-score' 键)
    overall = report.get("micro avg",
                         {"precision": 0, "recall": 0, "f1-score": 0})
    per_type = {}
    for etype in ENTITY_TYPES:
        if etype in report:
            r = report[etype]
            per_type[etype] = {
                "P": r["precision"], "R": r["recall"],
                "F1": r["f1-score"], "support": r["support"],
            }
        else:
            per_type[etype] = {"P": 0, "R": 0, "F1": 0, "support": 0}

    return {
        "precision": overall["precision"],
        "recall": overall["recall"],
        "f1": overall["f1-score"],
        "per_type": per_type,
        "support": sum(per_type[t]["support"] for t in ENTITY_TYPES),
    }


def _fallback_metrics(pred_ids, gold_ids) -> dict:
    """seqeval 不可用时的简单实现 (不严格, 仅兜底)。"""
    tp = fp = fn = 0
    per_tp = defaultdict(int); per_fp = defaultdict(int); per_fn = defaultdict(int)
    per_sup = defaultdict(int)
    for p, g in zip(pred_ids, gold_ids):
        p_str, g_str = _to_bio_str(p), _to_bio_str(g)
        p_ents = set(extract_entities(p_str))
        g_ents = set(extract_entities(g_str))
        for e in g_ents:
            per_sup[e[0]] += 1
        for e in p_ents:
            if e in g_ents:
                tp += 1; per_tp[e[0]] += 1
            else:
                fp += 1; per_fp[e[0]] += 1
        for e in g_ents:
            if e not in p_ents:
                fn += 1; per_fn[e[0]] += 1
    P = tp / (tp + fp) if (tp + fp) else 0
    R = tp / (tp + fn) if (tp + fn) else 0
    F = 2 * P * R / (P + R) if (P + R) else 0
    per_type = {}
    for t in ENTITY_TYPES:
        p = per_tp[t] / (per_tp[t] + per_fp[t]) if (per_tp[t] + per_fp[t]) else 0
        r = per_tp[t] / (per_tp[t] + per_fn[t]) if (per_tp[t] + per_fn[t]) else 0
        f = 2 * p * r / (p + r) if (p + r) else 0
        per_type[t] = {"P": p, "R": r, "F1": f, "support": per_sup[t]}
    return {"precision": P, "recall": R, "f1": F, "per_type": per_type,
            "support": sum(per_sup.values())}


def format_report(metrics: dict, model_name: str = "Model") -> str:
    """把指标格式化为表格字符串 (用于打印 / 写入报告)。"""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"{model_name} 实体级评估结果")
    lines.append(f"{'='*60}")
    lines.append(f"  整体 Precision : {metrics['precision']:.4f}")
    lines.append(f"  整体 Recall    : {metrics['recall']:.4f}")
    lines.append(f"  整体 F1        : {metrics['f1']:.4f}")
    lines.append(f"  实体总数       : {metrics['support']}")
    lines.append(f"  {'-'*54}")
    lines.append(f"  {'类型':<8}{'P':>10}{'R':>10}{'F1':>10}{'support':>10}")
    for t in ENTITY_TYPES:
        m = metrics["per_type"].get(t, {"P": 0, "R": 0, "F1": 0, "support": 0})
        lines.append(f"  {t:<8}{m['P']:>10.4f}{m['R']:>10.4f}"
                     f"{m['F1']:>10.4f}{m['support']:>10}")
    lines.append(f"{'='*60}")
    return "\n".join(lines)


# ==================================================================
# 命令行入口: 评估训练好的 BERT 模型, 写出 metrics.json + badcase.txt
# ==================================================================
def run_eval() -> dict:
    """对 test 集评估 BERT 模型, 同时输出规则基线对比。"""
    import json as _json
    from torch.utils.data import DataLoader
    from src.config import (BEST_CKPT_DIR, BADCASE_FILE, DEVICE, EVAL_BATCH,
                            METRICS_FILE, TEST_FILE, USE_CRF)
    from src.data.dataset import Collater, NERDataset
    from src.data.annotate import load_jsonl

    # ---- 加载模型 ----
    from transformers import AutoTokenizer
    from src.models.bert_ner import BertNER

    use_crf = USE_CRF
    cfg = BEST_CKPT_DIR / "train_config.json"
    if cfg.exists():
        use_crf = _json.loads(cfg.read_text(encoding="utf-8")).get("use_crf", USE_CRF)

    tokenizer = AutoTokenizer.from_pretrained(str(BEST_CKPT_DIR))
    model = BertNER.load(BEST_CKPT_DIR, map_location=DEVICE, use_crf=use_crf).to(DEVICE)
    model.eval()

    test_ds = NERDataset(TEST_FILE, tokenizer)
    loader = DataLoader(test_ds, batch_size=EVAL_BATCH,
                        collate_fn=Collater(tokenizer))

    # ---- BERT 预测 ----
    from src.config import TAG2ID
    all_preds, all_golds, samples_text = [], [], []
    for batch in loader:
        batch = {k: v.to(DEVICE) for k, v in batch.items()}
        preds = model.decode(batch["input_ids"], batch["attention_mask"],
                             batch.get("token_type_ids"))
        for i, p in enumerate(preds):
            gold_ids = batch["labels"][i].tolist()
            gold_seq = [g for g in gold_ids if g != -100]
            n = min(len(p), len(gold_seq))
            all_preds.append(p[:n])
            all_golds.append(gold_seq[:n])

    bert_metrics = compute_metrics(all_preds, all_golds)

    # ---- 规则基线 ----
    from src.baselines.rule_based import RuleBasedNER
    rb = RuleBasedNER()
    rule_preds, rule_golds = [], []
    for s in load_jsonl(TEST_FILE):
        tags = rb.extract_to_tags(s["text"])
        n = min(len(tags), len(s["tags"]))
        rule_preds.append([TAG2ID.get(t, 0) for t in tags[:n]])
        rule_golds.append([TAG2ID.get(t, 0) for t in s["tags"][:n]])
    rule_metrics = compute_metrics(rule_preds, rule_golds)

    # ---- 打印对比 ----
    print(format_report(bert_metrics, "BERT NER (深度学习)"))
    print(format_report(rule_metrics, "规则基线 (Rule-based)"))

    # ---- 保存 metrics.json ----
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "bert": bert_metrics,
        "rule_based": rule_metrics,
        "model": str(BEST_CKPT_DIR),
        "use_crf": use_crf,
    }

    def _to_native(obj):
        """递归把 numpy 类型转为 Python 原生类型 (JSON 序列化兼容)。"""
        import numpy as _np
        if isinstance(obj, dict):
            return {k: _to_native(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_to_native(x) for x in obj]
        if isinstance(obj, _np.integer):
            return int(obj)
        if isinstance(obj, _np.floating):
            return float(obj)
        return obj

    with METRICS_FILE.open("w", encoding="utf-8") as f:
        _json.dump(_to_native(out), f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 指标已保存 -> {METRICS_FILE}")

    # ---- Bad case 报告 ----
    samples = load_jsonl(TEST_FILE)
    bad_lines = ["=" * 60, "Bad Cases (BERT 预测与 gold 不一致的样本)",
                 "=" * 60]
    n_bad = 0
    for s, pred, gold in zip(samples, all_preds, all_golds):
        if pred != gold:
            n_bad += 1
            pred_str = "".join(ID2TAG.get(int(t), "O")[0] if ID2TAG.get(int(t), "O") != "O" else "·"
                                for t in pred)
            gold_str = "".join(ID2TAG.get(int(t), "O")[0] if ID2TAG.get(int(t), "O") != "O" else "·"
                                for t in gold)
            bad_lines.append(f"\n[{n_bad}] {s['text']}")
            bad_lines.append(f"  gold: {gold_str}")
            bad_lines.append(f"  pred: {pred_str}")
            if n_bad >= 20:  # 最多 20 条
                bad_lines.append("\n... (仅显示前 20 条)")
                break
    with BADCASE_FILE.open("w", encoding="utf-8") as f:
        f.write("\n".join(bad_lines))
    print(f"[OK] Bad case 报告 -> {BADCASE_FILE} ({n_bad} 条不一致)")

    return out


if __name__ == "__main__":
    run_eval()
