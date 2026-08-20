from __future__ import annotations

import csv
import json
import mimetypes
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "national_disaster_platform"

SCENARIOS = {
    "sichuan_earthquake": {
        "title": "四川汶川地震救援",
        "type": "earthquake",
        "type_label": "地震",
        "province": "四川",
        "city": "汶川",
        "event": "2008 年汶川地震",
        "date": "2008-05-12",
        "start": "成都市区",
        "target": "汶川县城",
        "hazard": "塌方、滑坡、道路中断、山区拥堵",
        "data_dir": ROOT / "data" / "osm_sichuan_earthquake",
        "output_dir": ROOT / "outputs" / "osm_sichuan_earthquake",
        "marker": {"x": 43, "y": 58},
        "pipeline_label": "四川地震场景",
        "pipeline_config": ROOT / "configs" / "osm_disaster_pipeline.sichuan_earthquake.json",
        "summary": "以成都到汶川救援为例，叠加 2008 年汶川地震影响区，识别塌方/中断风险路段。",
    },
    "beijing_flood": {
        "title": "北京暴雨洪涝救援",
        "type": "flood",
        "type_label": "洪水/内涝",
        "province": "北京",
        "city": "北京",
        "event": "2012 年北京 7.21 暴雨",
        "date": "2012-07-21",
        "start": "清华大学",
        "target": "北京朝阳站",
        "hazard": "积水、拥堵、城市通行能力下降",
        "data_dir": ROOT / "data" / "osm_beijing_flood",
        "output_dir": ROOT / "outputs" / "osm_beijing_flood",
        "marker": {"x": 72, "y": 32},
        "pipeline_label": "洪水OSM路网场景",
        "pipeline_config": None,
        "summary": "以北京城区洪涝应急通行为例，叠加历史暴雨影响区和高德实时拥堵数据。",
    },
    "shanghai_fire": {
        "title": "上海胶州路火灾救援",
        "type": "fire",
        "type_label": "火灾",
        "province": "上海",
        "city": "上海",
        "event": "2010 年上海胶州路 11.15 火灾",
        "date": "2010-11-15",
        "start": "武宁消防站",
        "target": "胶州路 728 号火灾点",
        "hazard": "火场影响区、交通管制、城市拥堵",
        "data_dir": ROOT / "data" / "osm_shanghai_fire",
        "output_dir": ROOT / "outputs" / "osm_shanghai_fire",
        "marker": {"x": 76, "y": 52},
        "pipeline_label": "上海火灾OSM路网场景",
        "pipeline_config": ROOT / "configs" / "osm_disaster_pipeline.shanghai_fire.json",
        "summary": "以消防站到火灾点救援为例，叠加真实火灾位置、火场缓冲区和高德交通态势。",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def scenario_payload(sid: str) -> dict:
    config = SCENARIOS[sid]
    data_dir = config["data_dir"]
    output_dir = config["output_dir"]
    nodes = read_csv(data_dir / "nodes.csv")
    edges = read_csv(data_dir / "edges.csv")
    disasters = read_csv(data_dir / "disaster_events.csv")
    mapping = read_csv(data_dir / "road_disaster_mapping.csv")
    traffic = read_csv(data_dir / "road_traffic_mapping.csv")
    comparison = read_csv(output_dir / "path_comparison.csv")
    by_mode = {row.get("mode", ""): row for row in comparison if row.get("algorithm") == "Dijkstra"}
    danger_counts: dict[str, int] = {}
    for row in mapping:
        danger = row.get("danger_type") or "unknown"
        danger_counts[danger] = danger_counts.get(danger, 0) + 1
    traffic_counts: dict[str, int] = {}
    for row in traffic:
        label = row.get("traffic_status_label") or "unknown"
        traffic_counts[label] = traffic_counts.get(label, 0) + 1

    image = output_dir / "route_map_abstract.png"
    return {
        "id": sid,
        **{k: v for k, v in config.items() if k not in {"data_dir", "output_dir", "pipeline_config", "pipeline_label"}},
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "disasterEvents": len(disasters),
            "mappedDangerEdges": len(mapping),
            "trafficMappedEdges": len(traffic),
            "dangerCounts": danger_counts,
            "trafficCounts": traffic_counts,
        },
        "result": {
            "distance": by_mode.get("distance", {}),
            "safe": by_mode.get("safe", {}),
        },
        "routeImage": f"/artifact?path={quote_rel(image)}",
        "pipelineSteps": ensure_pipeline_steps(sid),
        "dataDir": str(data_dir),
        "outputDir": str(output_dir),
        "pipeline": [
            "选择历史灾害事件和救援起终点",
            "抓取/加载该区域真实 OSM 道路网络",
            "叠加历史灾害影响区并识别危险路段",
            "叠加高德交通态势中的拥堵路段",
            "运行 Dijkstra：距离权重得到普通最短路径",
            "运行 Dijkstra：安全权重得到安全救援路径",
            "输出路径对比表和可视化路线图",
        ],
    }


def quote_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return ""


def run_recalculate(sid: str) -> dict:
    """真实运行模式：调用本地脚本重新执行 Dijkstra 和可视化。
    统一使用网页场景的 data_dir 和 output_dir，不输出到 demo_* 目录。"""
    config = SCENARIOS[sid]
    data_dir = config["data_dir"]
    output_dir = config["output_dir"]
    pipeline_label = config.get("pipeline_label", config["title"])
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)

    started = time.time()
    logs: list[str] = []

    # 步骤 1: 运行 Dijkstra 路径规划
    logs.append("[真实运行] 步骤 1/3: 运行 Dijkstra 路径规划")
    proc = subprocess.run(
        [
            str(python), str(ROOT / "src" / "rescue_planner.py"),
            "--data-dir", str(data_dir), "--output-dir", str(output_dir),
        ],
        cwd=ROOT, text=True, capture_output=True, timeout=180,
    )
    logs.append(proc.stdout)
    if proc.stderr:
        logs.append(proc.stderr)
    if proc.returncode != 0:
        return {"ok": False, "logs": logs, "elapsed": round(time.time() - started, 2)}

    # 步骤 2: 渲染完整路线对比图
    logs.append("[真实运行] 步骤 2/3: 渲染完整路线对比图")
    proc = subprocess.run(
        [
            str(python), "-c",
            (
                "from pathlib import Path; "
                "from tools.create_abstract_route_maps import render_scene; "
                f"render_scene(Path(r'{data_dir}'), Path(r'{output_dir}'), '{config['title']}')"
            ),
        ],
        cwd=ROOT, text=True, capture_output=True, timeout=180,
    )
    logs.append(proc.stdout)
    if proc.stderr:
        logs.append(proc.stderr)
    if proc.returncode != 0:
        return {"ok": False, "logs": logs, "elapsed": round(time.time() - started, 2)}

    # 步骤 3: 生成 7 张流水线步骤图
    logs.append("[真实运行] 步骤 3/3: 生成 7 张流水线阶段图")
    step_failed = False
    try:
        step_proc = subprocess.run(
            [
                str(python), "-c",
                (
                    "from pathlib import Path; "
                    "from tools.create_abstract_route_maps import render_pipeline_steps; "
                    f"render_pipeline_steps(Path(r'{data_dir}'), Path(r'{output_dir}'), '{pipeline_label}')"
                ),
            ],
            cwd=ROOT, text=True, capture_output=True, timeout=300,
        )
        logs.append(step_proc.stdout)
        if step_proc.stderr:
            logs.append(step_proc.stderr)
        if step_proc.returncode != 0:
            step_failed = True
            logs.append(f"[警告] 流水线步骤图生成失败 (exit code: {step_proc.returncode})")
    except subprocess.TimeoutExpired:
        step_failed = True
        logs.append("[警告] 流水线步骤图生成超时")
    except Exception as exc:
        step_failed = True
        logs.append(f"[警告] 流水线步骤图生成异常: {exc}")

    elapsed = round(time.time() - started, 2)
    if step_failed:
        logs.append(f"[完成] Dijkstra 和路线图已完成，但步骤图生成失败 (共耗时 {elapsed} 秒)")
    else:
        logs.append(f"[完成] 真实流水线执行完成，共耗时 {elapsed} 秒")
    return {"ok": True, "logs": logs, "elapsed": elapsed}


