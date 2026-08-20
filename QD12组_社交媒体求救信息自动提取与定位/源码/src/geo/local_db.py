"""本地地名库匹配: 最长匹配 + 后备省/市级匹配。"""
from __future__ import annotations

import json

from src.config import GEO_DICT_FILE


class LocalGeocoder:
    """基于 china_geo_dict.json 的本地地名匹配。"""

    def __init__(self, geo_dict_file=GEO_DICT_FILE):
        try:
            with geo_dict_file.open("r", encoding="utf-8") as f:
                self.geo = json.load(f)
        except FileNotFoundError:
            self.geo = {}
        # 按长度降序, 用于最长匹配
        self.names = sorted(self.geo.keys(), key=lambda x: -len(x))

    def geocode(self, text: str) -> dict | None:
        """在 text 中找最长的已知地名, 返回其经纬度。

        Returns:
            {"lng","lat","province","level","matched":地名}
            找不到时返回 None。
        """
        if not text:
            return None
        for name in self.names:
            if name and name in text:
                info = self.geo[name]
                return {
                    "lng": info["lng"], "lat": info["lat"],
                    "province": info.get("province", ""),
                    "level": info.get("level", ""),
                    "matched": name,
                    "source": "local",
                }
        return None

    def is_available(self) -> bool:
        return len(self.geo) > 0
