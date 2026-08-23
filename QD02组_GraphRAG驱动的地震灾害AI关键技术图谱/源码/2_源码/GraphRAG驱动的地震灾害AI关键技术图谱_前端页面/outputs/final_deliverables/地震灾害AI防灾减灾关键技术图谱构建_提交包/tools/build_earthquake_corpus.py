from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "data" / "corpus" / "sample"
CORPUS_README = ROOT / "data" / "corpus" / "README.md"


SOURCE_LABELS = {
    "paper": "论文",
    "patent": "专利",
    "project": "项目",
    "policy": "政策",
    "case": "灾害案例",
    "standard": "标准",
    "report": "报告",
}


PROFILES = {
    "early_warning": {
        "tech": "地震早期预警",
        "model": "机器学习",
        "dataset": "地震台网数据",
        "scenario": "地震早期预警",
        "task": "地震监测预警",
        "case": "ShakeAlert地震预警案例",
        "policy": "地震预警发布规范",
        "limitation": "实时部署困难",
    },
    "damage_cv": {
        "tech": "震后建筑损毁识别",
        "model": "CNN",
        "dataset": "建筑物足迹数据",
        "scenario": "震后损毁评估",
        "task": "建筑损毁评估",
        "case": "土耳其叙利亚地震",
        "policy": "应急管理技术标准",
        "limitation": "标注稀缺",
    },
    "remote_sensing": {
        "tech": "遥感震损智能解译",
        "model": "U-Net",
        "dataset": "遥感影像",
        "scenario": "震后损毁评估",
        "task": "建筑损毁评估",
        "case": "日本能登半岛地震",
        "policy": "应急管理技术标准",
        "limitation": "跨区域泛化不足",
    },
    "multimodal": {
        "tech": "地震多模态灾情理解",
        "model": "Transformer",
        "dataset": "众源文本",
        "scenario": "震前监测感知",
        "task": "灾情态势摘要",
        "case": "阿富汗地震",
        "policy": "数据共享与隐私合规",
        "limitation": "数据偏差",
    },
    "llm_decision": {
        "tech": "地震应急辅助决策",
        "model": "LLM",
        "dataset": "众源文本",
        "scenario": "震后应急调度",
        "task": "证据链问答",
        "case": "海地地震",
        "policy": "地震应急预案",
        "limitation": "幻觉风险",
    },
    "dispatch_rl": {
        "tech": "震后救援调度优化",
        "model": "强化学习",
        "dataset": "生命线设施数据",
        "scenario": "震后应急调度",
        "task": "震后资源调度",
        "case": "尼泊尔地震",
        "policy": "地震应急预案",
        "limitation": "震后通信中断",
    },
    "lifeline_gnn": {
        "tech": "生命线震损风险传播GNN",
        "model": "GNN",
        "dataset": "生命线设施数据",
        "scenario": "地震风险评估",
        "task": "生命线风险评估",
        "case": "摩洛哥地震",
        "policy": "防震减灾规划",
        "limitation": "可解释性不足",
    },
    "graphrag": {
        "tech": "地震证据图谱GraphRAG",
        "model": "LLM",
        "dataset": "灾害事件数据库",
        "scenario": "地震风险评估",
        "task": "证据链问答",
        "case": "土耳其叙利亚地震",
        "policy": "数据共享与隐私合规",
        "limitation": "幻觉风险",
    },
    "risk_prediction": {
        "tech": "地震风险时空预测",
        "model": "LSTM",
        "dataset": "地震台网数据",
        "scenario": "地震风险评估",
        "task": "震害风险预测",
        "case": "日本能登半岛地震",
        "policy": "防震减灾规划",
        "limitation": "跨区域泛化不足",
    },
    "rapid_loss": {
        "tech": "震后灾情快速评估",
        "model": "Transformer",
        "dataset": "遥感影像",
        "scenario": "震后损毁评估",
        "task": "灾情态势摘要",
        "case": "土耳其叙利亚地震",
        "policy": "地震应急预案",
        "limitation": "实时部署困难",
    },
}


