"use client";

import { useEffect, useState } from "react";
import ExpandableGraph from "./components/ExpandableGraph";

type TabKey = "corpus" | "index" | "communities" | "qa" | "export" | "interactive";
type AtlasSummary = {
  documents: number;
  chunks: number;
  entities: number;
  claims: number;
  relations: number;
  communities: number;
  extractor?: string;
};

type CorpusLayer = {
  source_type?: string;
  name: string;
  examples: string;
  role: string;
  readiness: number;
  count?: number;
};

type CommunityCard = {
  name: string;
  evidence: number;
  documents: number;
  summary: string;
  openQuestion: string;
  evidenceCount?: number;
};

type ExportTable = {
  name: string;
  fields: string;
  rows?: number;
};

type QaResult = {
  question_id: string;
  mode?: string;
  question?: string;
  status: string;
  evidence_coverage: number;
  expected_count?: number;
  matched_count?: number;
  answer_preview?: string;
};

type ExportCard = ExportTable & {
  category: string;
  fileType: string;
  purpose: string;
  scenario: string;
  submit: string;
  review: string;
  core: boolean;
};

type PipelineStep = {
  id: string;
  title: string;
  output: string;
  detail: string;
  risk: string;
};

type TopTechnology = {
  name: string;
  key_tech_score: number;
  maturity_level: string;
  evidence_doc_count: number;
  missing_evidence: string;
};

type AtlasSnapshot = {
  generatedAt?: string;
  summary: AtlasSummary;
  sourceTypes: string[];
  entityTypes: string[];
  relationTypes: string[];
  corpusLayers: CorpusLayer[];
  communities: CommunityCard[];
  exports: ExportTable[];
  gaps?: Array<{ technology: string; missing: string[] }>;
  topTechnologies?: TopTechnology[];
  topologyCommunities?: Array<{ topology_community_id: string; title: string; member_count: number; relation_count: number; summary: string; members?: Array<{ entity_id: string; name: string; entity_type: string }>; representative_docs?: Array<{ doc_id: string; relation_count: number }> }>;
  qaResults?: QaResult[];
  uncertainty?: { itemCount: number; highPriorityCount: number };
  graph?: { nodes: number; edges: number };
  graphData?: { nodes?: Array<{ type?: string; entity_type?: string }>; edges?: unknown[] };
};

const tabs: Array<{ id: TabKey; label: string }> = [
  { id: "corpus", label: "语料与本体" },
  { id: "index", label: "索引流程" },
  { id: "communities", label: "技术社区" },
  { id: "qa", label: "证据问答" },
  { id: "export", label: "图谱沉淀" },
  { id: "interactive", label: "交互图谱" },
];

const corpusLayers: CorpusLayer[] = [
  {
    name: "地震论文与综述",
    examples: "7 条地震专题语料",
    role: "提供地震AI技术术语、方法演化和实验指标",
    readiness: 100,
    count: 7,
  },
  {
    name: "地震相关专利",
    examples: "7 条地震专题语料",
    role: "识别地震预警、震损评估和应急决策的工程转化路径",
    readiness: 100,
    count: 7,
  },
  {
    name: "地震示范项目",
    examples: "7 条地震专题语料",
    role: "识别地震预警、遥感评估和风险建模的部署能力",
    readiness: 100,
    count: 7,
  },
  {
    name: "地震政策预案",
    examples: "7 条地震专题语料",
    role: "限定地震应急治理任务、合规边界和应用优先级",
    readiness: 100,
    count: 7,
  },
  {
    name: "地震案例",
    examples: "7 条地震专题语料",
    role: "验证技术是否进入真实地震处置和震后评估链条",
    readiness: 100,
    count: 7,
  },
];

const ontologyEntities = [
  "DisasterType",
  "Scenario",
  "AITech",
  "Model",
  "Dataset",
  "Task",
  "Case",
  "Policy",
  "Limitation",
];

const relationSchema = [
  { relation: "APPLIES_TO", from: "AITech", to: "DisasterType / Scenario", note: "技术适用地震灾害和应用场景" },
  { relation: "SERVES_STAGE", from: "AITech", to: "Scenario", note: "技术服务的防灾减灾阶段" },
  { relation: "SOLVES", from: "AITech", to: "Task", note: "技术解决的防灾减灾任务" },
  { relation: "DEPENDS_ON", from: "AITech", to: "Dataset / Model", note: "模型、数据和算力依赖" },
  { relation: "USES_MODEL", from: "AITech", to: "Model", note: "技术采用的模型结构或算法家族" },
  { relation: "VALIDATED_IN", from: "AITech", to: "Case", note: "工程案例或灾后复盘验证" },
  { relation: "LIMITED_BY", from: "AITech", to: "Limitation", note: "标注稀缺、泛化差、部署难等限制" },
  { relation: "REQUIRED_BY", from: "Scenario", to: "Policy", note: "治理场景对应的政策或标准要求" },
];

