"""LLM Few-shot NER: 用通义千问 (Qwen) 大语言模型做命名实体识别。

与 BERT+CRF 微调形成对比 (提示工程 vs 微调):
  - BERT+CRF: 288 条标注数据训练, 本地推理
  - LLM few-shot: 零训练, 给几个示例 prompt, API 推理

支持 3 种 prompt 策略:
  - zero-shot: 只给任务说明, 不给示例
  - 1-shot:    给 1 个示例
  - 3-shot:    给 3 个示例 (推荐)

用法:
    # 单条推理
    python -m src.baselines.llm_ner --text "急!郑州京广路隧道被淹..."

    # 在测试集上评估 (需要 DASHSCOPE_API_KEY)
    python -m src.baselines.llm_ner --evaluate --shots 3

环境变量:
    DASHSCOPE_API_KEY  阿里云百炼 API Key (https://bailian.console.aliyun.com/)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from src.config import ENTITY_TYPES, TEST_FILE


# ==================================================================
# Prompt 设计 (v2: 强调原样摘录, 禁止改写)
# ==================================================================

SYSTEM_PROMPT = """你是一个命名实体识别(NER)标注员。你的唯一任务是从求救文本中**逐字摘录**实体片段,不做任何改写、概括、补充或翻译。

需要提取的 4 类实体:

- LOC(地点):求救发生的位置。包括地名和具体场所。如「汶川映秀镇」「郑州京广路隧道」「地下车库」「3楼」
- PER(人员):受困/受灾人员的完整描述,包括前缀词。如「有6个老人」「我们一家三口」「有老人和小孩共12人」
- DIS(灾情):灾害状况的原文描述。如「房子塌了」「水深2米」「6.6级地震」「积水2米深」
- NEED(需求):物资/救援需求及联系电话,保留原文前缀。如「急需饮用水」「电话13900001234」「手机18600001111」

关键规则(必须严格遵守):
1. 实体必须是原文中连续出现的字串,逐字复制,不能改动任何一个字
2. PER 实体要包含「有」「我们」等前缀词,如原文是"有6个老人",实体就是「有6个老人」,不是「6个老人」
3. NEED 中的电话要包含「电话」「手机」「联系」等前缀词,如原文是"电话13900001234",实体就是「电话13900001234」
4. DIS 实体保留完整的灾害描述,如「积水2米深」不要缩写成「积水」
5. 一条文本中同一类型可能有多个实体,全部提取
6. 如果某类实体不存在,对应值为空数组 []
7. 输出严格的 JSON 格式,不要添加任何解释文字"""


# Few-shot 示例 (v2: 边界与 gold 标注完全一致)
FEW_SHOT_EXAMPLES = [
    {
        "input": "救命啊!汶川映秀镇中心学校3楼塌了,我们一家三口困在里面,缺水和食物,电话13900001234",
        "output": {
            "LOC": ["汶川映秀镇中心学校3楼"],
            "PER": ["我们一家三口"],
            "DIS": ["塌了"],
            "NEED": ["水和食物", "电话13900001234"],
        }
    },
    {
        "input": "急!郑州京广路隧道被淹,水深2米,我们一辆车4个人出不来,求救船只,电话13900001111",
        "output": {
            "LOC": ["郑州京广路隧道"],
            "PER": ["我们一辆车4个人"],
            "DIS": ["被淹", "水深2米"],
            "NEED": ["船只", "电话13900001111"],
        }
    },
    {
        "input": "舟曲县城特大泥石流,城关镇房屋被埋,有30多人被困,急需挖掘设备和救援,电话13900004444",
        "output": {
            "LOC": ["舟曲县城", "城关镇"],
            "PER": ["有30多人"],
            "DIS": ["特大泥石流", "房屋被埋"],
            "NEED": ["挖掘设备", "救援", "电话13900004444"],
        }
    },
]


def build_prompt(text: str, n_shots: int = 3) -> list[dict]:
    """构建通义千问 messages (system + user)。"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    user_parts = []
    if n_shots > 0:
        examples = FEW_SHOT_EXAMPLES[:n_shots]
        for ex in examples:
            user_parts.append(f"输入:{ex['input']}")
            user_parts.append(f"输出:{json.dumps(ex['output'], ensure_ascii=False)}")
            user_parts.append("")

    user_parts.append(f"输入:{text}")
    user_parts.append("输出:")
    messages.append({"role": "user", "content": "\n".join(user_parts)})
    return messages


# ==================================================================
# 调用通义千问 API
# ==================================================================

def call_qwen(messages: list[dict],
              model: str = "qwen-plus",
              temperature: float = 0.1) -> str:
    """调用通义千问 API, 返回文本响应。"""
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "未设置 DASHSCOPE_API_KEY, 请到 https://bailian.console.aliyun.com/ 申请")

    import dashscope
    dashscope.api_key = api_key

    response = dashscope.Generation.call(
        model=model,
        messages=messages,
        temperature=temperature,
        result_format="message",
        response_format={'type': 'json_object'},
    )

    if response.status_code != 200:
        raise RuntimeError(f"API 调用失败: {response.code} - {response.message}")

    return response.output.choices[0].message.content


