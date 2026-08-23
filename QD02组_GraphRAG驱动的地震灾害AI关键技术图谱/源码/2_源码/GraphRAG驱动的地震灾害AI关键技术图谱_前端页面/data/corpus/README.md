# 地震灾害专题语料来源清单

该目录为默认 GraphRAG 索引语料，已统一收敛到“以地震灾害为例”的研究尺度。
每篇 Markdown 均保留来源、时间、区域和文档类型，并把正文整理为面向实体关系抽取的中文证据摘要。

## 规模

- 灾害案例：7 篇
- 论文：7 篇
- 专利：7 篇
- 政策：7 篇
- 项目：7 篇
- 报告：7 篇
- 标准：7 篇
- 合计：49 篇
- 灾害类型：地震

## 来源明细

| doc_id | 类型 | 年份 | 区域 | 技术主线 | 来源 |
|---|---|---:|---|---|---|
| `paper_bddnet_damage` | 论文 | 2020 | global | 震后建筑损毁识别 | Remote Sensing |
| `paper_xbd_damage_assessment` | 论文 | 2019 | global | 遥感震损智能解译 | arXiv |
| `paper_transfer_learning_damage` | 论文 | 2022 | global | 遥感震损智能解译 | Remote Sensing |
| `paper_myshake_network` | 论文 | 2024 | United States | 地震早期预警 | UC Berkeley |
| `paper_lifeline_resilience` | 论文 | 2019 | global | 生命线震损风险传播GNN | World Bank and GFDRR |
| `paper_ai_emergency_qa` | 论文 | 2020 | global | 地震应急辅助决策 | GFDRR |
| `paper_seismic_risk_prediction` | 论文 | 2024 | global | 地震风险时空预测 | GEM Foundation |
| `patent_tw_earthquake_ai` | 专利 | 2015 | China Taiwan | 地震早期预警 | Google Patents TW201544830A |
| `patent_tw_earthquake_warning` | 专利 | 2014 | China Taiwan | 地震早期预警 | Google Patents TWI464443B |
| `patent_myshake_warning` | 专利 | 2018 | United States | 地震早期预警 | Google Patents US20180376314A1 |
| `patent_earthquake_prediction_device` | 专利 | 2014 | global | 地震风险时空预测 | Google Patents WO2014128965A1 |
| `patent_structural_damage_predictor` | 专利 | 2021 | United States | 震后建筑损毁识别 | Google Patents US10915829B1 |
| `patent_predictive_emergency_analytics` | 专利 | 2018 | global | 地震应急辅助决策 | Google Patents WO2018039142A1 |
| `patent_disaster_recovery_prediction` | 专利 | 2017 | United States | 震后救援调度优化 | Google Patents US20170308421A1 |
| `project_shakealert` | 项目 | 2024 | United States | 地震早期预警 | USGS |
| `project_myshake` | 项目 | 2024 | United States | 地震早期预警 | UC Berkeley |
| `project_xview2_earthquake` | 项目 | 2024 | global | 震后建筑损毁识别 | DIU and Carnegie Mellon |
| `project_nasa_earthquake_response` | 项目 | 2024 | global | 遥感震损智能解译 | NASA |
| `project_openquake` | 项目 | 2024 | global | 地震风险时空预测 | GEM Foundation |
| `project_fema_hazus` | 项目 | 2024 | United States | 震后灾情快速评估 | FEMA |
| `project_hot_osm_earthquake` | 项目 | 2024 | global | 地震多模态灾情理解 | Humanitarian OpenStreetMap Team |
| `policy_sendai_framework_earthquake` | 政策 | 2015 | global | 地震证据图谱GraphRAG | UNDRR |
| `policy_china_earthquake_plan` | 政策 | 2024 | China | 地震应急辅助决策 | State Council of China |
| `policy_china_14th_drr_plan` | 政策 | 2022 | China | 生命线震损风险传播GNN | State Council of China |
| `policy_japan_disaster_plan` | 政策 | 2024 | Japan | 地震早期预警 | Cabinet Office Japan |
| `policy_us_mitigation_framework` | 政策 | 2023 | United States | 地震风险时空预测 | FEMA |
| `policy_fema_nims` | 政策 | 2023 | United States | 震后救援调度优化 | FEMA |
| `policy_ai_governance_response` | 政策 | 2023 | United States | 地震证据图谱GraphRAG | NIST |
| `case_turkiye_syria_earthquake` | 灾害案例 | 2023 | Turkiye | 震后建筑损毁识别 | ReliefWeb |
| `case_morocco_earthquake` | 灾害案例 | 2023 | Morocco | 生命线震损风险传播GNN | ReliefWeb |
| `case_nepal_earthquake_pdna` | 灾害案例 | 2015 | Nepal | 震后救援调度优化 | ReliefWeb |
| `case_haiti_earthquake` | 灾害案例 | 2010 | Haiti | 地震应急辅助决策 | World Bank |
| `case_noto_earthquake` | 灾害案例 | 2024 | Japan | 地震早期预警 | ReliefWeb |
| `case_turkiye_rdna` | 灾害案例 | 2023 | Turkiye | 震后灾情快速评估 | GFDRR |
| `case_afghanistan_earthquake_2023` | 灾害案例 | 2023 | Afghanistan | 地震多模态灾情理解 | ReliefWeb |
| `standard_iso_22320_incident_management` | 标准 | 2018 | global | 地震应急辅助决策 | ISO 22320 |
| `standard_iso_22322_public_warning` | 标准 | 2022 | global | 地震早期预警 | ISO 22322 |
| `standard_iso_22324_colour_alerts` | 标准 | 2022 | global | 地震早期预警 | ISO 22324 |
| `standard_iso_31000_risk` | 标准 | 2018 | global | 地震风险时空预测 | ISO 31000 |
| `standard_iso_37123_resilient_cities` | 标准 | 2019 | global | 生命线震损风险传播GNN | ISO 37123 |
| `standard_ogc_sensorthings` | 标准 | 2021 | global | 地震早期预警 | OGC |
| `standard_oasis_cap` | 标准 | 2010 | global | 地震早期预警 | OASIS |
| `report_gfdrr_ml_drm` | 报告 | 2018 | global | 遥感震损智能解译 | GFDRR and World Bank |
| `report_gfdrr_responsible_ai` | 报告 | 2020 | global | 地震应急辅助决策 | GFDRR |
| `report_jrc_ai_drm` | 报告 | 2025 | Europe | 地震证据图谱GraphRAG | European Commission Joint Research Centre |
| `report_undrr_gar2025` | 报告 | 2025 | global | 地震风险时空预测 | UNDRR |
| `report_worldbank_lifelines` | 报告 | 2019 | global | 生命线震损风险传播GNN | World Bank and GFDRR |
| `report_fema_building_codes` | 报告 | 2020 | United States | 震后建筑损毁识别 | FEMA |
| `report_cdri_giri` | 报告 | 2023 | global | 生命线震损风险传播GNN | CDRI |

## 使用边界

- 本目录服务于期末大作业中的地震灾害 AI 技术图谱实验。
- 正文为中文整理稿，不是原始文献或网页全文转载。
- 正式引用应回到各文件 frontmatter 中的 `source_url` 核对原始来源。
