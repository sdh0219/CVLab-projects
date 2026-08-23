---
doc_id: EQ_DOC_003
title: ShakeMap与PAGER影响评估
source_file: 地震灾害数据收集与整理.docx
topic: 影响评估数据链
source_type: 整理报告
graph_usage: Document Source Evidence
language: zh-CN
quality_status: 待复核
---

# ShakeMap与PAGER影响评估

## 三、 地震动、烈度图与PAGER快速影响评估数据链

地震动参数（如地面峰值加速度 PGA、地面峰值速度 PGV）是评估地面震动剧烈程度和预测建筑物结构物理破坏力的核心指标 [4, 26]。美国地质调查局的 ShakeMap 系统和 PAGER（Prompt Assessment of Global Earthquakes for Response）系统，是当前全球最为先进的震后快速半结构化影响评估工具，广泛服务于灾害防御及应急资源调度决策 [26, 27, 28]。

PAGER 系统在发震后数分钟内自动触发，通过将快速推定的 ShakeMap 地震动场叠加在动态全球人口暴露体格网（WorldPop）及历史脆弱性矩阵上，预测可能造成的死亡人数和经济损失 [26, 27, 29]。PAGER 的红、橙、黄、绿四色警报阈值，为国际应急协调提供了量化的指挥链依据 [5, 29, 30]。

发震 (Earthquake Origin) │ ▼ 计算震源机制解与有限断层破裂线 (USGS Finite Fault Model) │ ▼ 融合台站实测波形 (Strong Motion Seismometers) ──► 绘制 ShakeMap 地震动图 (PGA / PGV / MMI) │ ▼ 合并暴露人口格网数据 (WorldPop Population Grid) ◄──────────┘ │ ▼ 叠加历史脆弱性矩阵 (Vulnerability Matrix) │ ▼ 生成 PAGER 快速评估结果 (死亡人数 / 经济损失估计值) │ ▼ 触发多色警报级别 ──► 输出标准 XML / XML-PAGER 数据包


表 3

| 评估指标与评估报告产品类型 | 2024年能登半岛地震数据值 [2, 4, 5, 29] | 2023年土耳其双震（主震）数据值 [9, 10, 31, 32] | 2015年尼泊尔大震数据值 [16, 17, 33, 34] | 2021年海地大震数据值 [20, 21] |
| --- | --- | --- | --- | --- |
| ShakeMap 最大实测PGA | () [2] | 超出 范围 [10, 35] | - （由于 Kathmandu 盆地厚软沉积层放大，长周期波突出） [16] | [20] |
| 最大修正麦加利烈度 (MMI) | MMI IX - XI (极度暴烈震动) [2, 5] | MMI X (毁灭性强烈震动) [9] | MMI IX - X [3, 33] | MMI VIII (严重破坏烈度) [20] |
| PAGER 经济损失警报级别 | 红色警报（经济损失极可能达到数亿美元，占日本国内生产总值的1%以下） [29] | 红色警报（经济损失数额极其巨大，破坏性极广） [9] | 红色警报（预估经济损失达到数十亿美元，约占尼泊尔国内生产总值的50%） [16] | 红色警报（预估损失巨大，占其GDP约 ，达到 ） [20] |
| PAGER 人员伤亡警报级别 | 黄色至橙色警报（得益于日本极高设防标准，实际由于大震直接死亡 人） [2, 29] | 红色警报（极高概率造成上万人遇难，主震实际导致土耳其及叙利亚境内超 人遇难） [9, 31, 32] | 红色警报（预估超千人遇难，主震及余震实际造成尼泊尔境内超过 人死亡） [33, 34] | 红色警报（实际造成 人确认遇难，超过 人受伤） [20] |
| 对应 ShakeMap 可下载物理产品 | Intensity Contours (JSON), XML Grid, Uncertainty Grid, PGA Contours, Shape Files (ZIP) [4, 36] | Intensity Contours (JSON), XML Grid, PGA Map (JPG/PDF), Fault Rupture JSON [36] | Intensity Map (PDF), PAGER XML results, Fatality Alert Histogram (PDF/PNG) [29] | PGA contours, Landslide Inventory Data Release, XML Grid [37, 38] |

从工程运用的角度看，这些评估报告反映出地震动的不确定性（Uncertainty Grid）也是一项核心自变量 [4]。AI智能体在调用 ShakeMap 数据进行灾害体分析时，不能仅读取“地面峰值加速度（PGA）”的平均值，还必须同时读取“不确定性网格（Uncertainty Grid）” [4]。在实测台站稀疏（台间距大于 ）的地区，不确定性标准差通常会剧烈上升 [26, 39]。如果在评估中未对高不确定性区域进行均值校正，将导致后端 AI 模型输出极高方差的建筑破坏预测，从而引发应急物资配置失衡 [1, 39]。