# ==================================================================
# 解析 LLM 输出
# ==================================================================

def parse_llm_output(raw: str) -> list[dict]:
    """把 LLM 输出的文本解析为实体列表 [{type, text}]。"""
    entities = []

    # 方法 1: 找 {...} 块
    json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
    if not json_match:
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})```', raw, re.DOTALL)

    if json_match:
        try:
            json_str = json_match.group(0) if json_match.group(0).startswith('{') else json_match.group(1)
            data = json.loads(json_str)
            for etype in ENTITY_TYPES:
                items = data.get(etype, [])
                if isinstance(items, str):
                    items = [items]
                for item in items:
                    entities.append({"type": etype, "text": item})
        except (json.JSONDecodeError, KeyError):
            pass

    # 方法 2: 正则回退
    if not entities:
        for etype in ENTITY_TYPES:
            pattern = rf'"{etype}"\s*:\s*\["([^"]+)"'
            for m in re.finditer(pattern, raw):
                entities.append({"type": etype, "text": m.group(1)})

    return entities


# ==================================================================
# 实体 -> BIO 标签
# ==================================================================

def entities_to_bio(entities: list[dict], text: str) -> list[str]:
    """把实体列表转为 BIO 标签序列 (与 text 等长)。"""
    tags = ["O"] * len(text)
    occupied = [False] * len(text)
    for e in sorted(entities, key=lambda x: -len(x["text"])):
        etext = e["text"]
        idx = text.find(etext)
        while idx != -1:
            end = idx + len(etext)
            if end <= len(text) and not any(occupied[idx:end]):
                for k in range(idx, end):
                    occupied[k] = True
                tags[idx] = f"B-{e['type']}"
                for k in range(idx + 1, end):
                    tags[k] = f"I-{e['type']}"
                break
            idx = text.find(etext, idx + 1)
    return tags


# ==================================================================
# 单条推理
# ==================================================================

def infer_llm(text: str, n_shots: int = 3,
              model: str = "qwen-plus") -> dict:
    """对单条文本做 LLM few-shot NER 推理。"""
    messages = build_prompt(text, n_shots)
    raw_output = call_qwen(messages, model=model)
    entities = parse_llm_output(raw_output)
    bio_tags = entities_to_bio(entities, text)
    return {
        "text": text,
        "entities": entities,
        "bio_tags": bio_tags,
        "raw_llm_output": raw_output,
    }


def print_result(r: dict) -> None:
    print(f"\n原文: {r['text']}")
    print(f"实体: {[(e['type'], e['text']) for e in r['entities']]}")
    for etype in ENTITY_TYPES:
        ents = [e["text"] for e in r["entities"] if e["type"] == etype]
        if ents:
            print(f"  {etype:6s}: {' / '.join(ents)}")


# ==================================================================
# 批量评估 (保存完整原始回复 + 错误分析)
# ==================================================================

def evaluate_on_test(n_shots: int = 3, model: str = "qwen-plus",
                     max_samples: int | None = None,
                     save_raw: bool = True) -> dict:
    """在测试集上评估 LLM few-shot NER。

    Args:
        save_raw: 是否保存每条的原始 LLM 回复 (用于错误分析)
    Returns:
        metrics dict (与 BERT 评估格式一致)
    """
    from src.data.annotate import load_jsonl
    from src.evaluate import compute_metrics
    from src.config import TAG2ID, REPORTS_DIR

    samples = load_jsonl(TEST_FILE)
    if max_samples:
        samples = samples[:max_samples]

    print(f"[LLM NER] 评估: {len(samples)} 条, shots={n_shots}, model={model}")
    print(f"          (每条约 1-3 秒 API 调用, 请耐心等待)")

    all_preds, all_golds = [], []
    all_details = []  # 保存每条的完整信息

    for i, s in enumerate(samples):
        text = s["text"]
        gold_tags = s["tags"]
        gold_ids = [TAG2ID.get(t, 0) for t in gold_tags]

        raw_output = ""
        pred_tags = ["O"] * len(text)
        pred_entities = []

        try:
            r = infer_llm(text, n_shots=n_shots, model=model)
            pred_tags = r["bio_tags"]
            pred_entities = r["entities"]
            raw_output = r["raw_llm_output"]
        except Exception as e:
            print(f"  [{i+1}] API 错误: {e}, 跳过")

        pred_ids = [TAG2ID.get(t, 0) for t in pred_tags]
        n = min(len(pred_ids), len(gold_ids))
        all_preds.append(pred_ids[:n])
        all_golds.append(gold_ids[:n])

        # 保存完整细节
        detail = {
            "id": s.get("id", ""),
            "text": text,
            "gold_entities": [(e["type"], e["text"]) for e in s.get("entities", [])],
            "pred_entities": [(e["type"], e["text"]) for e in pred_entities],
            "raw_llm_output": raw_output,
            "match": pred_tags == gold_tags,
        }
        all_details.append(detail)

        if (i + 1) % 10 == 0:
            print(f"  进度: {i+1}/{len(samples)}")
        time.sleep(0.5)

    metrics = compute_metrics(all_preds, all_golds)

    # 保存原始回复 + 错误分析
    if save_raw:
        _save_analysis(metrics, all_details, n_shots, model, REPORTS_DIR)

    return metrics


def _save_analysis(metrics: dict, details: list[dict],
                   n_shots: int, model: str, reports_dir: Path) -> None:
    """保存完整的原始回复和错误分析报告。"""
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. 保存完整细节 (JSON)
    raw_file = reports_dir / f"llm_ner_raw_{n_shots}shot.json"
    payload = {
        "config": {"shots": n_shots, "model": model},
        "metrics": metrics,
        "n_samples": len(details),
        "details": details,
    }

    def _to_native(obj):
        """递归转 numpy 类型为原生类型。"""
        try:
            import numpy as np
        except ImportError:
            return obj
        if isinstance(obj, dict):
            return {k: _to_native(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_to_native(x) for x in obj]
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return obj

    raw_file.write_text(
        json.dumps(_to_native(payload), ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"  原始回复已保存: {raw_file}")

    # 2. 错误分析报告 (文本)
    badcases = [d for d in details if not d["match"]]
    report_file = reports_dir / f"llm_ner_badcase_{n_shots}shot.txt"
    lines = [f"{'='*60}", f"LLM NER Bad Case 分析 ({n_shots}-shot, {model})",
             f"总样本: {len(details)}, 错误: {len(badcases)}",
             f"F1: {metrics['f1']:.4f}", f"{'='*60}"]

    for idx, d in enumerate(badcases[:20]):  # 最多 20 条
        gold_set = set(tuple(e) for e in d["gold_entities"])
        pred_set = set(tuple(e) for e in d["pred_entities"])
        missed = gold_set - pred_set
        extra = pred_set - gold_set
        lines.append(f"\n[{idx+1}] {d['text'][:70]}")
        lines.append(f"  Gold: {sorted(gold_set)}")
        lines.append(f"  Pred: {sorted(pred_set)}")
        if missed:
            lines.append(f"  漏抽: {sorted(missed)}")
        if extra:
            lines.append(f"  多抽: {sorted(extra)}")
        if d["raw_llm_output"]:
            lines.append(f"  LLM原始输出: {d['raw_llm_output'][:200]}")

    report_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"  错误分析已保存: {report_file}")


# ==================================================================
# 命令行入口
# ==================================================================

def main():
    p = argparse.ArgumentParser(description="LLM Few-shot NER (通义千问)")
    p.add_argument("--text", type=str, help="单条文本推理")
    p.add_argument("--evaluate", action="store_true", help="在测试集上评估")
    p.add_argument("--shots", type=int, default=3, choices=[0, 1, 3],
                   help="few-shot 示例数 (0=zero-shot)")
    p.add_argument("--model", type=str, default="qwen-plus",
                   help="模型名 (qwen-plus / qwen-turbo / qwen-max)")
    p.add_argument("--max-samples", type=int, default=None,
                   help="评估时最多用多少条 (调试用)")
    args = p.parse_args()

    if args.evaluate:
        m = evaluate_on_test(n_shots=args.shots, model=args.model,
                             max_samples=args.max_samples)
        print(f"\n{'='*60}")
        print(f"LLM Few-shot NER 评估结果 ({args.shots}-shot, {args.model})")
        print(f"{'='*60}")
        print(f"  Precision: {m['precision']:.4f}")
        print(f"  Recall:    {m['recall']:.4f}")
        print(f"  F1:        {m['f1']:.4f}")
        print(f"  分类型:")
        for t in ENTITY_TYPES:
            mt = m["per_type"].get(t, {"F1": 0, "support": 0})
            print(f"    {t:6s}: F1={mt['F1']:.4f}  support={mt['support']}")
        return

    if args.text:
        r = infer_llm(args.text, n_shots=args.shots, model=args.model)
        print_result(r)
        return

    # 默认: 演示 3 条
    demos = [
        "急!郑州京广路隧道被淹,水深2米,我们一辆车4个人出不来,求救船只,电话13900001111",
        "救命!汶川映秀镇3楼塌了,我们一家三口困在里面,缺水和食物,电话13900001234",
        "新疆伊犁新源县发生6.6级地震,那拉提镇有8位老人需要帐篷和药品,手机13900004444",
    ]
    print(f"{'='*60}")
    print(f"LLM Few-shot NER 演示 ({args.shots}-shot, {args.model})")
    print(f"{'='*60}")
    for t in demos:
        try:
            r = infer_llm(t, n_shots=args.shots, model=args.model)
            print_result(r)
        except Exception as e:
            print(f"\n原文: {t}")
            print(f"  错误: {e}")


if __name__ == "__main__":
    main()