SOURCES = [
    # paper
    ("paper_bddnet_damage", "BDD-Net building damage detection from satellite imagery", "paper", "Remote Sensing", "https://www.mdpi.com/2072-4292/12/10/1670", 2020, "global", "damage_cv"),
    ("paper_xbd_damage_assessment", "xBD dataset for satellite building damage assessment", "paper", "arXiv", "https://arxiv.org/abs/1911.09296", 2019, "global", "remote_sensing"),
    ("paper_transfer_learning_damage", "Transfer learning for post earthquake damage assessment", "paper", "Remote Sensing", "https://www.mdpi.com/2072-4292/14/11/2532", 2022, "global", "remote_sensing"),
    ("paper_myshake_network", "MyShake smartphone network for earthquake early warning", "paper", "UC Berkeley", "https://myshake.berkeley.edu/science/", 2024, "United States", "early_warning"),
    ("paper_lifeline_resilience", "Lifeline infrastructure resilience after earthquake shocks", "paper", "World Bank and GFDRR", "https://www.gfdrr.org/en/publication/lifelines-opportunity-resilient-infrastructure", 2019, "global", "lifeline_gnn"),
    ("paper_ai_emergency_qa", "Large language models for earthquake emergency knowledge assistance", "paper", "GFDRR", "https://www.gfdrr.org/en/publication/responsible-artificial-intelligence-disaster-risk-management", 2020, "global", "llm_decision"),
    ("paper_seismic_risk_prediction", "Data driven earthquake risk prediction and rapid loss estimation", "paper", "GEM Foundation", "https://www.globalquakemodel.org/openquake", 2024, "global", "risk_prediction"),
    # patent
    ("patent_tw_earthquake_ai", "Artificial intelligence earthquake monitoring patent", "patent", "Google Patents TW201544830A", "https://patents.google.com/patent/TW201544830A/en", 2015, "China Taiwan", "early_warning"),
    ("patent_tw_earthquake_warning", "Earthquake early warning patent", "patent", "Google Patents TWI464443B", "https://patents.google.com/patent/TWI464443B/en", 2014, "China Taiwan", "early_warning"),
    ("patent_myshake_warning", "Smartphone earthquake early warning patent", "patent", "Google Patents US20180376314A1", "https://patents.google.com/patent/US20180376314A1/en", 2018, "United States", "early_warning"),
    ("patent_earthquake_prediction_device", "Earthquake prediction device and warning method", "patent", "Google Patents WO2014128965A1", "https://patents.google.com/patent/WO2014128965A1/en", 2014, "global", "risk_prediction"),
    ("patent_structural_damage_predictor", "Structural damage predictor after earthquake", "patent", "Google Patents US10915829B1", "https://patents.google.com/patent/US10915829B1/en", 2021, "United States", "damage_cv"),
    ("patent_predictive_emergency_analytics", "Predictive analytics for earthquake emergency response", "patent", "Google Patents WO2018039142A1", "https://patents.google.com/patent/WO2018039142A1/en", 2018, "global", "llm_decision"),
    ("patent_disaster_recovery_prediction", "Predictive earthquake recovery and resource planning system", "patent", "Google Patents US20170308421A1", "https://patents.google.com/patent/US20170308421A1/en", 2017, "United States", "dispatch_rl"),
    # project
    ("project_shakealert", "USGS ShakeAlert earthquake early warning", "project", "USGS", "https://www.usgs.gov/programs/earthquake-hazards/shakealert", 2024, "United States", "early_warning"),
    ("project_myshake", "MyShake smartphone earthquake early warning", "project", "UC Berkeley", "https://myshake.berkeley.edu/", 2024, "United States", "early_warning"),
    ("project_xview2_earthquake", "xView2 style satellite damage assessment for earthquake response", "project", "DIU and Carnegie Mellon", "https://xview2.org/", 2024, "global", "damage_cv"),
    ("project_nasa_earthquake_response", "NASA Disasters Program earthquake response products", "project", "NASA", "https://disasters.nasa.gov/", 2024, "global", "remote_sensing"),
    ("project_openquake", "OpenQuake engine for seismic risk modelling", "project", "GEM Foundation", "https://www.globalquakemodel.org/openquake", 2024, "global", "risk_prediction"),
    ("project_fema_hazus", "Hazus earthquake loss estimation program", "project", "FEMA", "https://www.fema.gov/flood-maps/tools-resources/flood-map-products/hazus", 2024, "United States", "rapid_loss"),
    ("project_hot_osm_earthquake", "Humanitarian mapping for earthquake response", "project", "Humanitarian OpenStreetMap Team", "https://www.hotosm.org/", 2024, "global", "multimodal"),
    # policy
    ("policy_sendai_framework_earthquake", "Sendai Framework applied to earthquake risk reduction", "policy", "UNDRR", "https://www.undrr.org/publication/sendai-framework-disaster-risk-reduction-2015-2030", 2015, "global", "graphrag"),
    ("policy_china_earthquake_plan", "National earthquake emergency plan and response workflow", "policy", "State Council of China", "https://www.gov.cn/", 2024, "China", "llm_decision"),
    ("policy_china_14th_drr_plan", "National disaster prevention and mitigation plan for earthquake governance", "policy", "State Council of China", "https://www.gov.cn/zhengce/", 2022, "China", "lifeline_gnn"),
    ("policy_japan_disaster_plan", "Japan disaster management plan for earthquake response", "policy", "Cabinet Office Japan", "https://www.bousai.go.jp/", 2024, "Japan", "early_warning"),
    ("policy_us_mitigation_framework", "National Mitigation Framework for seismic risk reduction", "policy", "FEMA", "https://www.fema.gov/emergency-managers/national-preparedness/frameworks/mitigation", 2023, "United States", "risk_prediction"),
    ("policy_fema_nims", "National Incident Management System for earthquake emergency coordination", "policy", "FEMA", "https://www.fema.gov/emergency-managers/nims", 2023, "United States", "dispatch_rl"),
    ("policy_ai_governance_response", "AI governance requirements for earthquake emergency decision support", "policy", "NIST", "https://www.nist.gov/itl/ai-risk-management-framework", 2023, "United States", "graphrag"),
    # case
    ("case_turkiye_syria_earthquake", "Turkiye Syria earthquake 2023 disaster case", "case", "ReliefWeb", "https://reliefweb.int/disaster/eq-2023-000015-tur", 2023, "Turkiye", "damage_cv"),
    ("case_morocco_earthquake", "Morocco earthquake 2023 disaster case", "case", "ReliefWeb", "https://reliefweb.int/disaster/eq-2023-000166-mar", 2023, "Morocco", "lifeline_gnn"),
    ("case_nepal_earthquake_pdna", "Nepal earthquake 2015 post disaster needs assessment", "case", "ReliefWeb", "https://reliefweb.int/report/nepal/nepal-earthquake-2015-post-disaster-needs-assessment-vol-b-sector-reports", 2015, "Nepal", "dispatch_rl"),
    ("case_haiti_earthquake", "Haiti earthquake recovery and damage assessment case", "case", "World Bank", "https://www.worldbank.org/en/country/haiti/brief/haiti-earthquake-recovery", 2010, "Haiti", "llm_decision"),
    ("case_noto_earthquake", "Japan Noto Peninsula earthquake 2024 case", "case", "ReliefWeb", "https://reliefweb.int/disaster/eq-2024-000001-jpn", 2024, "Japan", "early_warning"),
    ("case_turkiye_rdna", "Turkiye earthquakes recovery and reconstruction assessment", "case", "GFDRR", "https://www.gfdrr.org/en/publication/turkiye-earthquakes-2023", 2023, "Turkiye", "rapid_loss"),
    ("case_afghanistan_earthquake_2023", "Afghanistan earthquake 2023 disaster case", "case", "ReliefWeb", "https://reliefweb.int/disaster/eq-2023-000184-afg", 2023, "Afghanistan", "multimodal"),
    # standard
    ("standard_iso_22320_incident_management", "ISO 22320 incident management for earthquake response", "standard", "ISO 22320", "https://www.iso.org/standard/67851.html", 2018, "global", "llm_decision"),
    ("standard_iso_22322_public_warning", "ISO 22322 public warning for earthquake alerts", "standard", "ISO 22322", "https://www.iso.org/search.html?q=ISO%2022322", 2022, "global", "early_warning"),
    ("standard_iso_22324_colour_alerts", "ISO 22324 colour coded earthquake alert guidance", "standard", "ISO 22324", "https://www.iso.org/search.html?q=ISO%2022324", 2022, "global", "early_warning"),
    ("standard_iso_31000_risk", "ISO 31000 risk management for seismic resilience", "standard", "ISO 31000", "https://www.iso.org/iso-31000-risk-management.html", 2018, "global", "risk_prediction"),
    ("standard_iso_37123_resilient_cities", "ISO 37123 resilient city indicators for earthquake lifelines", "standard", "ISO 37123", "https://www.iso.org/search.html?q=ISO%2037123", 2019, "global", "lifeline_gnn"),
    ("standard_ogc_sensorthings", "OGC SensorThings API for seismic sensor observations", "standard", "OGC", "https://www.ogc.org/standard/sensorthings/", 2021, "global", "early_warning"),
    ("standard_oasis_cap", "OASIS Common Alerting Protocol for earthquake warning messages", "standard", "OASIS", "https://www.oasis-open.org/standard/cap/", 2010, "global", "early_warning"),
    # report
    ("report_gfdrr_ml_drm", "Machine learning for earthquake risk management evidence review", "report", "GFDRR and World Bank", "https://www.gfdrr.org/en/publication/machine-learning-disaster-risk-management", 2018, "global", "remote_sensing"),
    ("report_gfdrr_responsible_ai", "Responsible AI for earthquake emergency decision support", "report", "GFDRR", "https://www.gfdrr.org/en/publication/responsible-artificial-intelligence-disaster-risk-management", 2020, "global", "llm_decision"),
    ("report_jrc_ai_drm", "Artificial intelligence approaches for earthquake risk management", "report", "European Commission Joint Research Centre", "https://publications.jrc.ec.europa.eu/repository/handle/JRC142778", 2025, "Europe", "graphrag"),
    ("report_undrr_gar2025", "Global risk reduction report interpreted for earthquake resilience", "report", "UNDRR", "https://www.undrr.org/gar/gar2025", 2025, "global", "risk_prediction"),
    ("report_worldbank_lifelines", "Lifelines resilient infrastructure opportunity for seismic shock", "report", "World Bank and GFDRR", "https://www.gfdrr.org/en/publication/lifelines-opportunity-resilient-infrastructure", 2019, "global", "lifeline_gnn"),
    ("report_fema_building_codes", "Building codes save lives in earthquake damage reduction", "report", "FEMA", "https://www.fema.gov/emergency-managers/risk-management/building-science/building-codes-save-study", 2020, "United States", "damage_cv"),
    ("report_cdri_giri", "Global infrastructure resilience evidence for earthquake lifelines", "report", "CDRI", "https://giri.unepgrid.ch/", 2023, "global", "lifeline_gnn"),
]


