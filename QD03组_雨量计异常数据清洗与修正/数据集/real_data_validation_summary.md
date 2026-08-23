# 真实/类真实数据迁移验证摘要

- 数据来源标识：**real-public-3rww**。
- 站点：**Bell Acres**。
- 推断时间分辨率：**15min**。
- 本项目按该分辨率缩放物理上限阈值，本次上限为 **60.0 mm/interval**。
- 本部分不使用逐点真值标签，因此不计算 precision、recall、F1。
- 目的在于展示规则 QC、质量标识和报告输出能否迁移到无真值场景。
- 在线公开数据源：3 Rivers Wet Weather Rainfall Data Downloads。
- 原始单位：inch per 15min，已换算为 `rainfall_mm`。
- 来源页面说明 Rain Gauge CSV 为 ALCOSAN QA/QC 后发布的数据。
- 下载地址：https://mds.3riverswetweather.org/atlas/docs/resources/rainfall/January%202020%2015-min%20Rain%20Data.csv

## 数据质量变化

- 规整后样本数：2976；
- 清洗前缺失率：0.0%，清洗后缺失率：0.0%；
- 清洗前最大值：2.29 mm，清洗后最大值：2.3 mm；
- 清洗前累计雨量：96.0 mm，清洗后累计雨量：96.3 mm；
- 规则可疑点计数：{'spurious': 11, 'stuck': 6}。

## 说明

若数据来源为 simulated-realistic，表示当前目录没有用户提供的真实 CSV，程序使用项目样例生成类真实流程展示数据。
若数据来源为 real-public-3rww，表示程序使用 3 Rivers Wet Weather 公开雨量计下载数据；该数据没有本项目逐点异常真值，因此只做无真值 QC 迁移验证。
真实公开数据来自官方 QA/QC 后 CSV，本项目检出的 spurious/stuck 仅表示在课程规则下建议复核的可疑点，不等同于官方数据错误。
真实业务迁移仍需结合站点元数据、当地极端降雨阈值和人工复核流程重新校准。