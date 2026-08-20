"""下载 Leaflet/jQuery/Bootstrap/markercluster 等静态资源到 static/ 目录。

让 rescue_map.html 完全离线可用(不依赖任何 CDN)。
所有资源从官方 CDN 下载一次,缓存到项目 static/ 目录,
之后生成 HTML 时引用本地文件。

运行:
    python scripts/download_static.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJ_ROOT / "outputs" / "maps" / "static"

# (相对路径, 下载 URL)
RESOURCES = [
    # Leaflet 核心
    ("leaflet/leaflet.js",
     "https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"),
    ("leaflet/leaflet.css",
     "https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"),
    # Leaflet markercluster
    ("markercluster/leaflet.markercluster.js",
     "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.1.0/leaflet.markercluster.js"),
    ("markercluster/MarkerCluster.css",
     "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.1.0/MarkerCluster.css"),
    ("markercluster/MarkerCluster.Default.css",
     "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.1.0/MarkerCluster.Default.css"),
    # jQuery
    ("jquery/jquery-3.7.1.min.js",
     "https://code.jquery.com/jquery-3.7.1.min.js"),
]


def download_all() -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    print(f"下载静态资源到: {STATIC_DIR}\n")
    ok = fail = 0
    for rel, url in RESOURCES:
        dst = STATIC_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size > 100:
            print(f"  [跳过] {rel} (已存在)")
            ok += 1
            continue
        try:
            print(f"  [下载] {rel} ...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            dst.write_bytes(data)
            print(f"          OK ({len(data)/1024:.1f} KB)")
            ok += 1
        except Exception as e:
            print(f"          失败: {e}")
            fail += 1
    print(f"\n完成: 成功 {ok}, 失败 {fail}")
    if fail:
        print("[!] 部分资源下载失败, HTML 将无法完全离线。可重跑本脚本。")
        sys.exit(1)


if __name__ == "__main__":
    download_all()