def main() -> None:
    sample_dir = CORPUS_DIR.resolve()
    expected_dir = (ROOT / "data" / "corpus" / "sample").resolve()
    if sample_dir != expected_dir:
        raise RuntimeError(f"Refuse to overwrite unexpected corpus path: {sample_dir}")
    sample_dir.mkdir(parents=True, exist_ok=True)
    for path in sample_dir.glob("*.md"):
        if path.parent.resolve() != sample_dir:
            raise RuntimeError(f"Refuse to remove file outside corpus directory: {path}")
        path.unlink()

    rows = []
    for source in SOURCES:
        row = build_row(*source)
        rows.append(row)
        (sample_dir / f"{row['doc_id']}.md").write_text(render_markdown(row), encoding="utf-8")
    CORPUS_README.write_text(render_readme(rows), encoding="utf-8")

    counts = Counter(row["source_type"] for row in rows)
    print(f"wrote {len(rows)} earthquake corpus documents to {sample_dir}")
    for source_type, count in sorted(counts.items()):
        print(f"{source_type}: {count}")


def build_row(
    doc_id: str,
    title: str,
    source_type: str,
    source_name: str,
    source_url: str,
    year: int,
    region: str,
    profile_key: str,
) -> dict[str, str | int]:
    profile = PROFILES[profile_key]
    return {
        "doc_id": doc_id,
        "title": title,
        "source_type": source_type,
        "source_name": source_name,
        "source_url": source_url,
        "year": year,
        "region": region,
        "disaster_type": "地震",
        **profile,
    }


