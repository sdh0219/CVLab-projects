"""基于规则与词典的基线 NER 方法。

用于与 BERT 模型做对比, 体现深度学习方法的优势。

抽取策略:
  - LOC (地点):  从本地地名库 (china_geo_dict.json) 做最长匹配
  - PER (人员):  正则匹配 "有X人/位/口/个" 类数量描述 + 亲属称谓
  - DIS (灾情):  自定义灾情关键词词典匹配
  - NEED (需求): 自定义需求关键词 + 电话号码正则

输出格式与 BERT 推理一致: {type, start, end, text}
"""
from __future__ import annotations

import json
import re

import jieba

from src.config import ENTITY_TYPES, GEO_DICT_FILE


# ---- 词典 ----

# 灾情关键词 (匹配即认为是 DIS 实体)
DIS_KEYWORDS = [
    "地震", "余震", "震感", "塌了", "倒塌", "坍塌", "裂开", "墙体开裂", "墙体倾斜",
    "楼板", "天花板掉", "山体滑坡", "滑坡", "泥石流", "山洪", "洪水", "决堤", "溃堤",
    "倒灌", "内涝", "积水", "被淹", "起火", "起大火", "火灾", "森林火灾", "草原火灾",
    "台风", "龙卷风", "暴雪", "暴雨", "停电", "停水", "海水倒灌", "塌陷", "垮塌",
    "崩塌", "失联", "水位暴涨", "水位猛涨", "水位超警", "水位上涨", "山体崩塌",
    "墙体", "火势", "房屋受损", "树木倒伏", "集装箱倒塌", "活动板房", "被埋",
]

# 需求关键词
NEED_KEYWORDS = [
    "水", "饮用水", "干净水", "食物", "食品", "粮食", "帐篷", "棉被", "保暖衣物",
    "御寒物资", "药品", "抗生素", "绷带", "担架", "吸氧设备", "发电机", "抽水机",
    "船只", "救生艇", "消防车", "云梯车", "救护车", "直升机", "救援人员", "救援队",
    "救援设备", "救援犬", "搜救犬", "挖掘机", "挖掘设备", "破拆工具", "沙袋",
    "安置点", "紧急安置", "紧急医疗", "紧急疏散", "转移", "安置", "支援",
    "撤离通道", "救援", "医疗", "疏散",
]

# 人员正则: "有/我们/我 + 数量 + 人/位/口/个" 或亲属称谓
PERSON_PATTERNS = [
    re.compile(r"(我们\s*[一-龥0-9]{0,6}(?:人|口|家[^\s人]?|户|个[人]?)?)"),
    re.compile(r"((?:有|共|共困|被困)\s*[0-9一二三四五六七八九十百两几多]{1,5}(?:个[人]|位|人|户|口|名[人]?))"),
    re.compile(r"([0-9一二三四五六七八九十百两几多]{1,4}(?:个[人]|位|人|户|名[人]?)(?:被困|被困住|困|失联)?)"),
    re.compile(r"((?:老人|孕妇|孩子|小孩|游客|村民|居民|工人|学生|研究员|牧民|渔民|司机|队员|群众|伤员)(?:和[^\s,，。!！；;]{1,8})?)"),
]

# 电话正则
PHONE_RE = re.compile(r"(?:电话|联系|手机|Tel|TEL|tel)\s*[:：]?\s*(1[3-9]\d{9})")
PHONE_RE2 = re.compile(r"(1[3-9]\d{9})")


