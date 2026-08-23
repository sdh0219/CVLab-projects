# GraphRAG驱动的地震灾害AI关键技术图谱研究方案

## 1. 研究定位

本项目不再泛化描述所有自然灾害，而是以地震灾害为主要研究和展示对象，构建一套基于 GraphRAG 的证据图谱生成与问答机制。

GraphRAG 在本项目中的角色是：

```text
地震专题文本语料
  -> 实体、关系、声明和证据抽取
  -> 地震证据知识图构建
  -> 地震关键技术社区发现与社区报告生成
  -> 问题驱动检索与归纳
  -> 专家校验
  -> 地震灾害AI关键技术图谱沉淀
```

## 2. 核心科学问题

核心问题：

> 如何基于 GraphRAG 从地震灾害多源文本证据中自动发现、组织和校验 AI 关键技术，并形成可追溯、可问答、可更新的地震灾害AI关键技术图谱？

子问题：

1. 地震灾害场景下有哪些稳定的 AI 关键技术社区？
2. 每个技术社区对应哪些地震阶段、数据条件、模型方法和工程证据？
3. 哪些技术文献热度较高，但缺少真实地震案例或部署验证？
4. 地震早期预警、震后损毁评估、应急调度、生命线风险和证据链问答中还存在哪些证据缺口？

## 3. 数据语料设计

默认语料位于 `data/corpus/sample/`，已统一为地震专题语料。语料类型如下：

| 语料类型 | 地震专题作用 |
|---|---|
| 地震论文与综述 | 提供技术术语、方法演化、实验指标和研究脉络 |
| 地震相关专利 | 识别地震预警、震损评估、应急辅助决策等工程转化路径 |
| 地震示范项目 | 识别 ShakeAlert、MyShake、OpenQuake、Hazus 等部署和工具链 |
| 地震政策预案 | 限定预警发布、应急调度、数据治理和防震减灾任务边界 |
| 地震案例与复盘 | 将技术映射到土耳其叙利亚地震、日本能登半岛地震等真实事件 |
| 地震适用标准 | 提供预警、应急管理、传感器、风险管理和互操作规范 |
| 地震相关报告 | 补充震害风险、生命线韧性、建筑规范和责任 AI 证据 |

每篇文档至少保留：

```text
doc_id
title
source_type
source_name
source_url
year
region
disaster_type = 地震
```

## 4. 领域本体设计

第一版本体已经冻结在 `config/ontology.json`：

| 实体类型 | 地震专题含义 |
|---|---|
| `DisasterType` | 固定为地震 |
| `Scenario` | 震前监测感知、地震风险评估、地震早期预警、震后应急调度、震后损毁评估 |
| `AITech` | 地震早期预警、震后建筑损毁识别、遥感震损智能解译、地震应急辅助决策等 |
| `Model` | Transformer、U-Net、GNN、LLM、强化学习、CNN、LSTM、机器学习 |
| `Dataset` | 地震台网数据、遥感影像、物联传感器、众源文本、建筑物足迹数据、生命线设施数据 |
| `Task` | 地震监测预警、建筑损毁评估、震后资源调度、证据链问答、生命线风险评估 |
| `Case` | 土耳其叙利亚地震、日本能登半岛地震、尼泊尔地震、海地地震、摩洛哥地震等 |
| `Policy` | 地震应急预案、地震预警发布规范、应急管理技术标准、防震减灾规划 |
| `Limitation` | 标注稀缺、跨区域泛化不足、实时部署困难、幻觉风险、震后通信中断等 |

## 5. 关系模式设计

每条边都绑定 `doc_id`、`chunk_id`、`evidence_text`、`confidence` 和专家状态。

