import json
from analyzer import EmergencyAnalyzer

text = "8月24日16时20分，滨海化工园区3号仓库冒出黄色烟雾，有明显刺鼻气味，2人受伤，当前东南风3级。"
print("输入：", text)
print(json.dumps(EmergencyAnalyzer().analyze(text), ensure_ascii=False, indent=2))

