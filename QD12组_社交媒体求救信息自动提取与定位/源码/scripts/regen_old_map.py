"""还原 rescue_map_old.html (旧版 folium 页面)。

按之前的 folium 实现重新生成, 从 Structured CSV 读取同样的 288 条数据。
"""
import csv
import sys
from pathlib import Path

# 把项目根目录加入 sys.path, 让 from src.config 可用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import folium
from folium.plugins import MarkerCluster
from src.config import STRUCTURED_CSV

URGENCY_COLOR = {"emergency": "red", "high": "orange", "medium": "beige"}
URGENCY_LABEL = {"emergency": "紧急", "high": "高", "medium": "中"}

items = []
with STRUCTURED_CSV.open("r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        try:
            lng = float(row["经度"]) if row.get("经度") else None
            lat = float(row["纬度"]) if row.get("纬度") else None
        except (ValueError, KeyError):
            lng = lat = None
        items.append({
            "text": row.get("原文", ""),
            "location": row.get("地点", ""),
            "person": row.get("人员", ""),
            "need": row.get("需求", ""),
            "disaster": row.get("灾情", ""),
            "urgency": row.get("紧急程度", "medium"),
            "lng": lng, "lat": lat,
        })


def _popup_html(item):
    text = item.get("text", "")
    loc = item.get("location", "")
    pers = item.get("person", "")
    need = item.get("need", "")
    dis = item.get("disaster", "")
    urg = item.get("urgency", "")
    urg_color = URGENCY_COLOR.get(urg, "gray")
    urg_label = URGENCY_LABEL.get(urg, urg)
    return f"""
    <div style="font-family: 'Microsoft YaHei', sans-serif; min-width:240px;">
      <div style="font-size:13px; color:{urg_color}; font-weight:bold;">
        ● 紧急程度: {urg_label}
      </div>
      <div style="font-size:13px; margin-top:4px;"><b>📍 地点:</b> {loc}</div>
      <div style="font-size:13px;"><b>⚠️ 灾情:</b> {dis}</div>
      <div style="font-size:13px;"><b>👥 人员:</b> {pers}</div>
      <div style="font-size:13px;"><b>🆘 需求:</b> {need}</div>
      <hr style="margin:6px 0;">
      <div style="font-size:12px; color:#555;">原文: {text}</div>
    </div>
    """


m = folium.Map(location=[33.0, 105.0], zoom_start=4,
               tiles="CartoDB positron", control_scale=True)
cluster = MarkerCluster(name="求救点").add_to(m)

n_placed = n_miss = 0
for it in items:
    lng, lat = it.get("lng"), it.get("lat")
    if lng is None or lat is None:
        n_miss += 1
        continue
    color = URGENCY_COLOR.get(it.get("urgency", "medium"), "gray")
    folium.Marker(
        location=[float(lat), float(lng)],
        popup=folium.Popup(_popup_html(it), max_width=320),
        tooltip=it.get("location", "")[:30],
        icon=folium.Icon(color=color, icon="info-sign"),
    ).add_to(cluster)
    n_placed += 1

legend_html = """
<div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;
            background: white; padding: 10px 14px; border-radius: 6px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-size: 13px;">
  <div style="font-weight:bold; margin-bottom:6px;">求救点紧急程度</div>
  <div><span style="color:red;">●</span> 紧急 (生命威胁)</div>
  <div><span style="color:orange;">●</span> 高 (需尽快救援)</div>
  <div><span style="color:#dd0;">●</span> 中 (信息通报/物资)</div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

out = Path("outputs/maps/rescue_map_old.html")
m.save(str(out))
print(f"[OK] 已还原旧版 folium 地图 -> {out}")
print(f"     已标记 {n_placed} 个求救点, 跳过 {n_miss} 个未定位")