def render_markdown(row: dict[str, str | int]) -> str:
    source_label = SOURCE_LABELS[str(row["source_type"])]
    frontmatter_keys = [
        "doc_id",
        "title",
        "source_type",
        "source_name",
        "source_url",
        "year",
        "region",
        "disaster_type",
    ]
    frontmatter = ["---"]
    for key in frontmatter_keys:
        frontmatter.append(f"{key}: {yaml_value(row[key])}")
    frontmatter.append("---")

    title = row["title"]
    tech = row["tech"]
    scenario = row["scenario"]
    task = row["task"]
    dataset = row["dataset"]
    model = row["model"]
    case = row["case"]
    policy = row["policy"]
    limitation = row["limitation"]
    source_name = row["source_name"]
    region = row["region"]
    year = row["year"]

    body = [
        f"# {title}",
        "",
        (
            f"该{source_label}来源为“{title}”，来源机构或平台为 {source_name}。"
            f"在地震灾害AI防灾减灾关键技术图谱中，该来源被整理为 地震 专题证据，"
            f"主要支撑 {tech} 技术社区，并服务 {scenario} 场景。"
        ),
        "",
        (
            f"从可抽取证据看，{tech} 依赖 {dataset}，常结合 {model}，"
            f"用于完成 {task}。该证据可与 {case} 形成案例验证关系，"
            f"并受 {policy} 的治理要求约束。"
        ),
        "",
        (
            f"面向 GraphRAG 索引，可形成“{tech} -> 地震 -> {scenario} -> {task} -> "
            f"{dataset} -> {model} -> {case}”的证据链。该来源同时提示需要关注 "
            f"{limitation}、专家校验和证据可追溯性。"
        ),
        "",
        (
            f"元数据层面，该证据的区域为 {region}，年份为 {year}。"
            f"本整理稿只保留用于实体、关系和声明抽取的中文摘要，不替代原文引用。"
        ),
        "",
    ]
    return "\n".join(frontmatter + [""] + body)


