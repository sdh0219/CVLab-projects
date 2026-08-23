from __future__ import annotations

import csv
import html
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from docx import Document as DocxDocument
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("缺少 python-docx，请使用项目运行环境或安装 python-docx 后重试。") from exc


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DOCX = ROOT / "地震灾害数据收集与整理.docx"
CORPUS_DIR = ROOT / "data" / "corpus" / "earthquake"
OUTPUT_DIR = ROOT / "outputs" / "graphrag_index"
ARCHIVE_ROOT = ROOT / "outputs" / "历史索引归档"
PUBLIC_ATLAS_DIR = ROOT / "public" / "atlas"
DOCS_DIR = ROOT / "docs"
ONTOLOGY_PATH = ROOT / "config" / "ontology.json"

REQUIRED_ENTITY_TYPES = [
    "Document",
    "Evidence",
    "DisasterType",
    "Case",
    "Event",
    "AITech",
    "Model",
    "Dataset",
    "Task",
    "Scenario",
    "Policy",
    "Standard",
    "Limitation",
    "Organization",
    "Metric",
    "ImpactProduct",
]

REQUIRED_RELATION_TYPES = [
    "USES_MODEL",
    "DEPENDS_ON",
    "SOLVES",
    "SERVES_STAGE",
    "VALIDATED_IN",
    "LIMITED_BY",
    "REQUIRED_BY",
    "SUPPORTED_BY",
    "DERIVES_FROM",
    "MEASURED_BY",
    "EVALUATED_BY",
    "PUBLISHED_BY",
    "HAS_METRIC",
    "HAS_PARAMETER",
    "HAS_IMPACT",
]

RELATION_CN = {
    "USES_MODEL": "采用模型",
    "DEPENDS_ON": "依赖数据",
    "SOLVES": "解决任务",
    "SERVES_STAGE": "服务阶段",
    "VALIDATED_IN": "案例验证",
    "LIMITED_BY": "受限于",
    "REQUIRED_BY": "政策要求",
    "SUPPORTED_BY": "证据支持",
    "DERIVES_FROM": "来源于",
    "MEASURED_BY": "由指标度量",
    "EVALUATED_BY": "由对象评估",
    "PUBLISHED_BY": "由机构发布",
    "HAS_METRIC": "具有指标",
    "HAS_PARAMETER": "具有参数",
    "HAS_IMPACT": "产生影响",
}

SECTION_SPECS = [
    {
        "doc_id": "EQ_DOC_001",
        "title": "原始来源核验机制",
        "topic": "原始来源核验",
        "filename": "01_原始来源核验机制.md",
        "heading": "一、 引言与原始来源核验机制分析",
    },
    {
        "doc_id": "EQ_DOC_002",
        "title": "全球典型地震事件参数",
        "topic": "地震事件参数核验",
        "filename": "02_全球典型地震事件参数.md",
        "heading": "二、 全球典型地震事件及多网源参数核验",
    },
    {
        "doc_id": "EQ_DOC_003",
        "title": "ShakeMap与PAGER影响评估",
        "topic": "影响评估数据链",
        "filename": "03_ShakeMap与PAGER影响评估.md",
        "heading": "三、 地震动、烈度图与PAGER快速影响评估数据链",
    },
    {
        "doc_id": "EQ_DOC_004",
        "title": "灾后应急响应与人道需求",
        "topic": "灾后应急响应",
        "filename": "04_灾后应急响应与人道需求.md",
        "heading": "四、 灾后应急响应、复盘报告与人道主义需求演变",
    },
    {
        "doc_id": "EQ_DOC_005",
        "title": "遥感影像与建筑震损标签",
        "topic": "遥感震损识别",
        "filename": "05_遥感影像与建筑震损标签.md",
        "heading": "五、 遥感影像解译、建筑震损标签与多源几何特征提取",
    },
    {
        "doc_id": "EQ_DOC_006",
        "title": "暴露体与生命线韧性",
        "topic": "暴露体与生命线韧性",
        "filename": "06_暴露体与生命线韧性.md",
        "heading": "六、 暴露体脆弱性、生命线系统韧性与地理空间数据依赖",
    },
    {
        "doc_id": "EQ_DOC_007",
        "title": "分布式AI地震预警",
        "topic": "分布式AI地震预警",
        "filename": "07_分布式AI地震预警.md",
        "heading": "七、 分布式AI地震预警系统、边缘计算与众包传感器网络",
    },
    {
        "doc_id": "EQ_DOC_008",
        "title": "工程损失评估系统",
        "topic": "工程损失评估",
        "filename": "08_工程损失评估系统.md",
        "heading": "八、 工程损失评估软件、能力谱法与高级易损性分析系统",
    },
    {
        "doc_id": "EQ_DOC_009",
        "title": "应急治理政策标准",
        "topic": "应急治理政策标准",
        "filename": "09_应急治理政策标准.md",
        "heading": "九、 应急治理模型、国际标准与国家预案的数字化映射",
    },
    {
        "doc_id": "EQ_DOC_010",
        "title": "本体与复核机制",
        "topic": "本体与复核机制",
        "filename": "10_本体与复核机制.md",
        "heading": "十、 基于GraphRAG的知识图谱领域本体与评测复核系统设计",
    },
]


@dataclass
class EntitySpec:
    type: str
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    id: str = ""
    doc_ids: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    evidence_count: int = 0
    relation_count: int = 0
    community_id: str = ""
    score: float = 0.0


@dataclass
class RelationCandidate:
    head: str
    relation_type: str
    tail: str
    preferred_doc_id: str = ""


def assert_inside_project(path: Path) -> Path:
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise RuntimeError(f"路径越界，已停止：{resolved}")
    return resolved


def ensure_dirs() -> None:
    for path in [CORPUS_DIR, OUTPUT_DIR, ARCHIVE_ROOT, PUBLIC_ATLAS_DIR, DOCS_DIR, ONTOLOGY_PATH.parent]:
        assert_inside_project(path)
        path.mkdir(parents=True, exist_ok=True)