const pipelineSteps: PipelineStep[] = [
  {
    id: "01",
    title: "语料规范化",
    output: "文档存储",
    detail: "统一论文、专利、项目、政策、地震案例报告的元数据：时间、地区、地震专题范围、来源类型和可信度。",
    risk: "来源混杂会导致技术热度与真实证据混淆。",
  },
  {
    id: "02",
    title: "实体、关系与声明抽取",
    output: "实体 / 关系 / 声明",
    detail: "抽取关键技术、灾害场景、应用任务、数据模型、证据声明和限制条件。",
    risk: "不能只抽实体名，必须抽“谁在什么证据下声称解决了什么问题”。",
  },
  {
    id: "03",
    title: "证据图构建",
    output: "证据图谱",
    detail: "把实体、关系、声明和原文片段连接成可追溯图谱，每条边保留 source、chunk、confidence、time。",
    risk: "没有证据锚点的图谱只能展示，不能用于论文结论。",
  },
  {
    id: "04",
    title: "社区发现与社区报告",
    output: "社区报告",
    detail: "在图上形成层次化技术社区，并为每个社区生成带来源的摘要、代表技术、关键证据和争议点。",
    risk: "社区报告必须能解释为什么这些技术属于同一关键方向。",
  },
  {
    id: "05",
    title: "问题驱动检索",
    output: "全局 / 局部 / 探索式答案",
    detail: "全局问题用社区报告综合，本地问题沿实体邻域追证据，探索性问题结合社区与局部证据迭代。",
    risk: "单纯向量检索容易漏掉跨文档的技术簇和弱连接证据。",
  },
  {
    id: "06",
    title: "专家校验与图谱沉淀",
    output: "校验后的技术图谱",
    detail: "专家对技术社区、关键声明、证据强度和技术缺口做确认，最终沉淀为关键技术图谱。",
    risk: "没有专家状态和版本管理，图谱无法进入科研或政策应用。",
  },
];

const communities: CommunityCard[] = [
  {
    name: "遥感智能解译",
    evidence: 100,
    documents: 5,
    evidenceCount: 384,
    summary: "该社区围绕遥感震损智能解译展开，主要关联震后建筑损毁评估和遥感证据链。",
    openQuestion: "需要由专家复核该社区是否构成稳定关键技术方向。",
  },
  {
    name: "地震风险时空预测",
    evidence: 100,
    documents: 5,
    evidenceCount: 361,
    summary: "该社区围绕地震风险时空预测展开，主要关联震前风险评估、强震动记录和损失预测。",
    openQuestion: "需要由专家复核该社区是否构成稳定关键技术方向。",
  },
  {
    name: "地震多模态灾情理解",
    evidence: 100,
    documents: 4,
    evidenceCount: 188,
    summary: "该社区围绕地震多模态灾情理解展开，适合继续追踪证据链问答和灾情摘要任务。",
    openQuestion: "缺少真实灾害案例或工程部署证据。",
  },
  {
    name: "地震应急辅助决策",
    evidence: 100,
    documents: 5,
    evidenceCount: 216,
    summary: "该社区围绕地震应急辅助决策展开，主要关联震后应急调度、风险评估和证据链问答。",
    openQuestion: "缺少真实灾害案例或工程部署证据。",
  },
  {
    name: "震后救援调度优化",
    evidence: 100,
    documents: 5,
    evidenceCount: 92,
    summary: "该社区围绕震后救援调度优化展开，主要关联应急调度、队伍调度和路径规划任务。",
    openQuestion: "缺少真实灾害案例或工程部署证据。",
  },
];

const queryModes = [
  {
    id: "global_key_communities",
    mode: "全局检索",
    question: "地震灾害 AI 防灾减灾有哪些关键技术社区？",
    answer: "综合社区报告后输出地震专题技术社区、证据强度、代表任务和争议点，适合写论文综述性结果。",
    outputFile: "community_reports.json / topology_communities.json",
    scenario: "用于总览关键技术方向和证据强弱。",
  },
  {
    id: "local_remote_sensing_case",
    mode: "局部检索",
    question: "遥感震损智能解译在土耳其叙利亚地震案例中的证据链是什么？",
    answer: "沿技术实体邻域检索相关论文、数据集、地震案例、指标和限制条件，给出可追溯引用。",
    outputFile: "evidence_edges.csv / graph_edges_neo4j.csv",
    scenario: "用于解释某项技术与真实案例之间的证据链。",
  },
  {
    id: "local_warning_dependency",
    mode: "局部检索",
    question: "地震早期预警依赖哪些传感数据和模型？",
    answer: "围绕地震早期预警节点追踪 DEPENDS_ON、USES_MODEL 和 VALIDATED_IN 关系。",
    outputFile: "relations.jsonl / evidence_edges.csv",
    scenario: "用于展示技术节点的数据依赖和模型方法。",
  },
  {
    id: "gap_case_validation",
    mode: "缺口检索",
    question: "哪些地震 AI 技术缺少真实案例验证？",
    answer: "从关键技术评分和不确定性复核项中定位缺少案例验证的技术。",
    outputFile: "key_technology_assessment.json / uncertainty_report.json",
    scenario: "用于说明后续专家复核和补证方向。",
  },
  {
    id: "drift_data_gap",
    mode: "探索式检索",
    question: "哪些技术缺少数据依赖证据？",
    answer: "先从社区层面定位薄弱技术簇，再沿局部证据追踪地震阶段、区域、任务和缺失证据。",
    outputFile: "atlas_quality_report.json / qa_evaluation_results.json",
    scenario: "用于发现跨社区的证据缺口。",
  },
];

const exportTables = [
  {
    name: "technology_nodes.csv",
    fields: "entity_id, name, entity_type, aliases, relation_count, evidence_score, expert_status",
  },
  {
    name: "scenario_nodes.csv",
    fields: "entity_id, name, entity_type, aliases, relation_count, policy_priority, expert_status",
  },
  {
    name: "evidence_edges.csv",
    fields: "source, source_name, target, target_name, relation_type, doc_id, chunk_id, evidence_text",
  },
  {
    name: "community_reports.json",
    fields: "community_id, title, entities, relation_ids, representative_docs, summary",
  },
  {
    name: "expert_review_log.csv",
    fields: "review_item_id, item_type, claim_id, relation_id, reviewer, decision, revision",
  },
  {
    name: "corpus_manifest.csv",
    fields: "doc_id, title, source_type, source_name, source_url, year, quality_status",
  },
];