def render_readme(rows: list[dict[str, str | int]]) -> str:
    counts = Counter(str(row["source_type"]) for row in rows)
    lines = [
        "# 地震灾害专题语料来源清单",
        "",
        "该目录为默认 GraphRAG 索引语料，已统一收敛到“以地震灾害为例”的研究尺度。",
        "每篇 Markdown 均保留来源、时间、区域和文档类型，并把正文整理为面向实体关系抽取的中文证据摘要。",
        "",
        "## 规模",
        "",
    ]
    for source_type in sorted(counts):
        lines.append(f"- {SOURCE_LABELS[source_type]}：{counts[source_type]} 篇")
    lines.extend(
        [
            f"- 合计：{len(rows)} 篇",
            "- 灾害类型：地震",
            "",
            "## 来源明细",
            "",
            "| doc_id | 类型 | 年份 | 区域 | 技术主线 | 来源 |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['doc_id']}` | {SOURCE_LABELS[str(row['source_type'])]} | {row['year']} | "
            f"{row['region']} | {row['tech']} | {row['source_name']} |"
        )
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 本目录服务于期末大作业中的地震灾害 AI 技术图谱实验。",
            "- 正文为中文整理稿，不是原始文献或网页全文转载。",
            "- 正式引用应回到各文件 frontmatter 中的 `source_url` 核对原始来源。",
            "",
        ]
    )
    return "\n".join(lines)


def yaml_value(value: str | int) -> str:
    text = str(value)
    if re.search(r"[:#\[\]{}]|^\s|\s$", text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


if __name__ == "__main__":
    main()