class RuleBasedNER:
    def __init__(self, geo_dict_file=GEO_DICT_FILE):
        # 加载地名库, 按长度降序 (最长匹配)
        try:
            with geo_dict_file.open("r", encoding="utf-8") as f:
                self.geo_dict = json.load(f)
        except FileNotFoundError:
            self.geo_dict = {}
        self.loc_names = sorted(self.geo_dict.keys(), key=lambda x: -len(x))

        # jieba 加入地名词典
        for name in self.loc_names:
            jieba.add_word(name)

        self.dis_kw = sorted(DIS_KEYWORDS, key=lambda x: -len(x))
        self.need_kw = sorted(NEED_KEYWORDS, key=lambda x: -len(x))

    def _longest_match(self, text: str, vocab: list[str]) -> list[tuple[int, int, str]]:
        """在 text 中对 vocab 做最长匹配 (贪心, 按词长度降序)。"""
        occupied = [False] * len(text)
        results = []
        for w in vocab:
            if not w:
                continue
            start = 0
            while True:
                idx = text.find(w, start)
                if idx == -1:
                    break
                end = idx + len(w)
                if not any(occupied[idx:end]):
                    for k in range(idx, end):
                        occupied[k] = True
                    results.append((idx, end, w))
                start = idx + 1
        return results

    def extract(self, text: str) -> list[dict]:
        """对单条文本抽取实体, 返回 [{type, start, end, text}]。"""
        ents = []

        # 1. LOC: 地名库最长匹配
        for s, e, w in self._longest_match(text, self.loc_names):
            ents.append({"type": "LOC", "start": s, "end": e, "text": w})

        # 2. DIS: 灾情关键词匹配
        for s, e, w in self._longest_match(text, self.dis_kw):
            ents.append({"type": "DIS", "start": s, "end": e, "text": w})

        # 3. NEED: 需求关键词匹配
        for s, e, w in self._longest_match(text, self.need_kw):
            ents.append({"type": "NEED", "start": s, "end": e, "text": w})

        # 4. PER: 正则
        occupied_per = [False] * len(text)
        for pat in PERSON_PATTERNS:
            for m in pat.finditer(text):
                s, e = m.start(), m.end()
                if not any(occupied_per[s:e]):
                    for k in range(s, e):
                        occupied_per[k] = True
                    ents.append({"type": "PER", "start": s, "end": e,
                                 "text": text[s:e]})

        # 5. NEED: 电话号码 (优先带前缀的)
        for m in PHONE_RE.finditer(text):
            s, e = m.span()
            ents.append({"type": "NEED", "start": s, "end": e,
                         "text": text[s:e]})
        # 没带前缀的 11 位号码
        for m in PHONE_RE2.finditer(text):
            s, e = m.span()
            # 避免重复 (已包含在前缀形式中)
            if not any(ent["start"] == s for ent in ents):
                ents.append({"type": "NEED", "start": s, "end": e,
                             "text": text[s:e]})

        # 去重 + 排序
        seen = set()
        unique = []
        for ent in ents:
            key = (ent["type"], ent["start"], ent["end"])
            if key not in seen:
                seen.add(key)
                unique.append(ent)
        unique.sort(key=lambda x: x["start"])
        return unique

    def extract_to_tags(self, text: str) -> list[str]:
        """对单条文本抽取, 返回 BIO 标签序列 (与 text 等长)。"""
        tags = ["O"] * len(text)
        ents = self.extract(text)
        for e in ents:
            t = e["type"]
            tags[e["start"]] = f"B-{t}"
            for k in range(e["start"] + 1, e["end"]):
                tags[k] = f"I-{t}"
        return tags


def main():
    """对 test 集评估规则基线, 与 BERT 形成对比。"""
    from src.config import TEST_FILE
    from src.data.annotate import load_jsonl
    from src.evaluate import compute_metrics, format_report
    from src.config import TAG2ID

    ner = RuleBasedNER()
    samples = load_jsonl(TEST_FILE)
    print(f"[规则基线] 测试集 {len(samples)} 条")

    preds, golds = [], []
    for s in samples:
        gold_tags = s["tags"]
        pred_tags = ner.extract_to_tags(s["text"])
        # 对齐长度
        n = min(len(pred_tags), len(gold_tags))
        preds.append([TAG2ID.get(t, 0) for t in pred_tags[:n]])
        golds.append([TAG2ID.get(t, 0) for t in gold_tags[:n]])

    m = compute_metrics(preds, golds)
    print(format_report(m, "规则基线 (Rule-based)"))
    return m


if __name__ == "__main__":
    main()
