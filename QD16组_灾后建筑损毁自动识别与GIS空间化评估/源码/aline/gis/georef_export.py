# -*- coding: utf-8 -*-
"""
A 线 → GIS 桥接：把模型的像素级损毁预测，落到真实经纬度上，导出 GeoJSON。

原理：
  xBD 标注 JSON 每栋建筑同时含 xy(像素) 与 lng_lat(WGS84) 两套坐标。
  - 空间定位：直接用标注里的 lng_lat 建筑底面（footprint），坐标精确、无需自己求变换。
  - 损毁等级：在该建筑的 xy 多边形范围内，对模型预测掩膜取众数 → 预测等级。
  这是损毁评估领域 "footprint + 模型定级" 的标准做法。报告中如实写明：
  建筑底面来自标注/底图，损毁等级由模型预测。

输出：outputs/gis/damage_buildings.geojson  (EPSG:4326, 每栋建筑一个 Feature)
字段：uid, disaster, pred(0~4), pred_label, true(0~4), true_label, area_m2
  pred=0 表示模型在该建筑处未检出损毁（漏检/判为背景）。

用法：python gis/georef_export.py
"""
import os, sys, json, glob
import numpy as np
import cv2
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C

GIS_DIR = os.path.join(C.ROOT, "outputs", "gis")
os.makedirs(GIS_DIR, exist_ok=True)

LABELS = ["background", "no-damage", "minor-damage", "major-damage", "destroyed"]


def _index_post_jsons(test_dir):
    """递归建立 {base: post_disaster.json路径}。"""
    idx = {}
    for root_, _, files in os.walk(test_dir):
        for f in files:
            if f.endswith("_post_disaster.json"):
                base = f.replace("_post_disaster.json", "")
                idx[base] = os.path.join(root_, f)
    return idx


def _load_buildings(post_json):
    """返回 [(uid, subtype, geom_xy, geom_lnglat)], meta。按 uid 对齐 xy 与 lng_lat。"""
    with open(post_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    feats = data.get("features", {})
    xy_list = feats.get("xy", [])
    ll_list = feats.get("lng_lat", [])
    ll_by_uid = {ft.get("properties", {}).get("uid"): ft for ft in ll_list}

    out = []
    for ft in xy_list:
        props = ft.get("properties", {})
        uid = props.get("uid")
        subtype = props.get("subtype")
        try:
            g_xy = shapely_wkt.loads(ft["wkt"])
        except Exception:
            continue
        ll = ll_by_uid.get(uid)
        if ll is None:
            continue
        try:
            g_ll = shapely_wkt.loads(ll["wkt"])
        except Exception:
            continue
        out.append((uid, subtype, g_xy, g_ll))
    return out, data.get("metadata", {})


def _pred_class_in_polygon(mask, geom_xy, native_size):
    """在建筑 xy 多边形范围内对预测掩膜取众数。mask 可能是下采样分辨率。"""
    scale = mask.shape[0] / float(native_size)
    coords = np.array(geom_xy.exterior.coords) * scale
    poly_mask = np.zeros(mask.shape, np.uint8)
    cv2.fillPoly(poly_mask, [coords.astype(np.int32)], 1)
    vals = mask[poly_mask > 0]
    vals = vals[vals > 0]
    if vals.size == 0:
        return 0
    return int(np.bincount(vals).argmax())


def main():
    pred_files = sorted(glob.glob(os.path.join(C.PRED_DIR, "*_dmg.npy")))
    if not pred_files:
        print("未找到预测结果(*_dmg.npy)，请先运行 inference.py")
        return
    json_idx = _index_post_jsons(C.TEST_DIR)
    print(f"预测样本 {len(pred_files)} 个 | 标注 JSON 索引 {len(json_idx)} 个")

    features = []
    n_build = 0
    matched_imgs = 0
    for pf in pred_files:
        base = os.path.basename(pf).replace("_dmg.npy", "")
        post_json = json_idx.get(base)
        if post_json is None:
            continue
        matched_imgs += 1
        mask = np.load(pf)
        buildings, meta = _load_buildings(post_json)
        gsd = float(meta.get("gsd", C.GSD_M))
        native = int(meta.get("width", 1024))
        disaster = meta.get("disaster", base.split("_")[0])

        for uid, subtype, g_xy, g_ll in buildings:
            pred = _pred_class_in_polygon(mask, g_xy, native)
            true = C.SUBTYPE_TO_ID.get(subtype, 0) if subtype else 0
            area_m2 = round(g_xy.area * (gsd ** 2), 2)  # 用原生像素面积×GSD²，分辨率无关
            features.append({
                "type": "Feature",
                "geometry": mapping(g_ll),
                "properties": {
                    "uid": uid,
                    "disaster": disaster,
                    "pred_cls": pred,
                    "pred_label": LABELS[pred],
                    "true_cls": true,
                    "true_label": LABELS[true],
                    "area_m2": area_m2,
                },
            })
            n_build += 1

    fc = {"type": "FeatureCollection",
          "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
          "features": features}
    out_path = os.path.join(GIS_DIR, "damage_buildings.geojson")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)

    # 统计预测分布
    from collections import Counter
    cnt = Counter(ft["properties"]["pred_cls"] for ft in features)
    print(f"匹配影像 {matched_imgs} 张，导出建筑 {n_build} 栋 -> {out_path}")
    for c in range(5):
        print(f"  预测 {LABELS[c]:>12}: {cnt.get(c,0)} 栋")


if __name__ == "__main__":
    main()