const corpusTypeDetails: Record<string, { description: string; sourceFields: string; usage: string }> = {
  地震案例: {
    description: "记录真实地震事件、处置过程和灾后复盘材料，是验证 AI 技术是否进入真实灾害链条的基础。",
    sourceFields: "doc_id、title、source_type、source_name、source_url、year、quality_status",
    usage: "用于验证技术与案例之间的 VALIDATED_IN 关系。",
  },
  地震论文与综述: {
    description: "沉淀模型方法、实验指标和技术演化脉络。",
    sourceFields: "题名、年份、来源、技术术语、实验任务、数据条件",
    usage: "用于抽取 AITech、Model、Dataset 和 Task 节点。",
  },
  地震相关专利: {
    description: "反映地震预警、震损识别和应急辅助决策的工程转化方案。",
    sourceFields: "专利名称、申请主体、技术方案、适用场景、方法步骤",
    usage: "用于补充工程化技术路径和部署约束。",
  },
  地震示范项目: {
    description: "描述系统部署、试点场景和技术集成方式。",
    sourceFields: "项目名称、平台、区域、任务、技术模块、成果形式",
    usage: "用于判断技术成熟度和应用阶段。",
  },
  地震政策预案: {
    description: "提供应急响应流程、治理目标和数据共享边界。",
    sourceFields: "政策名称、发布机构、适用区域、任务要求、合规边界",
    usage: "用于构建 REQUIRED_BY 和 Policy 节点。",
  },
  地震适用标准: {
    description: "限定预警发布、损毁评估、数据质量和应急管理的规范要求。",
    sourceFields: "标准编号、标准名称、适用对象、技术要求、评价指标",
    usage: "用于约束图谱中的质量要求和复核规则。",
  },
  地震相关报告: {
    description: "补充灾害调查、风险评估和机构发布的背景证据。",
    sourceFields: "报告题名、发布机构、地区、年份、结论摘要、证据片段",
    usage: "用于增强社区报告和证据问答的背景说明。",
  },
};

const entityTypeDetails: Record<string, { zh: string; meaning: string; examples: string[]; relations: string[] }> = {
  DisasterType: { zh: "灾害类型", meaning: "本项目聚焦地震灾害，用于限定技术适用范围。", examples: ["地震"], relations: ["APPLIES_TO（适用于）"] },
  Scenario: { zh: "地震阶段与应用场景", meaning: "表示震前、震中、震后不同防灾减灾阶段。", examples: ["地震早期预警", "震后损毁评估"], relations: ["SERVES_STAGE（服务阶段）", "REQUIRED_BY（政策要求）"] },
  AITech: { zh: "AI 关键技术", meaning: "图谱的核心研究对象。", examples: ["地震早期预警", "遥感震损智能解译"], relations: ["SOLVES（解决任务）", "DEPENDS_ON（依赖数据）", "USES_MODEL（采用模型）"] },
  Model: { zh: "模型方法", meaning: "表示算法、模型结构或方法族。", examples: ["Transformer", "GNN", "U-Net"], relations: ["USES_MODEL（采用模型）"] },
  Dataset: { zh: "数据条件", meaning: "表示技术需要的数据来源和观测条件。", examples: ["地震台网数据", "遥感影像"], relations: ["DEPENDS_ON（依赖数据）"] },
  Task: { zh: "防灾减灾任务", meaning: "表示技术要解决的业务任务。", examples: ["建筑损毁评估", "震后资源调度"], relations: ["SOLVES（解决任务）"] },
  Case: { zh: "地震案例", meaning: "表示真实案例或工程验证场景。", examples: ["土耳其叙利亚地震", "MyShake地震预警案例"], relations: ["VALIDATED_IN（案例验证）"] },
  Policy: { zh: "政策标准", meaning: "表示政策、标准和应急预案。", examples: ["地震应急预案", "防震减灾规划"], relations: ["REQUIRED_BY（政策要求）"] },
  Limitation: { zh: "适用边界与限制", meaning: "表示技术限制和复核风险。", examples: ["跨区域泛化不足", "标注稀缺"], relations: ["LIMITED_BY（受限于）"] },
};

const relationLabels: Record<string, string> = {
  APPLIES_TO: "适用于",
  SERVES_STAGE: "服务阶段",
  SOLVES: "解决任务",
  DEPENDS_ON: "依赖数据",
  USES_MODEL: "采用模型",
  VALIDATED_IN: "案例验证",
  LIMITED_BY: "受限于",
  REQUIRED_BY: "政策要求",
};

function relationLabel(type: string): string {
  return relationLabels[type] ? `${type}（${relationLabels[type]}）` : type;
}

function statusLabel(value: string | undefined): string {
  if (!value || value === "pending") return "待复核";
  if (value === "passed") return "已通过";
  if (value === "failed") return "未通过";
  if (value === "rule") return "规则抽取";
  return value;
}

function formatRows(value: number | undefined): string {
  return typeof value === "number" ? `${value} 行记录` : "暂无行数";
}