| 关系 | From | To | 含义 |
|---|---|---|---|
| `APPLIES_TO` | `AITech` | `DisasterType` | 技术适用于地震灾害 |
| `SERVES_STAGE` | `AITech` | `Scenario` | 技术服务的地震阶段 |
| `SOLVES` | `AITech` | `Task` | 技术解决的地震防灾减灾任务 |
| `DEPENDS_ON` | `AITech` | `Dataset` | 技术依赖的数据条件 |
| `USES_MODEL` | `AITech` | `Model` | 技术采用的模型结构或算法家族 |
| `VALIDATED_IN` | `AITech` | `Case` | 技术是否在地震案例或工程中验证 |
| `LIMITED_BY` | `AITech` | `Limitation` | 技术边界和风险 |
| `REQUIRED_BY` | `Scenario` | `Policy` | 地震场景对应的政策或标准要求 |

## 6. GraphRAG索引流程

1. 文档清洗与切块：保留地震专题元数据和来源 URL。
2. 实体、关系、声明抽取：抽取“哪项 AI 技术在地震场景下解决什么任务，以及证据来自哪里”。
3. 证据图构建：将实体、关系、声明和原文片段连接为可追溯证据图。
4. 社区发现：形成地震早期预警、震后损毁评估、应急调度、生命线风险、证据图谱等技术社区。
5. 社区报告生成：为每个技术社区生成摘要、代表证据、验证案例和待复核问题。
6. 查询与回答：根据全局、局部、缺口三类问题返回证据链。
7. 专家校验与图谱沉淀：将人工确认后的关系和证据写入正式图谱。

## 7. 问答模式设计

### Global Search

```text
地震灾害AI防灾减灾领域有哪些关键技术社区？
哪些地震技术方向证据最强？
哪些地震技术社区缺少真实工程验证？
```

### Local Search

```text
遥感震损智能解译在土耳其叙利亚地震案例中的证据链是什么？
地震早期预警依赖哪些传感数据和模型？
生命线震损风险传播GNN有哪些案例验证和限制条件？
```

### Gap Search

```text
哪些地震AI技术缺少真实案例验证？
哪些技术缺少数据依赖证据？
哪些地震应急场景存在高优先级复核风险？
```

## 8. 关键技术识别指标

关键技术评分不只看出现频次，而是结合：

```text
KeyTechScore =
  evidence_doc_count
  + earthquake_stage_coverage
  + dataset_dependency
  + case_validation
  + limitation_boundary
```

其中：

- `evidence_doc_count`：证据来源数量；
- `earthquake_stage_coverage`：覆盖地震监测、预警、评估、调度等应用环节数量；
- `dataset_dependency`：是否明确依赖地震台网、遥感、传感器或建筑物数据；
- `case_validation`：是否有土耳其叙利亚地震、日本能登半岛地震等案例支撑；
- `limitation_boundary`：是否明确披露泛化、实时性、幻觉或通信中断等限制。

## 9. 输出成果

| 文件 | 内容 |
|---|---|
| `technology_nodes.csv` | 地震AI技术节点、别名、社区、证据分数、专家状态 |
| `scenario_nodes.csv` | 地震类型、应用阶段、政策节点和证据数量 |
| `evidence_edges.csv` | 地震技术关系、来源文档、证据片段、置信度 |
| `community_reports.json` | 地震关键技术社区报告、代表文档和开放问题 |
| `expert_review_log.csv` | 专家审核记录、意见、版本和时间 |
| `atlas.graphml` | 可导入 Gephi、yEd 等工具的地震技术图谱 |
| `neo4j_import.cypher` | Neo4j 导入模板 |

## 10. 论文创新点

1. 面向地震灾害 AI 关键技术识别的证据图谱构建框架；
2. 将社区报告、证据链问答和专家校验结合，用于地震关键技术发现；
3. 区分论文热度、工程验证和真实地震应急需求；
4. 输出可追溯、可问答、可更新的地震灾害AI关键技术图谱；
5. 发现地震AI技术供给中的结构性证据缺口。

## 11. 当前原型边界

当前项目已具备可运行规则索引、LLM 抽取接口、地震专题语料、图谱导出、问答评测和提交包生成能力。专家审核表仍处于 `pending` 初始状态，Neo4j 导入文件仍需在真实图数据库中执行和验收。

## 参考资料

- Microsoft GraphRAG documentation: https://microsoft.github.io/graphrag/
- Microsoft Research, From Local to Global: A GraphRAG Approach to Query-Focused Summarization: https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/
