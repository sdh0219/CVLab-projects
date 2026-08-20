# -*- coding: utf-8 -*-
"""
xBD 标注解析：把 JSON 里的 WKT 多边形栅格化成训练用掩膜。
- 定位掩膜 loc_mask:  HxW，0=背景 1=建筑     （来自灾前 JSON）
- 损毁掩膜 dmg_mask:  HxW，0=背景 1~4=损毁等级（来自灾后 JSON 的 subtype）
不依赖 rasterio/GDAL，仅用 shapely 解析 WKT + OpenCV 填充。
"""
import json
import numpy as np
import cv2
from shapely import wkt as shapely_wkt

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C


def _polys_from_json(json_path):
    """返回 [(shapely_polygon, subtype_str_or_None), ...]"""
    with open(json_path, "r") as f:
        data = json.load(f)
    out = []
    feats = data.get("features", {}).get("xy", [])
    for feat in feats:
        try:
            geom = shapely_wkt.loads(feat["wkt"])
        except Exception:
            continue
        st = feat.get("properties", {}).get("subtype")
        out.append((geom, st))
    h = data.get("metadata", {}).get("height", C.IMG_SIZE)
    w = data.get("metadata", {}).get("width", C.IMG_SIZE)
    return out, (h, w)


def _fill(mask, geom, value):
    """把一个 shapely 多边形按像素坐标填进 mask。"""
    if geom.is_empty:
        return
    geoms = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for g in geoms:
        xy = np.array(g.exterior.coords, dtype=np.int32)
        if len(xy) >= 3:
            cv2.fillPoly(mask, [xy], int(value))


def make_loc_mask(pre_json_path):
    polys, (h, w) = _polys_from_json(pre_json_path)
    mask = np.zeros((h, w), np.uint8)
    for geom, _ in polys:
        _fill(mask, geom, 1)
    return mask


def make_damage_mask(post_json_path):
    polys, (h, w) = _polys_from_json(post_json_path)
    mask = np.zeros((h, w), np.uint8)
    # 先填重的后填轻的会相互覆盖；按等级从轻到重排序，重等级最后填，确保重叠处取重等级
    polys_sorted = sorted(
        polys, key=lambda x: C.SUBTYPE_TO_ID.get(x[1], 1)
    )
    for geom, st in polys_sorted:
        cls = C.SUBTYPE_TO_ID.get(st, 1)
        _fill(mask, geom, cls)
    return mask


if __name__ == "__main__":
    # 自检：对一张合成样本可视化掩膜
    import os, glob
    sample = sorted(glob.glob(os.path.join(C.TRAIN_DIR, "labels", "*_post_disaster.json")))[0]
    pre = sample.replace("_post_disaster.json", "_pre_disaster.json")
    loc = make_loc_mask(pre)
    dmg = make_damage_mask(sample)
    print("loc 掩膜 唯一值:", np.unique(loc), " 建筑像素:", int(loc.sum()))
    print("dmg 掩膜 唯一值:", np.unique(dmg))
