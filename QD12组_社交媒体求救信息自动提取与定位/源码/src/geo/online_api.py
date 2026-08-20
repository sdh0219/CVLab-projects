"""在线地理编码: 高德地图 API (主) + 百度地图 API (备)。

调用方式:
  1. 优先用高德 (restapi.amap.com/v3/geocode/geo)
  2. 高德失败时回退到百度 (api.map.baidu.com/geocoding/v3/)
  3. 需要在环境变量设置 AMAP_KEY 或 BAIDU_AK

环境变量:
  AMAP_KEY   高德 Web 服务 Key (https://console.amap.com/dev/key/app)
  BAIDU_AK   百度地图 AK (https://lbsyun.baidu.com/apiconsole/key)

注意:
  - 在线 API 返回坐标为 GCJ-02 (高德) / BD-09 (百度), 这里统一返回
    GCJ-02 (百度结果会做 BD09->GCJ02 转换), 与本地库一致, 适合中国地图可视化。
"""
from __future__ import annotations

import math
import os

import requests

from src.config import AMAP_KEY, BAIDU_AK, GEOCODE_TIMEOUT


def _bd09_to_gcj02(bd_lng: float, bd_lat: float) -> tuple[float, float]:
    """BD-09 -> GCJ-02 坐标转换。"""
    x_pi = math.pi * 3000.0 / 180.0
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
    return z * math.cos(theta), z * math.sin(theta)


def geocode_amap(text: str, key: str = AMAP_KEY) -> dict | None:
    """高德地理编码。"""
    if not key:
        return None
    try:
        r = requests.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params={"address": text, "key": key, "output": "json"},
            timeout=GEOCODE_TIMEOUT,
        )
        data = r.json()
        if data.get("status") == "1" and data.get("geocodes"):
            loc = data["geocodes"][0].get("location", "")  # "lng,lat"
            if loc:
                lng, lat = loc.split(",")
                return {
                    "lng": float(lng), "lat": float(lat),
                    "province": data["geocodes"][0].get("province", ""),
                    "level": data["geocodes"][0].get("level", ""),
                    "matched": text, "source": "amap",
                }
    except Exception as e:
        print(f"[geocode_amap] {text} 失败: {e}")
    return None


def geocode_baidu(text: str, ak: str = BAIDU_AK) -> dict | None:
    """百度地理编码。"""
    if not ak:
        return None
    try:
        r = requests.get(
            "https://api.map.baidu.com/geocoding/v3/",
            params={"address": text, "ak": ak, "output": "json"},
            timeout=GEOCODE_TIMEOUT,
        )
        data = r.json()
        if data.get("status") == 0 and data.get("result"):
            loc = data["result"].get("location", {})
            lng, lat = loc.get("lng"), loc.get("lat")
            if lng and lat:
                # BD-09 -> GCJ-02
                g_lng, g_lat = _bd09_to_gcj02(lng, lat)
                return {
                    "lng": g_lng, "lat": g_lat, "province": "",
                    "level": data["result"].get("level", "") or "precise",
                    "matched": text, "source": "baidu",
                }
    except Exception as e:
        print(f"[geocode_baidu] {text} 失败: {e}")
    return None


def online_geocode(text: str) -> dict | None:
    """优先高德, 回退百度。无 Key 时返回 None。"""
    if not (AMAP_KEY or BAIDU_AK):
        return None
    res = geocode_amap(text)
    if res is None:
        res = geocode_baidu(text)
    return res


if __name__ == "__main__":
    # 自测 (需要环境变量)
    import os
    if not os.environ.get("AMAP_KEY"):
        print("未设置 AMAP_KEY, 跳过自测")
    else:
        r = online_geocode("郑州京广路隧道")
        print(r)
