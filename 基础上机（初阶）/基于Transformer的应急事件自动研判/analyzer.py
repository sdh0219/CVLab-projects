import re
import torch
from model import EventTransformer

NAMES = {"fire":"火灾", "flood":"洪涝", "earthquake":"地震", "chemical_leak":"危化品泄漏", "landslide":"山体滑坡", "other":"其他"}
ADVICE = {
    "fire": ["确认报警并设置警戒区", "组织人员向安全区域疏散", "通知消防和医疗力量"],
    "flood": ["核实积水深度和上游水情", "封闭危险路段和低洼区域", "转移受威胁人员"],
    "earthquake": ["组织避险并远离受损建筑", "排查人员被困和次生灾害", "组织专业结构安全评估"],
    "chemical_leak": ["立即设置警戒区，禁止无防护人员进入", "根据实测风向向上风或侧风方向疏散", "查询物质清单并由专业队伍检测"],
    "landslide": ["封锁滑坡威胁区和道路", "立即转移威胁区人员", "监测裂缝、降雨和二次滑坡风险"],
    "other": ["进一步核实现场信息", "按属地流程上报并保持联络"],
}


class EmergencyAnalyzer:
    def __init__(self, model_path="event_transformer.pt"):
        c = torch.load(model_path, map_location="cpu", weights_only=True); self.vocab, self.labels, self.max_length = c["vocab"], c["labels"], c["max_length"]
        self.model = EventTransformer(len(self.vocab)+2, len(self.labels), self.max_length, c["d_model"], c["nhead"], c["layers"])
        self.model.load_state_dict(c["model_state"]); self.model.eval()

    def analyze(self, text):
        ids = [self.vocab.get(c, 1) for c in text[:self.max_length]]; ids += [0]*(self.max_length-len(ids))
        with torch.no_grad(): prob = torch.softmax(self.model(torch.tensor(ids).unsqueeze(0)), 1)[0]
        index = int(prob.argmax()); label = self.labels[index]
        time = re.search(r"(?:\d{1,2}月\d{1,2}日)?\d{1,2}时(?:\d{1,2}分)?|(?:今日|今晚|刚刚)", text)
        people = re.findall(r"\d+人(?:被困|受伤|失联|死亡|中毒)", text)
        wind = re.search(r"[东西南北]{1,2}风\d?级?|风向不定", text)
        place = re.search(r"([^,，。]{2,18}(?:园区|仓库|车间|村|街道|景区|隧道))", text)
        high_words = ("被困", "受伤", "呼吸困难", "刺鼻", "蔓延", "倒塌", "泄漏")
        severity = "高" if any(word in text for word in high_words) else ("中" if label != "other" else "低")
        return {"event_type": NAMES[label], "event_code": label, "confidence": round(float(prob[index]), 4),
            "severity": severity, "time": time.group(0) if time else "未提取", "location": place.group(1) if place else "未提取",
            "people": people or ["未提取"], "wind": wind.group(0) if wind else "未提取", "advice": ADVICE[label],
            "warning": "仅供教学演示；现场信息、响应级别和处置命令必须由有权人员核实决定。"}