def ensure_pipeline_steps(sid: str) -> list[str]:
    """确保流水线步骤图存在，返回相对路径列表。"""
    config = SCENARIOS[sid]
    data_dir = config["data_dir"]
    output_dir = config["output_dir"]
    steps: list[str] = []
    for i in range(1, 8):
        step_file = output_dir / f"pipeline_step_{i}.png"
        try:
            if step_file.exists():
                steps.append(step_file.resolve().relative_to(ROOT.resolve()).as_posix())
            else:
                steps.append("")
        except ValueError:
            steps.append("")
    # 如果 pipeline_step_7.png 不存在，回退到 route_map_abstract.png
    if not steps[6]:
        final = output_dir / "route_map_abstract.png"
        try:
            if final.exists():
                steps[6] = final.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            pass
    return steps


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            return self.serve_file(APP_DIR / "index.html")
        if path == "/api/scenarios":
            return self.json_response([scenario_payload(sid) for sid in SCENARIOS])
        if path.startswith("/api/scenarios/"):
            sid = path.rsplit("/", 1)[-1]
            if sid not in SCENARIOS:
                return self.error_json(404, "Unknown scenario")
            return self.json_response(scenario_payload(sid))
        if path == "/artifact":
            params = parse_qs(parsed.query)
            rel = unquote(params.get("path", [""])[0])
            target = (ROOT / rel).resolve()
            try:
                target.relative_to(ROOT.resolve())
            except ValueError:
                return self.error_json(403, "Forbidden path")
            return self.serve_file(target)
        if path.startswith("/static/"):
            return self.serve_file(APP_DIR / path.lstrip("/"))
        return self.error_json(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/run-pipeline/"):
            sid = parsed.path.rsplit("/", 1)[-1]
            if sid not in SCENARIOS:
                return self.error_json(404, "Unknown scenario")
            try:
                result = run_recalculate(sid)
            except Exception as exc:
                return self.json_response({"ok": False, "logs": [str(exc)], "elapsed": 0})
            return self.json_response(result)
        return self.error_json(404, "Not found")

    def serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return self.error_json(404, f"Missing file: {path}")
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def json_response(self, payload: object, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def error_json(self, status: int, message: str) -> None:
        self.json_response({"ok": False, "error": message}, status=status)

    def log_message(self, format: str, *args) -> None:
        print(f"[platform] {self.address_string()} - {format % args}")


def main() -> None:
    port = 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"National Disaster Response Platform: http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