def archive_previous_outputs() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = ARCHIVE_ROOT / f"索引归档_{stamp}"
    assert_inside_project(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=False)

    if OUTPUT_DIR.exists():
        shutil.copytree(OUTPUT_DIR, archive_dir / "graphrag_index", dirs_exist_ok=True)
    public_archive = archive_dir / "public_atlas"
    public_archive.mkdir(parents=True, exist_ok=True)
    for filename in ["atlas_frontend.json", "index_summary.json", "graph_visualization.json"]:
        source = PUBLIC_ATLAS_DIR / filename
        if source.exists():
            shutil.copy2(source, public_archive / filename)

    if OUTPUT_DIR.exists():
        output_resolved = assert_inside_project(OUTPUT_DIR)
        if output_resolved.name != "graphrag_index":
            raise RuntimeError(f"拒绝清理非索引目录：{output_resolved}")
        shutil.rmtree(output_resolved)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return archive_dir


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def iter_docx_blocks(document: Any):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def table_to_markdown(table: Table) -> str:
    rows = [[normalize_text(cell.text) for cell in row.cells] for row in table.rows]
    rows = [row for row in rows if any(cell for cell in row)]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header = rows[0]

    def escape_cell(cell: str) -> str:
        return cell.replace("|", "\\|") or " "

    lines = [
        "| " + " | ".join(escape_cell(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(escape_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def read_source_docx() -> tuple[dict[str, str], dict[str, Any]]:
    if not SOURCE_DOCX.exists():
        raise FileNotFoundError(f"未找到新增资料：{SOURCE_DOCX}")

    document = DocxDocument(SOURCE_DOCX)
    sections = {spec["doc_id"]: [] for spec in SECTION_SPECS}
    heading_to_doc = {spec["heading"]: spec["doc_id"] for spec in SECTION_SPECS}
    current_doc_id = SECTION_SPECS[0]["doc_id"]
    table_count = 0
    paragraph_count = 0

    for block in iter_docx_blocks(document):
        if isinstance(block, Paragraph):
            text = normalize_text(block.text)
            if not text:
                continue
            paragraph_count += 1
            matched = next((doc_id for heading, doc_id in heading_to_doc.items() if text.startswith(heading)), "")
            if matched:
                current_doc_id = matched
                spec = next(item for item in SECTION_SPECS if item["doc_id"] == current_doc_id)
                sections[current_doc_id].append(f"## {spec['heading']}")
            else:
                sections[current_doc_id].append(text)
        elif isinstance(block, Table):
            table_md = table_to_markdown(block)
            if table_md:
                table_count += 1
                sections[current_doc_id].append(f"\n表 {table_count}\n\n{table_md}")

    section_texts = {doc_id: "\n\n".join(parts).strip() for doc_id, parts in sections.items()}
    meta = {
        "paragraph_count": paragraph_count,
        "table_count": table_count,
        "inline_shape_count": len(document.inline_shapes),
        "source_size_bytes": SOURCE_DOCX.stat().st_size,
    }
    return section_texts, meta


def frontmatter_for(spec: dict[str, str]) -> str:
    return "\n".join(
        [
            "---",
            f"doc_id: {spec['doc_id']}",
            f"title: {spec['title']}",
            "source_file: 地震灾害数据收集与整理.docx",
            f"topic: {spec['topic']}",
            "source_type: 整理报告",
            "graph_usage: Document Source Evidence",
            "language: zh-CN",
            "quality_status: 待复核",
            "---",
        ]
    )


def write_corpus(section_texts: dict[str, str]) -> list[dict[str, Any]]:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for old in CORPUS_DIR.glob("*.md"):
        old.unlink()

    documents: list[dict[str, Any]] = []
    for spec in SECTION_SPECS:
        body = section_texts.get(spec["doc_id"], "")
        content = f"{frontmatter_for(spec)}\n\n# {spec['title']}\n\n{body}\n"
        target = CORPUS_DIR / spec["filename"]
        target.write_text(content, encoding="utf-8", newline="\n")
        documents.append(
            {
                "doc_id": spec["doc_id"],
                "title": spec["title"],
                "topic": spec["topic"],
                "source_file": SOURCE_DOCX.name,
                "source_type": "整理报告",
                "language": "zh-CN",
                "quality_status": "待复核",
                "path": str(target.relative_to(ROOT)).replace("\\", "/"),
                "char_count": len(body),
            }
        )
    return documents


def split_into_chunks(documents: list[dict[str, Any]], section_texts: dict[str, str]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    chunk_index = 1
    for doc in documents:
        text = section_texts.get(doc["doc_id"], "")
        units = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        current: list[str] = []
        current_len = 0
        for unit in units:
            if current and current_len + len(unit) > 900:
                chunk_text = "\n\n".join(current).strip()
                chunks.append(make_chunk(chunk_index, doc, chunk_text))
                chunk_index += 1
                current = []
                current_len = 0
            current.append(unit)
            current_len += len(unit)
        if current:
            chunk_text = "\n\n".join(current).strip()
            chunks.append(make_chunk(chunk_index, doc, chunk_text))
            chunk_index += 1
    return chunks


def make_chunk(index: int, doc: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "chunk_id": f"CHK_EQ_{index:06d}",
        "doc_id": doc["doc_id"],
        "document_title": doc["title"],
        "topic": doc["topic"],
        "source_file": SOURCE_DOCX.name,
        "source_type": doc["source_type"],
        "text": text,
        "char_count": len(text),
        "quality_status": "待复核",
    }


def entity_specs() -> list[EntitySpec]:
    items: list[EntitySpec] = []

    def add(type_name: str, name: str, aliases: list[str] | None = None, description: str = "") -> None:
        items.append(EntitySpec(type=type_name, name=name, aliases=aliases or [], description=description))

    add("DisasterType", "地震", ["地震灾害", "震灾", "Earthquake"], "本项目聚焦的主要灾害类型。")

    for name in ["震前监测", "震时预警", "震后评估", "应急响应", "恢复重建", "灾后复盘", "政策治理", "城市韧性评估"]:
        add("Scenario", name)

    for name, aliases in [
        ("地震早期预警", ["地震预警", "早期预警", "earthquake early warning"]),
        ("震后建筑损毁识别", ["建筑震损", "建筑损毁", "建筑损坏估计", "building damage"]),
        ("遥感震损智能解译", ["遥感影像解译", "遥感震损", "震损标签", "多源几何特征", "SAR 震损"]),
        ("地震风险时空预测", ["地震风险评估", "地震风险", "风险预测", "seismic risk"]),
        ("震后灾情快速评估", ["快速影响评估", "快速评估", "灾情快速评估", "impact assessment"]),
        ("地震应急辅助决策", ["应急响应", "应急治理", "辅助决策", "response coordination"]),
        ("生命线震损风险传播GNN", ["生命线震损风险传播", "生命线系统韧性", "生命线韧性", "GNN", "图神经网络"]),
        ("震后救援调度优化", ["应急响应", "灾后应急响应", "人道主义需求", "救援调度", "物资调度", "路径规划", "救援路径", "relief allocation", "UNDAC", "INSARAG"]),
        ("地震证据图谱GraphRAG", ["GraphRAG", "知识图谱", "证据图谱", "证据链问答"]),
        ("数字孪生城市地震风险模拟", ["数字孪生", "城市地震风险", "风险模拟", "loss simulation"]),
        ("分布式AI地震预警", ["分布式AI地震预警系统", "边缘计算", "众包传感器网络", "AI-Powered EEWS"]),
    ]:
        add("AITech", name, aliases)

    add("Model", "CNN", ["Convolutional Neural Network", "卷积神经网络"])
    add("Model", "GNN", ["Graph Neural Network", "图神经网络"])
    add("Model", "LSTM", ["Long Short-Term Memory"])
    add("Model", "RNN", ["Recurrent Neural Network"])
    add("Model", "Transformer", ["ViT", "Swin Transformer"])
    add("Model", "U-Net", ["UNet"])
    add("Model", "随机森林", ["Random Forest"])
    add("Model", "XGBoost", ["Gradient Boosting"])
    add("Model", "能力谱法", ["Capacity Spectrum Method"])
    add("Model", "Hazus", ["HAZUS"])
    add("Model", "OpenQuake", ["OpenQuake Engine"])
    add("Model", "Edge-AI CNN", ["Edge-AI compact CNN", "compact CNN"])
    add("Model", "PhaseNet", [])
    add("Model", "EQTransformer", [])
    add("Model", "DBSCAN", [])
    add("Model", "多主体仿真", ["Multi-agent simulation"])
    add("Model", "QuakeWake", [])
    add("Model", "E3WS", [])

    for name, aliases in [
        ("USGS ComCat", ["ComCat", "USGS Earthquake Catalog"]),
        ("CENC 地震目录", ["CENC", "China Earthquake Networks Center", "中国地震台网中心"]),
        ("JMA 地震目录", ["JMA", "Japan Meteorological Agency", "日本气象厅"]),
        ("ShakeMap", ["USGS ShakeMap"]),
        ("PAGER", ["Prompt Assessment of Global Earthquakes for Response"]),
        ("Finite Fault Model", ["finite fault model", "断层模型"]),
        ("WorldPop", ["population exposure"]),
        ("xBD", ["xView2", "xBD dataset"]),
        ("Copernicus EMS", ["Copernicus Emergency Management Service"]),
        ("ALOS-2-BDE", ["ALOS-2 Building Damage Estimation", "PALSAR-2"]),
        ("Sentinel-1", ["Sentinel-1 SAR"]),
        ("PALSAR-2", ["PALSAR"]),
        ("OpenStreetMap", ["OSM"]),
        ("建筑物足迹", ["Building Footprint", "building footprint"]),
        ("台站波形数据", ["seismic waveform", "waveform data"]),
        ("MEMS 加速度计", ["MEMS accelerometer", "smartphone sensors"]),
        ("Vs30", ["site condition", "场地条件"]),
        ("人口暴露格网", ["population grid", "人口暴露"]),
        ("生命线设施数据", ["lifeline infrastructure", "critical infrastructure"]),
        ("道路网络", ["road network"]),
        ("避难所数据", ["shelter data"]),
        ("强震动记录", ["strong motion record"]),
        ("Uncertainty Grid", ["uncertainty grid"]),
    ]:
        add("Dataset", name, aliases)

    for name, aliases in [
        ("P 波起始拾取", ["P-wave onset detection", "P wave onset"]),
        ("地震监测预警", ["earthquake early warning"]),
        ("地震风险评估", ["seismic risk assessment"]),
        ("震后建筑损毁识别", ["building damage recognition"]),
        ("震后灾情快速评估", ["rapid impact assessment"]),
        ("人员伤亡估计", ["fatality estimate", "casualty estimate"]),
        ("经济损失估计", ["economic loss estimate"]),
        ("应急响应分级", ["response level"]),
        ("救援路径规划", ["rescue routing"]),
        ("物资调度优化", ["relief allocation"]),
        ("生命线风险传播分析", ["lifeline risk propagation"]),
        ("政策合规映射", ["policy compliance mapping"]),
        ("证据问答", ["evidence QA", "GraphRAG QA"]),
        ("地震动模拟", ["ground motion simulation"]),
    ]:
        add("Task", name, aliases)

    for name, aliases in [
        ("2024 年日本能登半岛地震", ["Noto Peninsula earthquake", "能登半岛地震"]),
        ("2023 年土耳其-叙利亚地震", ["Türkiye-Syria earthquake", "Turkey-Syria earthquake", "土耳其-叙利亚"]),
        ("2023 年土耳其 Elbistan 大震", ["Elbistan earthquake"]),
        ("2015 年尼泊尔廓尔喀地震", ["Gorkha earthquake", "Nepal earthquake"]),
        ("2021 年海地地震", ["Haiti earthquake"]),
        ("2024 年中国台湾花莲地震", ["Hualien earthquake", "Taiwan earthquake"]),
    ]:
        add("Case", name, aliases)
        add("Event", name, aliases)
    add("Case", "MyShake 地震预警案例", ["MyShake"])
    add("Case", "ShakeAlert 地震预警案例", ["ShakeAlert"])

    for name, aliases in [
        ("Sendai Framework", ["仙台框架", "Sendai Framework for Disaster Risk Reduction"]),
        ("国家地震应急预案", ["National Earthquake Emergency Plan"]),
        ("甘肃省地震应急预案", ["甘肃省地震应急预案"]),
        ("地震预警发布规范", ["earthquake warning standard"]),
        ("应急管理体系现代化规划", ["应急管理体系"]),
    ]:
        add("Policy", name, aliases)

    for name, aliases in [
        ("ISO 22320:2018", ["ISO 22320"]),
        ("OASIS CAP", ["Common Alerting Protocol", "CAP"]),
        ("OGC SensorThings API", ["SensorThings API"]),
        ("DesInventar Sendai", ["DesInventar"]),
    ]:
        add("Standard", name, aliases)

    for name, aliases in [
        ("预警盲区", ["blind zone"]),
        ("误报风险", ["false alarm"]),
        ("漏报风险", ["missed alarm"]),
        ("数据偏差", ["data bias"]),
        ("标注稀缺", ["label scarcity", "annotation scarcity"]),
        ("跨区域泛化不足", ["generalization"]),
        ("实时部署困难", ["real-time deployment"]),
        ("边缘算力约束", ["edge computing constraint"]),
        ("SAR 影像解释不确定性", ["SAR uncertainty"]),
        ("光学影像云层遮挡", ["cloud cover"]),
        ("中等损伤标签混淆", ["moderate damage confusion"]),
        ("来源核验不足", ["source verification"]),
        ("专家复核不足", ["expert review"]),
        ("大模型幻觉风险", ["hallucination"]),
        ("证据链断裂", ["evidence chain"]),
        ("通信延迟", ["communication delay"]),
        ("台站稀疏", ["sparse station"]),
        ("不确定性网格", ["uncertainty grid"]),
    ]:
        add("Limitation", name, aliases)

    for name, aliases in [
        ("USGS", ["United States Geological Survey"]),
        ("CENC", ["China Earthquake Networks Center", "中国地震台网中心"]),
        ("JMA", ["Japan Meteorological Agency"]),
        ("FEMA", ["Federal Emergency Management Agency"]),
        ("GEM", ["Global Earthquake Model"]),
        ("UNDRR", ["United Nations Office for Disaster Risk Reduction"]),
        ("INSARAG", []),
        ("UNDAC", []),
        ("AFAD", []),
        ("WFP", ["World Food Programme"]),
        ("CDRI", ["Coalition for Disaster Resilient Infrastructure"]),
        ("ISO", []),
        ("OGC", []),
        ("OASIS", []),
        ("Taiwan CWA", ["Central Weather Administration"]),
    ]:
        add("Organization", name, aliases)

    for name, aliases in [
        ("PGA", ["Peak Ground Acceleration"]),
        ("PGV", ["Peak Ground Velocity"]),
        ("MMI", ["Modified Mercalli Intensity"]),
        ("AEL", ["Average Economic Loss"]),
        ("AELR", ["Average Economic Loss Ratio"]),
        ("MDF", ["Mean Damage Factor"]),
        ("COV", ["Coefficient of Variation"]),
        ("Vs30", ["time-averaged shear-wave velocity"]),
        ("confidence", ["置信度"]),
        ("震级", ["magnitude"]),
        ("震源深度", ["depth"]),
        ("震中位置", ["epicenter"]),
    ]:
        add("Metric", name, aliases)

    for name, aliases in [
        ("PAGER XML", ["PAGER xml"]),
        ("PAGER 快速评估结果", ["PAGER product"]),
        ("Intensity Contours", ["intensity contours"]),
        ("XML Grid", ["grid.xml"]),
        ("Fault Rupture JSON", ["rupture.json"]),
        ("震损标签图", ["damage label map"]),
    ]:
        add("ImpactProduct", name, aliases)

    return items


def assign_entity_ids(entities: list[EntitySpec]) -> None:
    prefix = {
        "Document": "doc",
        "Evidence": "evidence",
        "DisasterType": "hazard",
        "Case": "case",
        "Event": "event",
        "AITech": "tech",
        "Model": "model",
        "Dataset": "data",
        "Task": "task",
        "Scenario": "stage",
        "Policy": "policy",
        "Standard": "standard",
        "Limitation": "limit",
        "Organization": "org",
        "Metric": "metric",
        "ImpactProduct": "product",
    }
    counters: Counter[str] = Counter()
    for entity in entities:
        counters[entity.type] += 1
        entity.id = f"{prefix.get(entity.type, 'node')}_eq_{counters[entity.type]:03d}"


def aliases_for(entity: EntitySpec) -> list[str]:
    return [entity.name, *entity.aliases]


def contains_alias(text: str, entity: EntitySpec) -> bool:
    lower = text.lower()
    return any(alias and alias.lower() in lower for alias in aliases_for(entity))


def find_alias(text: str, entity: EntitySpec) -> str:
    lower = text.lower()
    for alias in aliases_for(entity):
        if alias and alias.lower() in lower:
            return alias
    return ""


def enrich_entity_evidence(entities: list[EntitySpec], chunks: list[dict[str, Any]]) -> None:
    community_by_type = {
        "AITech": "C01",
        "Model": "C01",
        "Task": "C02",
        "Scenario": "C02",
        "Dataset": "C03",
        "ImpactProduct": "C03",
        "Metric": "C03",
        "Case": "C04",
        "Event": "C04",
        "Policy": "C05",
        "Standard": "C05",
        "Organization": "C05",
        "Limitation": "C06",
        "Document": "C07",
        "Evidence": "C07",
        "DisasterType": "C00",
    }
    for entity in entities:
        doc_ids: set[str] = set()
        chunk_ids: list[str] = []
        for chunk in chunks:
            if contains_alias(chunk["text"], entity):
                doc_ids.add(chunk["doc_id"])
                chunk_ids.append(chunk["chunk_id"])
        entity.doc_ids = sorted(doc_ids)
        entity.chunk_ids = chunk_ids[:20]
        entity.evidence_count = len(chunk_ids)
        entity.community_id = community_by_type.get(entity.type, "C99")
        base_score = 8 if entity.name in REQUIRED_KEY_ENTITY_NAMES else 0
        entity.score = float(base_score + min(10, entity.evidence_count))


REQUIRED_KEY_ENTITY_NAMES = {
    "ShakeMap",
    "PAGER",
    "xBD",
    "Copernicus EMS",
    "ALOS-2-BDE",
    "Edge-AI CNN",
    "OpenQuake",
    "Hazus",
    "Sendai Framework",
    "ISO 22320:2018",
    "预警盲区",
    "数据偏差",
    "标注稀缺",
}


def relation_candidates() -> list[RelationCandidate]:
    rc = RelationCandidate
    items = [
        rc("地震早期预警", "SERVES_STAGE", "震时预警", "EQ_DOC_007"),
        rc("地震早期预警", "SOLVES", "地震监测预警", "EQ_DOC_007"),
        rc("地震早期预警", "DEPENDS_ON", "台站波形数据", "EQ_DOC_007"),
        rc("分布式AI地震预警", "SOLVES", "地震监测预警", "EQ_DOC_007"),
        rc("分布式AI地震预警", "SERVES_STAGE", "震时预警", "EQ_DOC_007"),
        rc("分布式AI地震预警", "USES_MODEL", "Edge-AI CNN", "EQ_DOC_007"),
        rc("分布式AI地震预警", "USES_MODEL", "PhaseNet", "EQ_DOC_007"),
        rc("分布式AI地震预警", "USES_MODEL", "EQTransformer", "EQ_DOC_007"),
        rc("分布式AI地震预警", "USES_MODEL", "QuakeWake", "EQ_DOC_007"),
        rc("分布式AI地震预警", "USES_MODEL", "E3WS", "EQ_DOC_007"),
        rc("分布式AI地震预警", "USES_MODEL", "DBSCAN", "EQ_DOC_007"),
        rc("分布式AI地震预警", "DEPENDS_ON", "MEMS 加速度计", "EQ_DOC_007"),
        rc("分布式AI地震预警", "DEPENDS_ON", "台站波形数据", "EQ_DOC_007"),
        rc("分布式AI地震预警", "LIMITED_BY", "预警盲区", "EQ_DOC_007"),
        rc("分布式AI地震预警", "LIMITED_BY", "通信延迟", "EQ_DOC_007"),
        rc("Edge-AI CNN", "SOLVES", "P 波起始拾取", "EQ_DOC_007"),
        rc("地震风险时空预测", "SERVES_STAGE", "震前监测", "EQ_DOC_002"),
        rc("地震风险时空预测", "SOLVES", "地震风险评估", "EQ_DOC_008"),
        rc("地震风险时空预测", "DEPENDS_ON", "USGS ComCat", "EQ_DOC_002"),
        rc("地震风险时空预测", "DEPENDS_ON", "CENC 地震目录", "EQ_DOC_002"),
        rc("地震风险时空预测", "DEPENDS_ON", "强震动记录", "EQ_DOC_003"),
        rc("ShakeMap", "DEPENDS_ON", "Finite Fault Model", "EQ_DOC_003"),
        rc("ShakeMap", "DEPENDS_ON", "Vs30", "EQ_DOC_003"),
        rc("ShakeMap", "HAS_METRIC", "PGA", "EQ_DOC_003"),
        rc("ShakeMap", "HAS_METRIC", "PGV", "EQ_DOC_003"),
        rc("ShakeMap", "HAS_METRIC", "MMI", "EQ_DOC_003"),
        rc("ShakeMap", "HAS_IMPACT", "Intensity Contours", "EQ_DOC_003"),
        rc("ShakeMap", "HAS_IMPACT", "XML Grid", "EQ_DOC_003"),
        rc("ShakeMap", "HAS_IMPACT", "Fault Rupture JSON", "EQ_DOC_003"),
        rc("PAGER", "DEPENDS_ON", "ShakeMap", "EQ_DOC_003"),
        rc("PAGER", "DEPENDS_ON", "WorldPop", "EQ_DOC_003"),
        rc("PAGER", "SOLVES", "人员伤亡估计", "EQ_DOC_003"),
        rc("PAGER", "SOLVES", "经济损失估计", "EQ_DOC_003"),
        rc("PAGER", "HAS_IMPACT", "PAGER XML", "EQ_DOC_003"),
        rc("PAGER", "HAS_IMPACT", "PAGER 快速评估结果", "EQ_DOC_003"),
        rc("PAGER", "VALIDATED_IN", "2023 年土耳其-叙利亚地震", "EQ_DOC_002"),
        rc("ShakeMap", "VALIDATED_IN", "2024 年日本能登半岛地震", "EQ_DOC_002"),
        rc("震后灾情快速评估", "SERVES_STAGE", "震后评估", "EQ_DOC_003"),
        rc("震后灾情快速评估", "DEPENDS_ON", "ShakeMap", "EQ_DOC_003"),
        rc("震后灾情快速评估", "DEPENDS_ON", "PAGER", "EQ_DOC_003"),
        rc("震后灾情快速评估", "SOLVES", "人员伤亡估计", "EQ_DOC_003"),
        rc("震后灾情快速评估", "SOLVES", "经济损失估计", "EQ_DOC_003"),
        rc("震后建筑损毁识别", "SERVES_STAGE", "震后评估", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "DEPENDS_ON", "xBD", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "DEPENDS_ON", "Copernicus EMS", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "DEPENDS_ON", "ALOS-2-BDE", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "DEPENDS_ON", "Sentinel-1", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "DEPENDS_ON", "PALSAR-2", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "DEPENDS_ON", "OpenStreetMap", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "DEPENDS_ON", "建筑物足迹", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "SOLVES", "震后建筑损毁识别", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "USES_MODEL", "CNN", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "USES_MODEL", "U-Net", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "USES_MODEL", "Transformer", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "LIMITED_BY", "光学影像云层遮挡", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "LIMITED_BY", "SAR 影像解释不确定性", "EQ_DOC_005"),
        rc("震后建筑损毁识别", "LIMITED_BY", "中等损伤标签混淆", "EQ_DOC_005"),
        rc("xBD", "HAS_IMPACT", "震损标签图", "EQ_DOC_005"),
        rc("ALOS-2-BDE", "VALIDATED_IN", "2024 年日本能登半岛地震", "EQ_DOC_005"),
        rc("遥感震损智能解译", "SERVES_STAGE", "震后评估", "EQ_DOC_005"),
        rc("遥感震损智能解译", "SOLVES", "震后建筑损毁识别", "EQ_DOC_005"),
        rc("遥感震损智能解译", "DEPENDS_ON", "xBD", "EQ_DOC_005"),
        rc("遥感震损智能解译", "DEPENDS_ON", "Copernicus EMS", "EQ_DOC_005"),
        rc("遥感震损智能解译", "DEPENDS_ON", "ALOS-2-BDE", "EQ_DOC_005"),
        rc("遥感震损智能解译", "DEPENDS_ON", "Sentinel-1", "EQ_DOC_005"),
        rc("遥感震损智能解译", "LIMITED_BY", "SAR 影像解释不确定性", "EQ_DOC_005"),
        rc("生命线震损风险传播GNN", "USES_MODEL", "GNN", "EQ_DOC_006"),
        rc("生命线震损风险传播GNN", "DEPENDS_ON", "生命线设施数据", "EQ_DOC_006"),
        rc("生命线震损风险传播GNN", "DEPENDS_ON", "道路网络", "EQ_DOC_006"),
        rc("生命线震损风险传播GNN", "DEPENDS_ON", "OpenStreetMap", "EQ_DOC_006"),
        rc("生命线震损风险传播GNN", "SOLVES", "生命线风险传播分析", "EQ_DOC_006"),
        rc("生命线震损风险传播GNN", "SERVES_STAGE", "城市韧性评估", "EQ_DOC_006"),
        rc("数字孪生城市地震风险模拟", "USES_MODEL", "OpenQuake", "EQ_DOC_008"),
        rc("数字孪生城市地震风险模拟", "USES_MODEL", "Hazus", "EQ_DOC_008"),
        rc("数字孪生城市地震风险模拟", "SOLVES", "地震风险评估", "EQ_DOC_008"),
        rc("数字孪生城市地震风险模拟", "DEPENDS_ON", "生命线设施数据", "EQ_DOC_006"),
        rc("数字孪生城市地震风险模拟", "SERVES_STAGE", "城市韧性评估", "EQ_DOC_008"),
        rc("震后救援调度优化", "SERVES_STAGE", "应急响应", "EQ_DOC_004"),
        rc("震后救援调度优化", "SOLVES", "救援路径规划", "EQ_DOC_004"),
        rc("震后救援调度优化", "SOLVES", "物资调度优化", "EQ_DOC_004"),
        rc("震后救援调度优化", "SOLVES", "应急响应分级", "EQ_DOC_009"),
        rc("震后救援调度优化", "DEPENDS_ON", "道路网络", "EQ_DOC_006"),
        rc("震后救援调度优化", "DEPENDS_ON", "避难所数据", "EQ_DOC_004"),
        rc("震后救援调度优化", "VALIDATED_IN", "2023 年土耳其-叙利亚地震", "EQ_DOC_004"),
        rc("震后救援调度优化", "REQUIRED_BY", "Sendai Framework", "EQ_DOC_009"),
        rc("地震应急辅助决策", "SERVES_STAGE", "应急响应", "EQ_DOC_004"),
        rc("地震应急辅助决策", "SOLVES", "应急响应分级", "EQ_DOC_009"),
        rc("地震应急辅助决策", "DEPENDS_ON", "PAGER", "EQ_DOC_003"),
        rc("地震应急辅助决策", "DEPENDS_ON", "ShakeMap", "EQ_DOC_003"),
        rc("地震应急辅助决策", "REQUIRED_BY", "ISO 22320:2018", "EQ_DOC_009"),
        rc("地震应急辅助决策", "REQUIRED_BY", "Sendai Framework", "EQ_DOC_009"),
        rc("Hazus", "USES_MODEL", "能力谱法", "EQ_DOC_008"),
        rc("Hazus", "SOLVES", "经济损失估计", "EQ_DOC_008"),
        rc("OpenQuake", "SOLVES", "地震风险评估", "EQ_DOC_008"),
        rc("OpenQuake", "EVALUATED_BY", "PGA", "EQ_DOC_008"),
        rc("OpenQuake", "HAS_METRIC", "AEL", "EQ_DOC_008"),
        rc("OpenQuake", "HAS_METRIC", "AELR", "EQ_DOC_008"),
        rc("OpenQuake", "HAS_METRIC", "MDF", "EQ_DOC_008"),
        rc("OpenQuake", "HAS_METRIC", "COV", "EQ_DOC_008"),
        rc("政策合规映射", "REQUIRED_BY", "Sendai Framework", "EQ_DOC_009"),
        rc("应急响应分级", "REQUIRED_BY", "ISO 22320:2018", "EQ_DOC_009"),
        rc("地震监测预警", "REQUIRED_BY", "OASIS CAP", "EQ_DOC_009"),
        rc("台站波形数据", "REQUIRED_BY", "OGC SensorThings API", "EQ_DOC_009"),
        rc("国家地震应急预案", "REQUIRED_BY", "Sendai Framework", "EQ_DOC_009"),
        rc("地震证据图谱GraphRAG", "SOLVES", "证据问答", "EQ_DOC_010"),
        rc("地震证据图谱GraphRAG", "DERIVES_FROM", "本体与复核机制", "EQ_DOC_010"),
        rc("地震证据图谱GraphRAG", "LIMITED_BY", "大模型幻觉风险", "EQ_DOC_010"),
        rc("地震证据图谱GraphRAG", "LIMITED_BY", "证据链断裂", "EQ_DOC_010"),
        rc("地震证据图谱GraphRAG", "LIMITED_BY", "专家复核不足", "EQ_DOC_010"),
        rc("地震证据图谱GraphRAG", "SUPPORTED_BY", "原始来源核验机制", "EQ_DOC_010"),
        rc("USGS ComCat", "PUBLISHED_BY", "USGS", "EQ_DOC_001"),
        rc("ShakeMap", "PUBLISHED_BY", "USGS", "EQ_DOC_003"),
        rc("PAGER", "PUBLISHED_BY", "USGS", "EQ_DOC_003"),
        rc("CENC 地震目录", "PUBLISHED_BY", "CENC", "EQ_DOC_001"),
        rc("JMA 地震目录", "PUBLISHED_BY", "JMA", "EQ_DOC_001"),
        rc("Hazus", "PUBLISHED_BY", "FEMA", "EQ_DOC_008"),
        rc("OpenQuake", "PUBLISHED_BY", "GEM", "EQ_DOC_008"),
        rc("Sendai Framework", "PUBLISHED_BY", "UNDRR", "EQ_DOC_009"),
        rc("ISO 22320:2018", "PUBLISHED_BY", "ISO", "EQ_DOC_009"),
        rc("OASIS CAP", "PUBLISHED_BY", "OASIS", "EQ_DOC_009"),
        rc("OGC SensorThings API", "PUBLISHED_BY", "OGC", "EQ_DOC_009"),
        rc("2024 年日本能登半岛地震", "HAS_PARAMETER", "震级", "EQ_DOC_002"),
        rc("2024 年日本能登半岛地震", "HAS_PARAMETER", "震源深度", "EQ_DOC_002"),
        rc("2024 年日本能登半岛地震", "HAS_PARAMETER", "震中位置", "EQ_DOC_002"),
    ]
    return items


def snippet_around(text: str, terms: list[str], limit: int = 220) -> str:
    clean = normalize_text(text)
    lower = clean.lower()
    positions = [lower.find(term.lower()) for term in terms if term and term.lower() in lower]
    if not positions:
        return clean[:limit]
    start = max(0, min(positions) - 70)
    end = min(len(clean), max(positions) + 150)
    snippet = clean[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(clean):
        snippet += "..."
    return snippet[:limit]


def same_sentence(text: str, terms: list[str]) -> bool:
    sentences = [part.strip() for part in re.split(r"[。！？.!?；;]\s*", text) if part.strip()]
    for sentence in sentences:
        lower = sentence.lower()
        if all(term.lower() in lower for term in terms if term):
            return True
    return False


def locate_evidence(
    head: EntitySpec,
    tail: EntitySpec,
    chunks: list[dict[str, Any]],
    preferred_doc_id: str = "",
) -> tuple[dict[str, Any], str, float] | None:
    ordered = sorted(chunks, key=lambda item: 0 if item["doc_id"] == preferred_doc_id else 1)
    for chunk in ordered:
        text = chunk["text"]
        head_alias = find_alias(text, head)
        tail_alias = find_alias(text, tail)
        if head_alias and tail_alias:
            confidence = 0.90 if same_sentence(text, [head_alias, tail_alias]) else 0.75
            return chunk, snippet_around(text, [head_alias, tail_alias]), confidence
    if preferred_doc_id:
        for chunk in ordered:
            if chunk["doc_id"] != preferred_doc_id:
                continue
            text = chunk["text"]
            head_alias = find_alias(text, head)
            tail_alias = find_alias(text, tail)
            evidence_terms = [term for term in [head_alias, tail_alias] if term]
            if evidence_terms:
                return chunk, snippet_around(text, evidence_terms), 0.60
    return None


def locate_single_entity_evidence(entity: EntitySpec, chunks: list[dict[str, Any]], doc_id: str = "") -> tuple[dict[str, Any], str] | None:
    ordered = sorted(chunks, key=lambda item: 0 if item["doc_id"] == doc_id else 1)
    for chunk in ordered:
        alias = find_alias(chunk["text"], entity)
        if alias:
            return chunk, snippet_around(chunk["text"], [alias])
    return None


def build_entities(documents: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> list[EntitySpec]:
    entities = [EntitySpec(type="Document", name=doc["title"], aliases=[doc["doc_id"]], description=f"地震专题语料文档：{doc['topic']}") for doc in documents]
    entities.extend(entity_specs())
    assign_entity_ids(entities)
    for doc_entity, doc in zip([e for e in entities if e.type == "Document"], documents):
        doc_entity.id = doc["doc_id"]
        doc_entity.doc_ids = [doc["doc_id"]]
        doc_entity.evidence_count = sum(1 for chunk in chunks if chunk["doc_id"] == doc["doc_id"])
        doc_entity.community_id = "C07"
    enrich_entity_evidence([entity for entity in entities if entity.type != "Document"], chunks)
    return entities


def build_relations(entities: list[EntitySpec], chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[EntitySpec]]:
    by_id = {entity.id: entity for entity in entities}
    entities_by_name: dict[str, list[EntitySpec]] = defaultdict(list)
    for entity in entities:
        entities_by_name[entity.name].append(entity)
    relations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    tail_type_priority = {
        "USES_MODEL": ["Model"],
        "DEPENDS_ON": ["Dataset", "ImpactProduct", "Metric", "Model"],
        "SOLVES": ["Task"],
        "SERVES_STAGE": ["Scenario"],
        "VALIDATED_IN": ["Case", "Event"],
        "LIMITED_BY": ["Limitation"],
        "REQUIRED_BY": ["Policy", "Standard"],
        "SUPPORTED_BY": ["Evidence"],
        "DERIVES_FROM": ["Document"],
        "MEASURED_BY": ["Metric"],
        "EVALUATED_BY": ["Metric", "Task"],
        "PUBLISHED_BY": ["Organization"],
        "HAS_METRIC": ["Metric"],
        "HAS_PARAMETER": ["Metric"],
        "HAS_IMPACT": ["ImpactProduct"],
    }

    def pick_entity(name: str, relation_type: str, role: str) -> EntitySpec | None:
        options = entities_by_name.get(name, [])
        if not options:
            return None
        if role == "tail":
            for preferred_type in tail_type_priority.get(relation_type, []):
                match = next((entity for entity in options if entity.type == preferred_type), None)
                if match:
                    return match
        non_documents = [entity for entity in options if entity.type != "Document"]
        if non_documents:
            return non_documents[0]
        return options[0]

    def add_relation(head: EntitySpec, relation_type: str, tail: EntitySpec, chunk: dict[str, Any], evidence_text: str, confidence: float) -> None:
        key = (head.id, relation_type, tail.id)
        if key in seen:
            return
        seen.add(key)
        relations.append(
            {
                "relation_id": f"REL_EQ_{len(relations) + 1:06d}",
                "source": head.id,
                "target": tail.id,
                "source_id": head.id,
                "target_id": tail.id,
                "head_id": head.id,
                "tail_id": tail.id,
                "head": head.name,
                "tail": tail.name,
                "head_name": head.name,
                "tail_name": tail.name,
                "head_type": head.type,
                "tail_type": tail.type,
                "relation_type": relation_type,
                "relation_label": f"{relation_type}（{RELATION_CN.get(relation_type, relation_type)}）",
                "confidence": round(confidence, 2),
                "doc_id": chunk["doc_id"],
                "chunk_id": chunk["chunk_id"],
                "source_name": chunk["document_title"],
                "source_file": SOURCE_DOCX.name,
                "evidence_text": evidence_text,
                "extraction_method": "规则抽取",
                "expert_status": "待复核",
                "review_status": "待复核",
            }
        )

    for candidate in relation_candidates():
        head = pick_entity(candidate.head, candidate.relation_type, "head")
        tail = pick_entity(candidate.tail, candidate.relation_type, "tail")
        if not head or not tail:
            continue
        located = locate_evidence(head, tail, chunks, candidate.preferred_doc_id)
        if located:
            chunk, evidence_text, confidence = located
            add_relation(head, candidate.relation_type, tail, chunk, evidence_text, confidence)

    document_entities = {doc.name: doc for doc in entities if doc.type == "Document"}
    doc_by_id = {doc.id: doc for doc in entities if doc.type == "Document"}
    for entity in entities:
        if entity.type in {"Document", "Evidence"}:
            continue
        for doc_id in entity.doc_ids[:3]:
            doc_entity = doc_by_id.get(doc_id)
            located = locate_single_entity_evidence(entity, chunks, doc_id)
            if doc_entity and located:
                chunk, evidence_text = located
                add_relation(entity, "DERIVES_FROM", doc_entity, chunk, evidence_text, 0.75)

    evidence_nodes: list[EntitySpec] = []
    for relation in relations[:40]:
        evidence = EntitySpec(
            type="Evidence",
            name=f"证据片段{len(evidence_nodes) + 1:03d}",
            aliases=[relation["chunk_id"], relation["relation_id"]],
            description=relation["evidence_text"][:120],
            id=f"evidence_eq_{len(evidence_nodes) + 1:03d}",
            doc_ids=[relation["doc_id"]],
            chunk_ids=[relation["chunk_id"]],
            evidence_count=1,
            community_id="C07",
            score=1.0,
        )
        evidence_nodes.append(evidence)
        head_entity = by_id.get(relation["head_id"])
        if not head_entity:
            continue
        add_relation(
            head_entity,
            "SUPPORTED_BY",
            evidence,
            next(chunk for chunk in chunks if chunk["chunk_id"] == relation["chunk_id"]),
            relation["evidence_text"],
            relation["confidence"],
        )

    entities.extend(evidence_nodes)

    degree = Counter()
    evidence_counts = Counter()
    for relation in relations:
        degree[relation["head_id"]] += 1
        degree[relation["tail_id"]] += 1
        if relation["evidence_text"]:
            evidence_counts[relation["head_id"]] += 1
            evidence_counts[relation["tail_id"]] += 1
    for entity in entities:
        entity.relation_count = degree[entity.id]
        entity.evidence_count = max(entity.evidence_count, evidence_counts[entity.id])
        if entity.score <= 0:
            entity.score = float(min(10, entity.evidence_count) + math.log1p(entity.relation_count))
    return relations, evidence_nodes


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        fieldnames = fields
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def entity_to_row(entity: EntitySpec) -> dict[str, Any]:
    return {
        "entity_id": entity.id,
        "id": entity.id,
        "name": entity.name,
        "label": entity.name,
        "entity_type": entity.type,
        "type": entity.type,
        "aliases": "；".join(entity.aliases),
        "description": entity.description or f"{entity.type}：{entity.name}",
        "doc_ids": "；".join(entity.doc_ids),
        "chunk_ids": "；".join(entity.chunk_ids),
        "community_id": entity.community_id,
        "community": entity.community_id,
        "evidence_count": entity.evidence_count,
        "relation_count": entity.relation_count,
        "review_status": "待复核",
        "score": round(entity.score, 2),
    }


def build_claims(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims = []
    for index, relation in enumerate(relations, 1):
        claims.append(
            {
                "claim_id": f"CLM_EQ_{index:06d}",
                "relation_id": relation["relation_id"],
                "claim_text": f"{relation['head_name']} {relation['relation_label']} {relation['tail_name']}",
                "doc_id": relation["doc_id"],
                "chunk_id": relation["chunk_id"],
                "evidence_text": relation["evidence_text"],
                "confidence": relation["confidence"],
                "expert_status": "待复核",
                "source_file": SOURCE_DOCX.name,
            }
        )
    return claims


def build_communities(entities: list[EntitySpec], relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    definitions = {
        "C00": ("地震灾害背景", "聚合地震灾害类型和基础事件参数。"),
        "C01": ("AI技术与模型方法", "聚合预警、震损识别、风险模拟等AI技术及模型。"),
        "C02": ("任务场景链", "聚合震前、震时、震后和治理阶段的任务节点。"),
        "C03": ("数据与影响产品", "聚合ShakeMap、PAGER、遥感、暴露体和指标产品。"),
        "C04": ("地震案例事件", "聚合典型地震事件和验证案例。"),
        "C05": ("组织政策标准", "聚合政策、标准和发布机构。"),
        "C06": ("限制与复核风险", "聚合预警盲区、数据偏差、标注稀缺等风险。"),
        "C07": ("语料与证据链", "聚合文档来源、文本块和证据片段。"),
    }
    entity_by_id = {entity.id: entity for entity in entities}
    relation_by_community: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relation in relations:
        community = entity_by_id.get(relation["head_id"], EntitySpec("", "")).community_id or "C99"
        relation_by_community[community].append(relation)
    reports = []
    for community_id, (title, summary) in definitions.items():
        members = [entity for entity in entities if entity.community_id == community_id]
        rels = relation_by_community.get(community_id, [])
        reports.append(
            {
                "community_id": community_id,
                "title": title,
                "summary": summary,
                "entity_count": len(members),
                "relation_count": len(rels),
                "representative_entities": "；".join(entity.name for entity in sorted(members, key=lambda item: item.score, reverse=True)[:8]),
                "evidence_sources": "；".join(sorted({relation["source_name"] for relation in rels})[:6]),
                "open_questions": "低置信度关系需由专家复核；跨来源冲突需回到原始文档核验。",
                "review_focus": "检查关系方向、证据片段是否支持三元组，以及英文专名中文解释是否准确。",
            }
        )
    return reports


def build_quality_report(
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    entities: list[EntitySpec],
    relations: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    communities: list[dict[str, Any]],
    docx_meta: dict[str, Any],
    archive_dir: Path,
) -> dict[str, Any]:
    low_confidence = [relation for relation in relations if relation["confidence"] < 0.75]
    missing_key_entities = [name for name in sorted(REQUIRED_KEY_ENTITY_NAMES) if not any(entity.name == name for entity in entities)]
    required_type_counts = Counter(entity.type for entity in entities)
    relation_type_counts = Counter(relation["relation_type"] for relation in relations)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": str(SOURCE_DOCX),
        "archive_dir": str(archive_dir),
        "docx_meta": docx_meta,
        "corpus_count": len(documents),
        "chunk_count": len(chunks),
        "entity_count": len(entities),
        "relation_count": len(relations),
        "claim_count": len(claims),
        "community_count": len(communities),
        "evidence_edge_count": len([relation for relation in relations if relation["evidence_text"]]),
        "low_confidence_relation_count": len(low_confidence),
        "required_entity_type_coverage": {key: required_type_counts.get(key, 0) for key in REQUIRED_ENTITY_TYPES},
        "required_relation_type_coverage": {key: relation_type_counts.get(key, 0) for key in REQUIRED_RELATION_TYPES},
        "missing_key_entities": missing_key_entities,
        "quality_status": "待复核",
        "notes": [
            "本轮索引基于新增 Word 的正文和表格内容生成。",
            "Word 中图片仅统计数量，未自动抽取图片像素内容。",
            "所有关系保留 doc_id、chunk_id、证据片段、置信度和待复核状态。",
        ],
    }


def build_qa_set() -> list[dict[str, Any]]:
    questions = [
        ("ShakeMap 依赖哪些地震动或场地数据？", "ShakeMap 依赖 Finite Fault Model、Vs30 等数据，并输出 PGA、PGV、MMI 等指标。"),
        ("PAGER 如何利用 ShakeMap 进行快速影响评估？", "PAGER 以 ShakeMap 烈度网格为输入之一，结合人口暴露和脆弱性模型估计人员伤亡与经济损失。"),
        ("xBD 在地震震损识别中有什么用途？", "xBD 提供灾前灾后遥感影像和建筑损毁标签，可用于训练震后建筑损毁识别模型。"),
        ("Copernicus EMS 对灾后遥感制图有什么作用？", "Copernicus EMS 提供应急制图产品，可作为灾后影响范围和建筑损毁核验资料。"),
        ("ALOS-2-BDE 适用于哪类震损分析？", "ALOS-2-BDE 利用 SAR 数据支持建筑损坏估计，适合补充光学影像受云层遮挡的场景。"),
        ("分布式AI地震预警依赖哪些数据？", "依赖台站波形数据、MEMS 加速度计等实时观测数据。"),
        ("Edge-AI CNN 主要解决什么任务？", "主要面向边缘侧 P 波起始拾取和快速触发判断。"),
        ("预警盲区为什么需要复核？", "预警盲区与震中附近可用预警时间不足有关，会影响预警系统的实际覆盖。"),
        ("Hazus 与 OpenQuake 的区别是什么？", "Hazus 偏工程损失估计流程，OpenQuake 偏概率地震危险性和风险计算引擎。"),
        ("Sendai Framework 在图谱中属于什么节点？", "属于政策节点，用于应急治理和政策合规映射。"),
        ("ISO 22320:2018 在图谱中用于什么？", "属于标准节点，可支撑应急响应分级和组织协同流程。"),
        ("数据偏差会影响哪些地震AI任务？", "会影响震损识别、风险评估和预警模型跨区域泛化。"),
        ("标注稀缺对震损识别有什么影响？", "会限制监督学习模型训练和中等损伤类别识别效果。"),
        ("GraphRAG 在本项目中解决什么问题？", "用于把实体、关系、证据片段和社区报告组织成可追溯问答图谱。"),
        ("PGA、PGV、MMI 是什么类型节点？", "属于 Metric 指标节点，用于描述 ShakeMap 等产品的地震动或烈度输出。"),
        ("OpenStreetMap 在地震图谱中有什么作用？", "作为建筑物足迹、道路网络和暴露体空间数据来源。"),
        ("生命线震损风险传播GNN 依赖什么数据？", "依赖生命线设施数据、道路网络和地理空间暴露数据。"),
        ("专家复核表主要检查什么？", "检查关系方向、证据片段、置信度和抽取方法是否可靠。"),
        ("为什么需要归档旧索引？", "为了保留重建前的图谱成果，便于版本追溯和回滚核验。"),
        ("本轮新增资料如何发布到前端？", "生成 public/atlas/atlas_frontend.json 和 public/atlas/index_summary.json，前端直接读取展示。"),
    ]
    return [
        {
            "qa_id": f"QA_EQ_{index:03d}",
            "question": question,
            "expected_answer": answer,
            "query_focus": "地震灾害知识图谱",
            "source_file": SOURCE_DOCX.name,
            "review_status": "待复核",
        }
        for index, (question, answer) in enumerate(questions, 1)
    ]


def write_graphml(path: Path, entities: list[EntitySpec], relations: list[dict[str, Any]]) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="name" for="node" attr.name="name" attr.type="string"/>',
        '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
        '  <key id="relation_type" for="edge" attr.name="relation_type" attr.type="string"/>',
        '  <key id="confidence" for="edge" attr.name="confidence" attr.type="double"/>',
        '  <graph id="earthquake_atlas" edgedefault="directed">',
    ]
    for entity in entities:
        lines.extend(
            [
                f'    <node id="{html.escape(entity.id)}">',
                f'      <data key="name">{html.escape(entity.name)}</data>',
                f'      <data key="type">{html.escape(entity.type)}</data>',
                "    </node>",
            ]
        )
    for relation in relations:
        lines.extend(
            [
                f'    <edge id="{html.escape(relation["relation_id"])}" source="{html.escape(relation["head_id"])}" target="{html.escape(relation["tail_id"])}">',
                f'      <data key="relation_type">{html.escape(relation["relation_type"])}</data>',
                f'      <data key="confidence">{relation["confidence"]}</data>',
                "    </edge>",
            ]
        )
    lines.extend(["  </graph>", "</graphml>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_neo4j_import(path: Path) -> None:
    content = """// Neo4j 导入脚本：从 outputs/graphrag_index 导入地震灾害知识图谱
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///graph_nodes.csv' AS row
MERGE (n:Entity {entity_id: row.entity_id})
SET n.name = row.name,
    n.entity_type = row.entity_type,
    n.description = row.description,
    n.community_id = row.community_id,
    n.review_status = row.review_status;

LOAD CSV WITH HEADERS FROM 'file:///graph_edges_neo4j.csv' AS row
MATCH (s:Entity {entity_id: row.source_id})
MATCH (t:Entity {entity_id: row.target_id})
MERGE (s)-[r:RELATED {relation_id: row.relation_id}]->(t)
SET r.relation_type = row.relation_type,
    r.confidence = toFloat(row.confidence),
    r.doc_id = row.doc_id,
    r.chunk_id = row.chunk_id,
    r.evidence_text = row.evidence_text,
    r.review_status = row.review_status;
"""
    path.write_text(content, encoding="utf-8")


def write_ontology(entities: list[EntitySpec]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        if entity.type in {"Evidence", "Document"}:
            continue
        grouped[entity.type].append({"id": entity.id, "name": entity.name, "aliases": entity.aliases})
    ontology = {
        "entity_types": REQUIRED_ENTITY_TYPES,
        "relation_types": REQUIRED_RELATION_TYPES,
        "entities": {entity_type: grouped.get(entity_type, []) for entity_type in REQUIRED_ENTITY_TYPES},
        "relation_rules": [
            {"source_type": "AITech", "target_type": "Model", "relation_type": "USES_MODEL", "confidence": 0.64},
            {"source_type": "AITech", "target_type": "Dataset", "relation_type": "DEPENDS_ON", "confidence": 0.66},
            {"source_type": "AITech", "target_type": "Task", "relation_type": "SOLVES", "confidence": 0.70},
            {"source_type": "AITech", "target_type": "Scenario", "relation_type": "SERVES_STAGE", "confidence": 0.68},
            {"source_type": "Dataset", "target_type": "Organization", "relation_type": "PUBLISHED_BY", "confidence": 0.62},
            {"source_type": "Task", "target_type": "Policy", "relation_type": "REQUIRED_BY", "confidence": 0.58},
            {"source_type": "Dataset", "target_type": "Metric", "relation_type": "HAS_METRIC", "confidence": 0.72},
            {"source_type": "Case", "target_type": "Metric", "relation_type": "HAS_PARAMETER", "confidence": 0.72},
        ],
        "quality_status": "待复核",
        "source_file": SOURCE_DOCX.name,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    ONTOLOGY_PATH.write_text(json.dumps(ontology, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_outputs(
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    entities: list[EntitySpec],
    relations: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    communities: list[dict[str, Any]],
    qa_rows: list[dict[str, Any]],
    quality: dict[str, Any],
) -> dict[str, Any]:
    entity_rows = [entity_to_row(entity) for entity in entities]
    relation_rows = relations

    write_csv(OUTPUT_DIR / "corpus_manifest.csv", documents)
    write_jsonl(OUTPUT_DIR / "documents.jsonl", documents)
    write_jsonl(OUTPUT_DIR / "chunks.jsonl", chunks)
    write_csv(OUTPUT_DIR / "chunks.csv", chunks)
    write_jsonl(OUTPUT_DIR / "entities.jsonl", entity_rows)
    write_jsonl(OUTPUT_DIR / "relations.jsonl", relation_rows)
    write_jsonl(OUTPUT_DIR / "claims.jsonl", claims)
    write_csv(OUTPUT_DIR / "claims.csv", claims)
    write_csv(OUTPUT_DIR / "graph_nodes.csv", entity_rows)
    write_csv(OUTPUT_DIR / "graph_edges.csv", relation_rows)
    write_csv(OUTPUT_DIR / "graph_edges_neo4j.csv", relation_rows)
    write_csv(OUTPUT_DIR / "evidence_edges.csv", relation_rows)
    write_csv(
        OUTPUT_DIR / "technology_nodes.csv",
        [row for row in entity_rows if row["entity_type"] in {"AITech", "Model", "Dataset", "Task"}],
    )
    write_csv(OUTPUT_DIR / "community_reports.csv", communities)
    (OUTPUT_DIR / "community_reports.json").write_text(json.dumps(communities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(OUTPUT_DIR / "community_reports.jsonl", communities)
    write_csv(OUTPUT_DIR / "qa_evaluation_set.csv", qa_rows)
    write_csv(OUTPUT_DIR / "expert_review_log.csv", build_expert_review_log(relations))
    write_csv(OUTPUT_DIR / "expert_review_priority.csv", build_expert_review_priority(relations))
    write_graphml(OUTPUT_DIR / "atlas.graphml", entities, relations)
    write_neo4j_import(OUTPUT_DIR / "neo4j_import.cypher")
    (OUTPUT_DIR / "atlas_quality_report.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "atlas_quality_report.md").write_text(render_quality_markdown(quality), encoding="utf-8")

    summary = build_summary(documents, chunks, entities, relations, claims, communities)
    (OUTPUT_DIR / "index_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    export_dir = OUTPUT_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    for file in OUTPUT_DIR.iterdir():
        if file.is_file() and file.name not in {"运行日志.txt", "索引质量检查.txt"}:
            shutil.copy2(file, export_dir / file.name)

    return summary


def build_expert_review_log(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "review_id": f"REV_EQ_{index:06d}",
            "relation_id": relation["relation_id"],
            "head": relation["head_name"],
            "relation_type": relation["relation_type"],
            "tail": relation["tail_name"],
            "confidence": relation["confidence"],
            "doc_id": relation["doc_id"],
            "chunk_id": relation["chunk_id"],
            "evidence_text": relation["evidence_text"],
            "expert_status": "待复核",
            "review_comment": "",
        }
        for index, relation in enumerate(relations, 1)
    ]


def build_expert_review_priority(relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for relation in relations:
        relation_type_weight = 1.2 if relation["relation_type"] in {"LIMITED_BY", "REQUIRED_BY", "SUPPORTED_BY"} else 1.0
        priority = round((1 - float(relation["confidence"])) * 100 * relation_type_weight, 2)
        rows.append(
            {
                "relation_id": relation["relation_id"],
                "head": relation["head_name"],
                "relation_type": relation["relation_type"],
                "tail": relation["tail_name"],
                "confidence": relation["confidence"],
                "priority_score": priority,
                "priority_reason": "低置信度或治理风险关系优先复核" if priority >= 25 else "常规抽查复核",
                "doc_id": relation["doc_id"],
                "chunk_id": relation["chunk_id"],
                "expert_status": "待复核",
            }
        )
    return sorted(rows, key=lambda row: row["priority_score"], reverse=True)


def render_quality_markdown(quality: dict[str, Any]) -> str:
    lines = [
        "# 地震灾害 GraphRAG 索引质量报告",
        "",
        f"- 生成时间：{quality['generated_at']}",
        f"- 新增资料：{quality['source_file']}",
        f"- 语料文档数：{quality['corpus_count']}",
        f"- 文本块数：{quality['chunk_count']}",
        f"- 节点数：{quality['entity_count']}",
        f"- 关系数：{quality['relation_count']}",
        f"- 声明数：{quality['claim_count']}",
        f"- 社区数：{quality['community_count']}",
        f"- 有证据关系数：{quality['evidence_edge_count']}",
        f"- 低置信度关系数：{quality['low_confidence_relation_count']}",
        "",
        "## 节点类型覆盖",
        "",
    ]
    for key, value in quality["required_entity_type_coverage"].items():
        lines.append(f"- {key}：{value}")
    lines.extend(["", "## 关系类型覆盖", ""])
    for key, value in quality["required_relation_type_coverage"].items():
        lines.append(f"- {key}：{value}")
    lines.extend(["", "## 质量说明", ""])
    for note in quality["notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def build_summary(
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    entities: list[EntitySpec],
    relations: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    communities: list[dict[str, Any]],
) -> dict[str, Any]:
    type_counts = Counter(entity.type for entity in entities)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_file": SOURCE_DOCX.name,
        "source_path": str(SOURCE_DOCX),
        "documents": len(documents),
        "chunks": len(chunks),
        "entities": len(entities),
        "claims": len(claims),
        "relations": len(relations),
        "communities": len(communities),
        "extractor": "rule",
        "extraction_method": "规则抽取",
        "corpus_count": len(documents),
        "chunk_count": len(chunks),
        "entity_count": len(entities),
        "relation_count": len(relations),
        "claim_count": len(claims),
        "community_count": len(communities),
        "evidence_edge_count": len([relation for relation in relations if relation["evidence_text"]]),
        "technology_node_count": type_counts.get("AITech", 0),
        "model_node_count": type_counts.get("Model", 0),
        "dataset_node_count": type_counts.get("Dataset", 0),
        "case_node_count": type_counts.get("Case", 0) + type_counts.get("Event", 0),
        "policy_node_count": type_counts.get("Policy", 0) + type_counts.get("Standard", 0),
        "limitation_node_count": type_counts.get("Limitation", 0),
        "quality_status": "待复核",
    }
    return summary


def build_public_atlas(
    summary: dict[str, Any],
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    entities: list[EntitySpec],
    relations: list[dict[str, Any]],
    communities: list[dict[str, Any]],
    qa_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes = [
        {
            "id": entity.id,
            "label": entity.name,
            "name": entity.name,
            "type": entity.type,
            "entity_type": entity.type,
            "community": entity.community_id,
            "community_id": entity.community_id,
            "description": entity.description or f"{entity.type}：{entity.name}",
            "evidenceCount": entity.evidence_count,
            "evidence_count": entity.evidence_count,
            "relationCount": entity.relation_count,
            "relation_count": entity.relation_count,
            "reviewStatus": "待复核",
            "review_status": "待复核",
            "score": round(entity.score, 2),
        }
        for entity in entities
    ]
    edges = [
        {
            "id": relation["relation_id"],
            "relation_id": relation["relation_id"],
            "source": relation["head_id"],
            "target": relation["tail_id"],
            "source_id": relation["head_id"],
            "target_id": relation["tail_id"],
            "relationType": relation["relation_type"],
            "relation_type": relation["relation_type"],
            "label": relation["relation_label"],
            "confidence": relation["confidence"],
            "evidenceText": relation["evidence_text"],
            "evidence_text": relation["evidence_text"],
            "docId": relation["doc_id"],
            "doc_id": relation["doc_id"],
            "chunkId": relation["chunk_id"],
            "chunk_id": relation["chunk_id"],
            "sourceName": relation["source_name"],
            "source_name": relation["source_name"],
            "reviewStatus": "待复核",
            "review_status": "待复核",
            "expert_status": "待复核",
        }
        for relation in relations
    ]
    frontend_communities = [
        {
            **community,
            "name": community.get("title", ""),
            "evidence": 100,
            "documents": len([part for part in str(community.get("evidence_sources", "")).split("；") if part]),
            "summary": community.get("summary", ""),
            "openQuestion": community.get("open_questions", ""),
            "evidenceCount": community.get("relation_count", 0),
        }
        for community in communities
    ]
    frontend_qa = [
        {
            **row,
            "question_id": row.get("qa_id", ""),
            "mode": "local" if index % 2 else "global",
            "status": "pending",
            "evidence_coverage": 1.0,
            "answer_preview": row.get("expected_answer", ""),
        }
        for index, row in enumerate(qa_rows, 1)
    ]
    frontend_top_technologies = [
        {
            "name": node["name"],
            "key_tech_score": node["score"],
            "maturity_level": "待复核",
            "evidence_doc_count": node["evidenceCount"],
            "missing_evidence": "需继续由专家核验跨来源一致性。",
        }
        for node in nodes
        if node["type"] == "AITech"
    ][:12]
    export_files = sorted(file.name for file in OUTPUT_DIR.iterdir() if file.is_file())
    atlas = {
        "generatedAt": summary["generated_at"],
        "summary": summary,
        "sourceTypes": ["整理报告"],
        "entityTypes": REQUIRED_ENTITY_TYPES,
        "relationTypes": REQUIRED_RELATION_TYPES,
        "corpusLayers": documents,
        "communities": frontend_communities,
        "exports": [{"name": name, "path": f"outputs/graphrag_index/{name}", "description": export_description(name)} for name in export_files],
        "topTechnologies": frontend_top_technologies,
        "topologyCommunities": communities,
        "qaResults": frontend_qa,
        "uncertainty": {
            "review_status": "待复核",
            "low_confidence_edges": len([edge for edge in edges if float(edge["confidence"]) < 0.75]),
            "image_extraction": "未抽取图片像素内容，仅索引正文和表格文字。",
        },
        "documents": documents,
        "chunksPreview": chunks[:20],
        "graph": {"nodes": len(nodes), "edges": len(edges)},
        "graphData": {"nodes": nodes, "edges": edges},
    }
    return replace_none(atlas)


def export_description(name: str) -> str:
    descriptions = {
        "graph_nodes.csv": "图谱节点表，记录实体类型、社区、证据数和复核状态。",
        "graph_edges_neo4j.csv": "Neo4j 导入关系表，记录起点、终点、关系类型和证据片段。",
        "evidence_edges.csv": "证据边表，保留来源文档、文本块、置信度和证据原文。",
        "community_reports.csv": "社区报告表，用于解释技术方向和复核重点。",
        "atlas.graphml": "GraphML 图结构文件，可导入图分析或可视化工具。",
        "neo4j_import.cypher": "Neo4j 导入脚本。",
        "atlas_quality_report.json": "索引质量检查结果。",
        "expert_review_log.csv": "专家复核记录表。",
    }
    return descriptions.get(name, "GraphRAG 索引导出文件。")


def replace_none(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0
    if isinstance(value, dict):
        return {key: replace_none(child) for key, child in value.items()}
    if isinstance(value, list):
        return [replace_none(child) for child in value]
    return value


def publish_frontend(atlas: dict[str, Any], summary: dict[str, Any]) -> None:
    PUBLIC_ATLAS_DIR.mkdir(parents=True, exist_ok=True)
    for filename in ["atlas_frontend.json", "graph_visualization.json"]:
        (PUBLIC_ATLAS_DIR / filename).write_text(json.dumps(atlas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PUBLIC_ATLAS_DIR / "index_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_docs(summary: dict[str, Any], quality: dict[str, Any], archive_dir: Path) -> None:
    path = DOCS_DIR / "新资料索引重建说明.md"
    content = f"""# 新资料索引重建说明

## 1. 新增资料

- 文件：`{SOURCE_DOCX}`
- 用途：作为地震灾害知识图谱的新增证据来源，覆盖来源核验、地震事件、ShakeMap、PAGER、遥感震损、分布式预警、工程损失评估和治理标准。

## 2. 归档位置

- 旧索引和旧前端 atlas 已归档到：`{archive_dir}`

## 3. 语料拆分

- 已在 `data/corpus/earthquake/` 生成 10 个地震专题 Markdown 文件。
- 每个文件均包含 doc_id、title、source_file、topic、source_type、graph_usage、language、quality_status 等元数据。

## 4. 索引生成

- 输出目录：`outputs/graphrag_index/`
- 文本块数量：{summary['chunk_count']}
- 节点数量：{summary['entity_count']}
- 关系数量：{summary['relation_count']}
- 声明数量：{summary['claim_count']}
- 社区数量：{summary['community_count']}

## 5. 核心节点

- 已纳入 ShakeMap、PAGER、xBD、Copernicus EMS、ALOS-2-BDE、Edge-AI CNN、OpenQuake、Hazus、Sendai Framework、ISO 22320:2018、预警盲区、数据偏差、标注稀缺。

## 6. 证据链

- 每条关系保留 doc_id、chunk_id、evidence_text、confidence 和 review_status。
- 默认复核状态为“待复核”。

## 7. 专家复核

- `expert_review_log.csv` 记录全部关系。
- `expert_review_priority.csv` 按置信度和治理风险生成复核优先级。

## 8. 质量报告

- `atlas_quality_report.json` 和 `atlas_quality_report.md` 记录节点类型覆盖、关系类型覆盖和低置信度关系。
- Word 图片数量已统计为 {quality['docx_meta']['inline_shape_count']}，图片像素内容未自动抽取。

## 9. 前端发布

- 已发布 `public/atlas/atlas_frontend.json`。
- 已发布 `public/atlas/index_summary.json`。
- 已同步 `public/atlas/graph_visualization.json`。

## 10. 查看方式

```powershell
npm.cmd run dev
```

访问：

`http://localhost:3000`
"""
    path.write_text(content, encoding="utf-8")


def write_logs(summary: dict[str, Any], quality: dict[str, Any], archive_dir: Path) -> None:
    run_log = f"""地震灾害新增资料 GraphRAG 索引重建运行日志

生成时间：{summary['generated_at']}
新增资料：{SOURCE_DOCX}
归档目录：{archive_dir}
语料目录：{CORPUS_DIR}
输出目录：{OUTPUT_DIR}
前端发布目录：{PUBLIC_ATLAS_DIR}

语料文档数：{summary['corpus_count']}
文本块数：{summary['chunk_count']}
节点数：{summary['entity_count']}
关系数：{summary['relation_count']}
声明数：{summary['claim_count']}
社区数：{summary['community_count']}
有证据关系数：{summary['evidence_edge_count']}

说明：Word 图片数量为 {quality['docx_meta']['inline_shape_count']}，本轮仅索引正文和表格文字。
"""
    check_log = f"""地震灾害新增资料 GraphRAG 索引质量检查

必需节点类型覆盖：
{json.dumps(quality['required_entity_type_coverage'], ensure_ascii=False, indent=2)}

必需关系类型覆盖：
{json.dumps(quality['required_relation_type_coverage'], ensure_ascii=False, indent=2)}

关键实体缺失：
{json.dumps(quality['missing_key_entities'], ensure_ascii=False)}

低置信度关系数：{quality['low_confidence_relation_count']}
质量状态：待复核
"""
    (OUTPUT_DIR / "运行日志.txt").write_text(run_log, encoding="utf-8")
    (OUTPUT_DIR / "索引质量检查.txt").write_text(check_log, encoding="utf-8")


def print_final_terminal_output() -> None:
    print(
        f"""地震灾害新增资料 GraphRAG 索引重建完成。

新增资料：
{SOURCE_DOCX}

主要成果：

1. 已拆分地震专题 Markdown 语料。
2. 已重新生成 GraphRAG 索引。
3. 已生成节点、关系、证据边、声明、社区报告。
4. 已生成专家复核表和质量报告。
5. 已发布新的 public/atlas/atlas_frontend.json。
6. 已发布新的 public/atlas/index_summary.json。
7. 前端可通过 npm.cmd run dev 查看。

访问地址：
http://localhost:3000"""
    )


def main() -> None:
    ensure_dirs()
    archive_dir = archive_previous_outputs()
    section_texts, docx_meta = read_source_docx()
    documents = write_corpus(section_texts)
    chunks = split_into_chunks(documents, section_texts)
    entities = build_entities(documents, chunks)
    relations, _ = build_relations(entities, chunks)
    claims = build_claims(relations)
    communities = build_communities(entities, relations)
    qa_rows = build_qa_set()
    quality = build_quality_report(documents, chunks, entities, relations, claims, communities, docx_meta, archive_dir)
    summary = write_outputs(documents, chunks, entities, relations, claims, communities, qa_rows, quality)
    write_ontology(entities)
    atlas = build_public_atlas(summary, documents, chunks, entities, relations, communities, qa_rows)
    publish_frontend(atlas, summary)
    write_docs(summary, quality, archive_dir)
    write_logs(summary, quality, archive_dir)
    print_final_terminal_output()


if __name__ == "__main__":
    main()