function pipelineDetail(step: PipelineStep): { goal: string; input: string; files: string; quality: string; status: string } {
  const details: Record<string, { goal: string; input: string; files: string; quality: string; status: string }> = {
    "01": { goal: "把多源地震材料转换为带来源、年份、类型和质量状态的规范化语料。", input: "论文、专利、项目、政策、案例、标准和报告。", files: "documents.jsonl、chunks.jsonl、corpus_manifest.csv。", quality: "每条语料需要保留 doc_id、source_type、source_name、source_url 和质量状态。", status: "已完成地震专题语料整理与切块。" },
    "02": { goal: "从地震专题语料中抽取 AI 技术、任务、数据、模型、案例、限制和政策节点，并建立证据关系。", input: "地震专题文本块 chunks.jsonl。", files: "entities.jsonl、relations.jsonl、claims.jsonl。", quality: "每条关系需要保留 doc_id、chunk_id、evidence_text、confidence 和复核状态。", status: "已完成规则抽取，LLM/Hybrid 抽取接口已保留。" },
    "03": { goal: "把实体、关系、声明和证据片段组织成可追溯图谱。", input: "实体表、关系表和声明表。", files: "evidence_edges.csv、graph_edges_neo4j.csv、atlas.graphml。", quality: "关系边必须绑定来源文档、证据片段和置信度。", status: "已生成证据边、Neo4j 导入表和 GraphML。" },
    "04": { goal: "按关系网络形成技术社区，并生成社区摘要。", input: "实体关系图和证据边。", files: "community_reports.json、topology_communities.json。", quality: "社区报告需说明代表技术、证据来源、开放问题和复核重点。", status: "已生成规则社区与拓扑社区。" },
    "05": { goal: "围绕关键技术、证据链和缺口问题执行检索评测。", input: "社区报告、实体邻域、证据边和评测问题集。", files: "qa_evaluation_set.json、qa_evaluation_results.json。", quality: "答案必须返回依赖数据、证据来源和适用场景。", status: "已生成问答评测问题与覆盖度结果。" },
    "06": { goal: "把可追溯证据、复核状态和导出文件沉淀为可提交成果。", input: "索引输出、质量报告、技术评分和专家复核表。", files: "submission_manifest.json、expert_review_log.csv、key_technology_assessment.json。", quality: "核心结论必须可追溯，待专家复核项不能表述为已人工确认。", status: "已生成提交包和复核清单。" },
  };
  return details[step.id] ?? details["01"];
}

function exportCategory(name: string): string {
  if (/graph|atlas\.graphml|neo4j|nodes|edges/i.test(name)) return "图谱结构文件";
  if (/corpus|document|chunk|claim|evidence/i.test(name)) return "语料与证据文件";
  if (/technology|assessment/i.test(name)) return "技术评估文件";
  if (/community|topology/i.test(name)) return "社区分析文件";
  if (/quality|uncertainty|gap/i.test(name)) return "质量评估文件";
  if (/qa/i.test(name)) return "问答评估文件";
  if (/expert|review/i.test(name)) return "专家复核文件";
  if (/submission|manifest|final|checklist/i.test(name)) return "提交成果文件";
  return "提交成果文件";
}

function exportFileType(name: string, fields: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith(".csv")) return "CSV 文件";
  if (lower.endsWith(".json")) return "JSON 文件";
  if (lower.endsWith(".jsonl")) return "JSONL 文件";
  if (lower.endsWith(".graphml")) return "GraphML 文件";
  if (lower.endsWith(".md")) return "Markdown 文档";
  if (fields === "json") return "JSON 文件";
  return "成果文件";
}

function enrichExport(table: ExportTable): ExportCard {
  const category = exportCategory(table.name);
  const purposeByName: Record<string, string> = {
    "evidence_edges.csv": "记录技术关系、来源文档、证据片段、置信度和复核状态，是图谱可追溯性的核心证据表。",
    "graph_nodes.csv": "记录图谱节点及其类型、名称和统计信息，用于论文图表和 Neo4j 展示。",
    "graph_edges_neo4j.csv": "记录可导入 Neo4j 的关系边，用于图数据库展示和后续查询。",
    "community_reports.json": "保存技术社区摘要、代表实体和证据来源，用于全局检索和报告归纳。",
    "key_technology_assessment.json": "保存关键技术评分、成熟度和证据缺口，用于成果分析。",
    "expert_review_log.csv": "保存待专家复核项目和处理状态，用于人工校验闭环。",
    "qa_evaluation_results.json": "保存证据问答评测结果，用于验证检索覆盖度。",
  };
  const purpose = purposeByName[table.name] ?? `${category}，用于支撑地震灾害 AI 关键技术图谱的复现、展示或提交。`;
  const core = /evidence_edges|graph_nodes|graph_edges|community_reports|key_technology|expert_review|qa_evaluation|submission/i.test(table.name);
  return { ...table, category, fileType: exportFileType(table.name, table.fields), purpose, scenario: category === "图谱结构文件" ? "适合导入 Neo4j、制作图谱截图和支撑结构化分析。" : "适合课程报告、复核说明和成果提交。", submit: core ? "建议提交" : "按需提交", review: /expert|review|uncertainty|quality|evidence|relation|assessment/i.test(table.name) ? "需要复核" : "一般无需复核", core };
}

