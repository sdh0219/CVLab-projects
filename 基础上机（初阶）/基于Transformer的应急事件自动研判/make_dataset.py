"""生成可复现的中文应急事件教学数据集。"""
import json
import random
from pathlib import Path

random.seed(2026)
templates = {
    "fire": ["{time}{place}{object}冒出{smoke}，现场发现火光，{people}。", "{place}发生火灾，火势{level}，{people}，消防车正在赶来。"],
    "flood": ["{time}{place}连续强降雨，道路积水{depth}，{people}。", "{place}河流水位快速上涨，部分区域被淹，{people}。"],
    "earthquake": ["{time}{place}发生明显震感，部分墙体开裂，{people}。", "{place}发生地震，有建筑物掉落物，{people}。"],
    "chemical_leak": ["{time}{place}{object}冒出{smoke}，有刺鼻气味，{people}，{wind}。", "{place}疑似危险化学品泄漏，检测到异常气体，{people}，{wind}。"],
    "landslide": ["{time}{place}山体出现裂缝并有土石滑落，{people}。", "{place}发生山体滑坡，道路被土石阻断，{people}。"],
    "other": ["{time}{place}发生停电，目前正在抢修，{people}。", "{place}举行大型活动，现场人员较多，暂无异常。"],
}
values = {
    "time": ["8月24日16时20分，", "今日上午9时，", "刚刚", "晚上22时，"],
    "place": ["滨海化工园区", "东城街道", "新河村", "高速公路隧道", "西山景区", "中心仓库"],
    "object": ["3号仓库", "储罐区", "生产车间", "地下车库"],
    "smoke": ["大量黑烟", "黄色烟雾", "白色浓烟", "灰色烟雾"],
    "people": ["暂无人员伤亡", "2人被困", "3人受伤", "多人出现咳嗽", "人员正在疏散"],
    "wind": ["当前东南风3级", "当前西风2级", "现场风向不定"],
    "level": ["较小", "较大", "正在蔓延"], "depth": ["20厘米", "50厘米", "1米"],
}
rows = []
for label, patterns in templates.items():
    for _ in range(180):
        pattern = random.choice(patterns)
        text = pattern.format(**{key: random.choice(items) for key, items in values.items()})
        rows.append({"text": text, "label": label})
random.shuffle(rows)
out = Path("data"); out.mkdir(exist_ok=True)
with (out / "events.jsonl").open("w", encoding="utf-8") as file:
    for row in rows: file.write(json.dumps(row, ensure_ascii=False) + "\n")
print(f"已生成 {len(rows)} 条教学数据: data/events.jsonl")

