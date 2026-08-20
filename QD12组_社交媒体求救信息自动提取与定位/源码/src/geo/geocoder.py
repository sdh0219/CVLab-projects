"""统一地理编码接口: 本地库优先 -> 在线 API 回退。

用法:
    from src.geo.geocoder import Geocoder
    geo = Geocoder()
    result = geo.geocode("汶川映秀镇中心学校3楼")
    # -> {"lng":103.486, "lat":31.008, "matched":"汶川映秀镇中心学校",
    #     "source":"local", "province":"四川"}

策略 (与用户选择"两者结合"一致):
  1. 本地库最长匹配 (覆盖数据集中所有地名 + 主要灾区)
  2. 本地库未命中 -> 在线 API (高德->百度)
  3. 都失败 -> 返回 None (调用方决定如何标记)
"""
from __future__ import annotations

from src.config import GEO_DICT_FILE
from src.geo.local_db import LocalGeocoder
from src.geo.online_api import online_geocode


class Geocoder:
    def __init__(self, geo_dict_file=GEO_DICT_FILE,
                 use_online: bool = True, verbose: bool = False):
        self.local = LocalGeocoder(geo_dict_file)
        self.use_online = use_online
        self.verbose = verbose
        self._stats = {"local_hit": 0, "online_hit": 0, "miss": 0}

    def geocode(self, text: str) -> dict | None:
        """对一段文本做地理编码。

        Args:
            text: 文本 (通常是抽取出的地点实体, 也可以是整条求救文本)
        Returns:
            {"lng","lat","matched","source","province","level"} 或 None
        """
        if not text:
            return None

        # 1. 本地库
        r = self.local.geocode(text)
        if r is not None:
            self._stats["local_hit"] += 1
            if self.verbose:
                print(f"[geocode/local] {text[:20]} -> {r['matched']} ({r['lng']},{r['lat']})")
            return r

        # 2. 在线 API
        if self.use_online:
            r = online_geocode(text)
            if r is not None:
                self._stats["online_hit"] += 1
                if self.verbose:
                    print(f"[geocode/online] {text[:20]} -> ({r['lng']},{r['lat']}) [{r['source']}]")
                return r

        self._stats["miss"] += 1
        if self.verbose:
            print(f"[geocode/miss] {text}")
        return None

    def batch(self, texts: list[str]) -> list[dict | None]:
        return [self.geocode(t) for t in texts]

    def stats(self) -> dict:
        return dict(self._stats)

    def is_available(self) -> bool:
        return self.local.is_available() or self.use_online


def main():
    """简单自测。"""
    geo = Geocoder(verbose=True)
    tests = ["汶川映秀镇中心学校3楼", "郑州京广路隧道", "我们在学校地下车库里",
             "某个虚构的地方不存在县"]
    for t in tests:
        print(f"\n>> {t}")
        r = geo.geocode(t)
        print(f"   -> {r}")
    print(f"\n统计: {geo.stats()}")


if __name__ == "__main__":
    main()