function questionModeLabel(mode: string | undefined): string {
  if (mode === "global") return "全局检索";
  if (mode === "local") return "局部检索";
  if (mode === "drift") return "探索式检索";
  if (mode === "gap") return "缺口检索";
  return mode ?? "评测问题";
}
export function TechnologyGraphExplorer() {
  const [activeTab, setActiveTab] = useState<TabKey>("interactive");
  const [atlas, setAtlas] = useState<AtlasSnapshot | null>(null);
  const [activeCorpusName, setActiveCorpusName] = useState("地震案例");
  const [activeEntityType, setActiveEntityType] = useState("AITech");
  const [activePipelineStepId, setActivePipelineStepId] = useState("02");
  const [showAllPipelineDetails, setShowAllPipelineDetails] = useState(false);
  const [activeCommunityName, setActiveCommunityName] = useState("");
  const [communitySearch, setCommunitySearch] = useState("");
  const [communitySort, setCommunitySort] = useState<"evidence" | "name">("evidence");
  const [activeQuestionId, setActiveQuestionId] = useState("global_key_communities");
  const [activeExportCategory, setActiveExportCategory] = useState("全部成果");
  const [activeExportName, setActiveExportName] = useState("");
  const [showExportFields, setShowExportFields] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch("/atlas/atlas_frontend.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`Atlas snapshot ${response.status}`);
        return response.json() as Promise<AtlasSnapshot>;
      })
      .then((snapshot) => {
        if (alive) setAtlas(snapshot);
      })
      .catch(() => {
        if (alive) setAtlas(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  const activeCorpusLayers = atlas?.corpusLayers?.length ? atlas.corpusLayers : corpusLayers;
  const activeEntityTypes = atlas?.entityTypes?.length ? atlas.entityTypes : ontologyEntities;
  const activeCommunities = atlas?.communities?.length ? atlas.communities : communities;
  const activeExportTables = atlas?.exports?.length ? atlas.exports : exportTables;
  const activeTopTechnologies = atlas?.topTechnologies?.length ? atlas.topTechnologies.slice(0, 5) : [];
  const activeTopologyCommunities = atlas?.topologyCommunities?.length ? atlas.topologyCommunities.slice(0, 4) : [];
  const qaResults = atlas?.qaResults ?? [];
  const summary = atlas?.summary;
  const graphDataNodes = atlas?.graphData?.nodes ?? [];
  const technologyNodeCount = graphDataNodes.filter((node) => (node.type ?? node.entity_type) === "AITech").length || activeTopTechnologies.length || 10;
  const communityReportCount = summary?.communities ?? activeCommunities.length;
  const activeCorpus = activeCorpusLayers.find((layer) => layer.name === activeCorpusName) ?? activeCorpusLayers[0];
  const activeCorpusDetail = corpusTypeDetails[activeCorpus?.name ?? "地震案例"] ?? corpusTypeDetails["地震案例"];
  const activeEntityDetail = entityTypeDetails[activeEntityType] ?? entityTypeDetails.AITech;
  const activePipelineStep = pipelineSteps.find((step) => step.id === activePipelineStepId) ?? pipelineSteps[0];
  const activePipelineDetail = pipelineDetail(activePipelineStep);
  const filteredCommunities = [...activeCommunities]
    .filter((community) => `${community.name} ${community.summary} ${community.openQuestion}`.includes(communitySearch.trim()))
    .sort((a, b) => communitySort === "evidence" ? (b.evidenceCount ?? b.evidence) - (a.evidenceCount ?? a.evidence) : a.name.localeCompare(b.name, "zh-Hans-CN"));
  const activeCommunity = filteredCommunities.find((community) => community.name === activeCommunityName) ?? filteredCommunities[0] ?? activeCommunities[0];
  const activeTopologyCommunity = activeTopologyCommunities.find((item) => activeCommunity?.name && item.title.includes(activeCommunity.name)) ?? activeTopologyCommunities[0];
  const topologyMembers = activeTopologyCommunity?.members ?? [];
  const communityModels = topologyMembers.filter((item) => item.entity_type === "Model").slice(0, 4).map((item) => item.name);
  const communityDatasets = topologyMembers.filter((item) => item.entity_type === "Dataset").slice(0, 4).map((item) => item.name);
  const communityCases = topologyMembers.filter((item) => item.entity_type === "Case").slice(0, 4).map((item) => item.name);
  const questionCards = qaResults.length
    ? qaResults.map((item) => ({
        id: item.question_id,
        mode: questionModeLabel(item.mode),
        question: item.question ?? item.question_id,
        answer: item.answer_preview || "当前展示为评测问题设计，实际答案由索引检索命令生成。",
        outputFile: item.mode === "global" ? "community_reports.json" : "evidence_edges.csv / qa_evaluation_results.json",
        scenario: `覆盖度 ${(item.evidence_coverage * 100).toFixed(0)}%，状态：${statusLabel(item.status)}`,
      }))
    : queryModes;
  const activeQuestion = questionCards.find((item) => item.id === activeQuestionId) ?? questionCards[0];
  const exportCards = activeExportTables.map(enrichExport);
  const exportCategories = ["全部成果", ...Array.from(new Set(exportCards.map((item) => item.category)))];
  const filteredExports = activeExportCategory === "全部成果" ? exportCards : exportCards.filter((item) => item.category === activeExportCategory);
  const activeExport = filteredExports.find((item) => item.name === activeExportName) ?? filteredExports[0] ?? exportCards[0];
  const relationDisplayRows = relationSchema.map((row) => ({ ...row, relationText: relationLabel(row.relation) }));

  return (
    <main className="graphrag-app">
      <header className="graphrag-header">
        <section>
          <span className="eyebrow">地震灾害 AI 关键技术图谱</span>
          <h1>GraphRAG 驱动的地震灾害 AI 关键技术图谱</h1>
          <p>
            目标是用GraphRAG从地震灾害文本证据中抽取实体、关系、声明和社区报告，
            再通过证据问答、专家校验和结构化导出，沉淀为可追溯的地震关键技术图谱。
          </p>
        </section>
        <aside>
          <span>核心转向</span>
          <strong>GraphRAG不是最终图谱，而是从大规模证据中构建、检索、总结和校验图谱的研究机制。</strong>
        </aside>
      </header>

      <section className="metric-row" aria-label="GraphRAG目标指标">
        <article>
          <span>语料类型</span>
          <strong>{atlas?.sourceTypes?.length ?? 7}</strong>
          <p>当前索引覆盖 {summary?.documents ?? 49} 条地震专题整理语料。</p>
        </article>
        <article>
          <span>实体类型</span>
          <strong>{activeEntityTypes.length}</strong>
          <p>围绕地震、场景、技术、模型、数据、任务、案例、政策和限制建模。</p>
        </article>
        <article>
          <span>关系数量</span>
          <strong>{summary?.relations ?? atlas?.graph?.edges ?? 792}</strong>
          <p>每条关系绑定来源文档、证据片段、置信度和复核状态。</p>
        </article>
        <article>
          <span>输出成果</span>
          <strong>{activeExportTables.length}</strong>
          <p>
            包含节点、关系、证据边、社区报告、质量报告和专家复核表。
            {atlas?.graph ? ` 图谱 ${atlas.graph.nodes} 节点/${atlas.graph.edges} 边。` : ""}
          </p>
        </article>
        <article>
          <span>技术节点</span>
          <strong>{technologyNodeCount}</strong>
          <p>聚焦地震预警、震损识别、风险评估、调度优化和证据图谱等AI关键技术。</p>
        </article>
        <article>
          <span>技术社区</span>
          <strong>{communityReportCount}</strong>
          <p>基于实体关系形成可解释的地震 AI 技术社区。</p>
        </article>
      </section>

      <nav className="tab-bar" aria-label="GraphRAG工作台">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? "active" : ""}
            onClick={() => setActiveTab(tab.id)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === "corpus" ? (
        <section className="workspace two-col corpus-workspace">
          <section className="panel">
            <div className="panel-title">
              <span className="eyebrow">语料设计</span>
              <h2>点击语料类型查看来源、数量和图谱作用</h2>
              <p>每类语料都保留来源、时间、地区、文档类型和可信度字段，用于支撑后续实体抽取与证据追溯。</p>
            </div>
            <div className="corpus-list interactive-list">
              {activeCorpusLayers.map((layer) => {
                const selected = layer.name === activeCorpus?.name;
                return (
                  <button className={selected ? "interactive-card selected" : "interactive-card"} key={layer.name} onClick={() => setActiveCorpusName(layer.name)} type="button">
                    <div>
                      <strong>{layer.name}</strong>
                      <span>{layer.count ? `${layer.count} 条` : `${layer.readiness}%`}</span>
                    </div>
                    <p>{layer.examples}</p>
                    <small>{layer.role}</small>
                    <em><i style={{ width: `${layer.readiness}%` }} /></em>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="panel detail-panel">
            <div className="panel-title compact">
              <span className="eyebrow">语料详情</span>
              <h2>{activeCorpus?.name ?? "地震案例"}</h2>
              <p>{activeCorpusDetail.description}</p>
            </div>
            <div className="detail-metric-grid">
              <div className="detail-metric"><span>当前数量</span><strong>{activeCorpus?.count ?? 0} 条</strong></div>
              <div className="detail-metric"><span>完成度</span><strong>{activeCorpus?.readiness ?? 0}%</strong></div>
              <div className="detail-metric"><span>来源字段</span><strong>{activeCorpusDetail.sourceFields}</strong></div>
            </div>
            <section className="detail-section compact-card">
              <span className="eyebrow">图谱作用</span>
              <p>{activeCorpusDetail.usage}</p>
            </section>

            <div className="panel-title compact score-title">
              <span className="eyebrow">领域本体</span>
              <h2>点击实体类型查看含义、示例和关系规则</h2>
            </div>
            <div className="ontology-grid interactive-chips">
              {activeEntityTypes.map((entity) => (
                <button className={entity === activeEntityType ? "selected" : ""} key={entity} onClick={() => setActiveEntityType(entity)} type="button">
                  {entityTypeDetails[entity]?.zh ?? entity}
                </button>
              ))}
            </div>
            <section className="detail-section ontology-detail-card">
              <span className="eyebrow">实体类型详情</span>
              <h3>{activeEntityType}（{activeEntityDetail.zh}）</h3>
              <p>{activeEntityDetail.meaning}</p>
              <div className="relation-count-grid">
                {activeEntityDetail.examples.map((item) => <span key={item}>{item}</span>)}
              </div>
              <div className="relation-count-grid">
                {activeEntityDetail.relations.map((item) => <span key={item}>{item}</span>)}
              </div>
            </section>
            <div className="relation-table" role="table" aria-label="关系模式">
              <div role="row" className="table-head">
                <span role="columnheader">关系</span>
                <span role="columnheader">来源类型</span>
                <span role="columnheader">目标类型</span>
                <span role="columnheader">用途</span>
              </div>
              {relationDisplayRows.map((row) => (
                <div role="row" key={row.relation}>
                  <strong role="cell">{row.relationText}</strong>
                  <span role="cell">{row.from}</span>
                  <span role="cell">{row.to}</span>
                  <span role="cell">{row.note}</span>
                </div>
              ))}
            </div>
          </section>
        </section>
      ) : null}
      {activeTab === "index" ? (
        <section className="workspace two-col pipeline-workspace">
          <section className="panel">
            <div className="panel-title">
              <span className="eyebrow">索引流程</span>
              <h2>点击流程步骤查看输入、输出和质量要求</h2>
              <p>这个流程是方法部分主轴。每一步都输出可检查中间产物，而不是只得到最终答案。</p>
            </div>
            <div className="pipeline-grid interactive-pipeline">
              {pipelineSteps.map((step, index) => (
                <button className={step.id === activePipelineStep.id ? "interactive-card selected" : "interactive-card"} key={step.id} onClick={() => setActivePipelineStepId(step.id)} type="button">
                  <span>{step.id}</span>
                  <h3>{step.title}</h3>
                  <strong>{step.output}</strong>
                  <p>{step.detail}</p>
                  {index < pipelineSteps.length - 1 ? <i aria-hidden="true">→</i> : null}
                </button>
              ))}
            </div>
            <button className="toggle-button flow-toggle" onClick={() => setShowAllPipelineDetails((value) => !value)} type="button">
              {showAllPipelineDetails ? "收起流程说明" : "查看全部流程说明"}
            </button>
          </section>

          <section className="panel detail-panel">
            <div className="panel-title compact">
              <span className="eyebrow">步骤详情</span>
              <h2>{activePipelineStep.id}. {activePipelineStep.title}</h2>
              <p>{activePipelineStep.detail}</p>
            </div>
            <div className="detail-stack">
              <article><span>步骤目标</span><p>{activePipelineDetail.goal}</p></article>
              <article><span>输入数据</span><p>{activePipelineDetail.input}</p></article>
              <article><span>输出结果</span><p>{activePipelineStep.output}</p></article>
              <article><span>对应文件</span><p>{activePipelineDetail.files}</p></article>
              <article><span>质量要求</span><p>{activePipelineDetail.quality}</p></article>
              <article><span>当前状态</span><p>{activePipelineDetail.status}</p></article>
            </div>
            {showAllPipelineDetails ? (
              <div className="all-flow-list">
                {pipelineSteps.map((step) => {
                  const detail = pipelineDetail(step);
                  return <article key={step.id}><strong>{step.id}. {step.title}</strong><span>{detail.files}</span><p>{detail.status}</p></article>;
                })}
              </div>
            ) : null}
          </section>
        </section>
      ) : null}
      {activeTab === "communities" ? (
        <section className="workspace two-col community-workspace">
          <section className="panel">
            <div className="panel-title">
              <span className="eyebrow">技术社区</span>
              <h2>点击社区卡片查看代表技术、证据强度和开放问题</h2>
              <p>社区报告用于把分散的实体关系归纳为可解释技术方向，右侧面板集中展示证据和待复核问题。</p>
            </div>
            <div className="community-toolbar">
              <input aria-label="搜索社区" onChange={(event) => setCommunitySearch(event.target.value)} placeholder="搜索社区名称或摘要" value={communitySearch} />
              <button className={communitySort === "evidence" ? "active" : ""} onClick={() => setCommunitySort("evidence")} type="button">按证据强度排序</button>
              <button className={communitySort === "name" ? "active" : ""} onClick={() => setCommunitySort("name")} type="button">按名称排序</button>
            </div>
            <div className="community-list interactive-list community-card-list">
              {filteredCommunities.length ? filteredCommunities.map((community, index) => (
                <button className={community.name === activeCommunity?.name ? "interactive-card selected" : "interactive-card"} key={community.name} onClick={() => setActiveCommunityName(community.name)} type="button">
                  <div>
                    <strong>社区 {String(index + 1).padStart(2, "0")}</strong>
                    <span>{community.evidence} 分</span>
                  </div>
                  <h3>{community.name}</h3>
                  <p>{community.summary}</p>
                  <small>{community.evidenceCount ?? community.documents} 条证据 · {community.documents} 份来源</small>
                </button>
              )) : <p className="empty-inline">暂无社区报告数据</p>}
            </div>
          </section>

          <section className="panel detail-panel">
            <div className="panel-title compact">
              <span className="eyebrow">社区详情</span>
              <h2>{activeCommunity?.name ?? "暂无社区报告数据"}</h2>
              <p>{activeCommunity?.summary ?? "暂无社区报告数据"}</p>
            </div>
            {activeCommunity ? (
              <>
                <div className="detail-metric-grid">
                  <div className="detail-metric"><span>证据强度</span><strong>{activeCommunity.evidence}</strong></div>
                  <div className="detail-metric"><span>证据数量</span><strong>{activeCommunity.evidenceCount ?? activeCommunity.documents}</strong></div>
                  <div className="detail-metric"><span>实体数量</span><strong>{activeTopologyCommunity?.member_count ?? "暂无数据"}</strong></div>
                </div>
                <section className="detail-section compact-card"><span className="eyebrow">代表技术</span><p>{activeCommunity.name}</p></section>
                <section className="detail-section compact-card"><span className="eyebrow">关联模型</span><div className="relation-count-grid">{(communityModels.length ? communityModels : ["暂无模型数据"]).map((item) => <span key={item}>{item}</span>)}</div></section>
                <section className="detail-section compact-card"><span className="eyebrow">关联数据</span><div className="relation-count-grid">{(communityDatasets.length ? communityDatasets : ["暂无数据条件"]).map((item) => <span key={item}>{item}</span>)}</div></section>
                <section className="detail-section compact-card"><span className="eyebrow">代表案例</span><div className="relation-count-grid">{(communityCases.length ? communityCases : ["暂无案例数据"]).map((item) => <span key={item}>{item}</span>)}</div></section>
                <section className="detail-section compact-card"><span className="eyebrow">开放问题</span><p>{activeCommunity.openQuestion}</p></section>
                <section className="detail-section compact-card"><span className="eyebrow">证据来源</span><p>{activeTopologyCommunity?.representative_docs?.slice(0, 5).map((item) => item.doc_id).join("、") || "暂无代表来源"}</p></section>
              </>
            ) : null}
          </section>
        </section>
      ) : null}
      {activeTab === "qa" ? (
        <section className="workspace two-col qa-workspace">
          <section className="panel">
            <div className="panel-title">
              <span className="eyebrow">证据问答</span>
              <h2>点击问题卡片查看检索类型、依赖数据和输出文件</h2>
              <p>问答页展示评测问题设计和真实评测结果。正式答案由索引检索命令生成，页面保留可追溯的文件和命令提示。</p>
            </div>
            <div className="query-grid interactive-list">
              {questionCards.map((query) => (
                <button className={query.id === activeQuestion?.id ? "interactive-card selected" : "interactive-card"} key={query.id} onClick={() => setActiveQuestionId(query.id)} type="button">
                  <span>{query.mode}</span>
                  <h3>{query.question}</h3>
                  <p>{query.answer}</p>
                </button>
              ))}
            </div>
          </section>

          <section className="panel detail-panel">
            <div className="panel-title compact">
              <span className="eyebrow">答案结构说明</span>
              <h2>{activeQuestion?.question ?? "暂无评测问题"}</h2>
              <p>{activeQuestion?.answer ?? "当前展示为评测问题设计，实际答案由索引检索命令生成。"}</p>
            </div>
            <div className="detail-stack">
              <article><span>检索类型</span><p>{activeQuestion?.mode ?? "评测问题"}</p></article>
              <article><span>返回内容</span><p>相关实体、关系、证据片段、置信度、复核状态和可沉淀三元组。</p></article>
              <article><span>依赖数据</span><p>社区报告、实体邻域、证据边、语料切块和问答评测结果。</p></article>
              <article><span>对应输出文件</span><p>{activeQuestion?.outputFile ?? "qa_evaluation_results.json"}</p></article>
              <article><span>适用场景</span><p>{activeQuestion?.scenario ?? "用于课程报告中的证据链解释。"}</p></article>
            </div>
            <pre className="command-hint">{`python -m graphrag_atlas global-search "${activeQuestion?.question ?? "问题文本"}" --output outputs/graphrag_index`}</pre>
          </section>
        </section>
      ) : null}
      {activeTab === "interactive" ? (
        <section className="workspace">
          <ExpandableGraph snapshot={atlas} />
        </section>
      ) : null}
      {activeTab === "export" ? (
        <section className="workspace two-col export-workspace">
          <section className="panel">
            <div className="panel-title">
              <span className="eyebrow">图谱沉淀</span>
              <h2>按成果类型筛选文件，点击查看用途和提交意义</h2>
              <p>这里不再铺满调试式文件列表，而是把导出文件整理为可筛选、可解释、可复核的成果清单。</p>
            </div>
            <div className="filter-chip-grid export-category-chips">
              {exportCategories.map((category) => (
                <button className={category === activeExportCategory ? "selected" : ""} key={category} onClick={() => { setActiveExportCategory(category); setActiveExportName(""); }} type="button">
                  {category}
                </button>
              ))}
            </div>
            <div className="export-card-grid">
              {filteredExports.map((file) => (
                <button className={file.name === activeExport?.name ? "interactive-card selected" : "interactive-card"} key={file.name} onClick={() => { setActiveExportName(file.name); setShowExportFields(false); }} type="button">
                  <strong>{file.name}</strong>
                  <span>{file.fileType}</span>
                  <small>{formatRows(file.rows)} · {file.core ? "核心成果" : "辅助成果"}</small>
                  <em>{file.category}</em>
                </button>
              ))}
            </div>
          </section>

          <section className="panel detail-panel">
            <div className="panel-title compact">
              <span className="eyebrow">成果文件详情</span>
              <h2>{activeExport?.name ?? "暂无成果文件"}</h2>
              <p>{activeExport?.purpose ?? "暂无文件用途说明。"}</p>
            </div>
            {activeExport ? (
              <>
                <div className="detail-metric-grid">
                  <div className="detail-metric"><span>文件类型</span><strong>{activeExport.fileType}</strong></div>
                  <div className="detail-metric"><span>记录数</span><strong>{formatRows(activeExport.rows)}</strong></div>
                  <div className="detail-metric"><span>用途标签</span><strong>{activeExport.category}</strong></div>
                  <div className="detail-metric"><span>是否核心成果</span><strong>{activeExport.core ? "是" : "否"}</strong></div>
                  <div className="detail-metric"><span>是否建议提交</span><strong>{activeExport.submit}</strong></div>
                  <div className="detail-metric"><span>是否需要复核</span><strong>{activeExport.review}</strong></div>
                </div>
                <section className="detail-section compact-card"><span className="eyebrow">适用场景</span><p>{activeExport.scenario}</p></section>
                <section className="detail-section compact-card"><span className="eyebrow">对应提交意义</span><p>{activeExport.core ? "支撑课程成果的核心证据、结构或评测结论。" : "用于补充复现说明、质量检查或过程留痕。"}</p></section>
                <button className="toggle-button" onClick={() => setShowExportFields((value) => !value)} type="button">
                  {showExportFields ? "收起字段说明" : "展开字段说明"}
                </button>
                {showExportFields ? <code className="field-preview">{activeExport.fields === "json" ? "JSON 结构化字段，详见文件内容。" : activeExport.fields}</code> : null}
              </>
            ) : null}

            {activeTopTechnologies.length ? (
              <section className="detail-section compact-card score-title">
                <span className="eyebrow">关键技术评分前五</span>
                <div className="focused-edge-list">
                  {activeTopTechnologies.map((tech) => (
                    <article key={tech.name}>
                      <strong>{tech.name} · {tech.key_tech_score}</strong>
                      <span>{tech.maturity_level}</span>
                      <em>证据来源 {tech.evidence_doc_count} 份；{tech.missing_evidence || "无规则缺口"}</em>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}
          </section>
        </section>
      ) : null}
    </main>
  );
}


