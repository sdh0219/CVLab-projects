# GraphRAG驱动的地震灾害AI关键技术图谱项目

这是一个可运行的 GraphRAG 风格工程原型。当前成果已经统一到“以地震灾害为例”的研究尺度，不再以多个灾害类型并列展示。

项目目标：

```text
地震论文 / 地震相关专利 / 地震示范项目 / 地震政策预案 / 地震案例 / 地震适用标准 / 地震相关报告
  -> GraphRAG 抽取实体、关系、声明、证据来源
  -> 构建地震关键技术社区和 community reports
  -> 面向问题检索与归纳
  -> 发现地震早期预警、震后损毁评估、应急调度、生命线风险和证据链问答等技术簇
  -> 专家校验
  -> 沉淀为地震灾害AI关键技术图谱
```

## 当前已实现

- 地震专题语料：`data/corpus/sample/`，覆盖论文、专利、项目、政策、地震案例、标准、报告 7 类来源
- 语料来源清单：`data/corpus/README.md`
- 地震专题本体：`config/ontology.json`
- 本地 GraphRAG 风格索引管线：`graphrag_atlas/`
- 规则抽取器、LLM 抽取器、hybrid 抽取模式
- 实体、关系、声明、证据来源抽取
- 地震关键技术社区报告 `community_reports`
- Global Search / Local Search / Gap Search
- 图谱 CSV/JSON 导出
- 专家校验初始表、语料清单、质量报告
- Neo4j 导入 CSV、GraphML 和可视化 JSON
- 关键技术评分、问答评测种子集、QA 自动评测结果
- 拓扑社区发现、冲突不确定性筛查、成果清单
- 最终 Markdown/HTML 报告和干净提交 zip 包
- 前端真实数据快照 `public/atlas/atlas_frontend.json`

## 快速运行

重新生成地震专题语料、索引、增强分析、前端快照并校验：

```bash
npm.cmd run atlas:refresh
```

单独生成地震语料：

```bash
npm.cmd run atlas:corpus:earthquake
```

单独构建规则索引：

```bash
npm.cmd run atlas:index
```

完整检查、构建和打包：

```bash
npm.cmd run atlas:all
```

## 查询

```bash
npm.cmd run atlas:global
npm.cmd run atlas:local
npm.cmd run atlas:gaps
```

真实中文研究问题可直接使用 Python CLI：

```bash
python -m graphrag_atlas global-search "地震灾害AI防灾减灾有哪些关键技术社区" --output outputs/graphrag_index
python -m graphrag_atlas local-search "遥感震损智能解译" --output outputs/graphrag_index
python -m graphrag_atlas local-search tech_remote_sensing_eq_damage --output outputs/graphrag_index
python -m graphrag_atlas gap-search --output outputs/graphrag_index
```

## LLM抽取

默认命令使用离线规则抽取器。严格使用 LLM 抽取：

```bash
$env:ATLAS_LLM_API_KEY="你的API Key"
$env:ATLAS_LLM_MODEL="你的模型名"
npm.cmd run atlas:index:llm
```

规则 + LLM 混合抽取：

```bash
$env:ATLAS_LLM_API_KEY="你的API Key"
npm.cmd run atlas:index:hybrid
```

使用 NVIDIA Build 的 `minimaxai/minimax-m3`：

```bash
$env:ATLAS_LLM_API_KEY="你的新NVIDIA Build Key"
npm.cmd run atlas:index:nvidia:hybrid
```

LLM 接入参数见 `.env.example`。当前实现使用 OpenAI-compatible `/chat/completions` 接口，并把模型输出约束在 `config/ontology.json` 的实体 ID 和关系规则内。

## 输出位置

```text
outputs/graphrag_index/
  documents.jsonl
  chunks.jsonl
  entities.jsonl
  claims.jsonl
  relations.jsonl
  community_reports.jsonl
  exports/
    technology_nodes.csv
    scenario_nodes.csv
    evidence_edges.csv
    community_reports.csv
    community_reports.json
    expert_review_log.csv
    expert_review_priority.csv
    corpus_manifest.csv
    graph_nodes.csv
    graph_edges_neo4j.csv
    graph_visualization.json
    atlas.graphml
    neo4j_import.cypher
    key_technology_assessment.csv
    key_technology_assessment.json
    key_technology_assessment.md
    qa_evaluation_set.csv
    qa_evaluation_set.json
    qa_evaluation_results.csv
    qa_evaluation_results.json
    topology_communities.csv
    topology_communities.json
    topology_communities.md
    uncertainty_report.json
    uncertainty_report.md
    submission_manifest.md
    submission_manifest.json
    atlas_quality_report.json
    atlas_quality_report.md
public/atlas/
  atlas_frontend.json
  index_summary.json
outputs/final_deliverables/
  final_report.md
  final_report.html
  submission_checklist.md
  地震灾害AI防灾减灾关键技术图谱构建_提交包/
  地震灾害AI防灾减灾关键技术图谱构建_提交包.zip
```

## 说明文档

- [项目实现与运行说明](docs/项目实现与运行说明.md)
- [GraphRAG研究方案说明](docs/GraphRAG研究方案说明.md)
- [阶段性工作汇总](docs/阶段性工作汇总.md)

## 当前边界

当前版本是可运行的地震灾害专题原型。专家审核表和专家预审优先级表仍是待审核结构，不代表已完成人工专家评审。Neo4j 导入文件已经生成，但仍需在真实 Neo4j 实例中执行和验收。
