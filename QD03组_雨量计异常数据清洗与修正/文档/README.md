# 雨量计异常数据清洗与修正

> AI + 防灾减灾课程实践项目 · 项目3：雨量计异常数据清洗与修正

本项目面向雨量计、水位计、气象站等监测传感器时间序列，构建一条可复现的数据质量控制链路：
**时间轴规整 → 规则异常检测 → 缺失与异常修正 → 滑动窗口平滑 → 质量标识 → 学习型异常分数辅助 →
方法对比 → 消融实验 → 预警影响分析 → 真实/类真实迁移验证**。

项目主线仍然是项目3要求的传感器异常识别、缺失值处理、插值修正、清洗前后对比和防灾减灾应用分析。
LSTM-AutoEncoder 只作为异常检测增强和对照实验，不做未来水位预测，也不替代规则法。

## 1. 环境安装

```bash
pip install -r requirements.txt

# 可选：启用 LSTM-AutoEncoder
pip install -r requirements-ml.txt
```

如果没有安装 `torch`，程序不会崩溃；LSTM-AE 会被标记为 skipped，并在
`output/reports/ml_anomaly_scores.csv`、方法对比表和日志中说明。

## 2. 运行命令

```bash
# 保持原有一键行为：规则清洗 baseline
python src/main.py
python src/main.py --mode baseline

# 增强流程：规则法 + 质量标识 + ML辅助 + 方法对比 + 预警影响
python src/main.py --mode enhanced

# 只运行学习型异常检测
python src/main.py --mode ml

# 只运行规则组件消融实验
python src/main.py --mode ablation

# 运行真实/类真实无真值迁移验证
python src/main.py --mode real

# 运行全部流程
python src/main.py --mode all
```

### Windows 一键运行 exe

最终提交包的 `2_源码` 目录中已提供 `雨量计一键运行.exe`。双击后会在当前 `2_源码` 目录下执行完整流程，等价于运行 `python src/main.py --mode all` 的主要实验内容，并把结果写入 `data` 和 `output` 文件夹，同时生成 `一键运行日志.txt`。该 exe 已打包 pandas、numpy、matplotlib、scipy、scikit-learn 等核心依赖，不要求电脑预先安装 Python，也不依赖系统 PATH。

为控制体积并提高通用电脑上的运行稳定性，自包含 exe 默认跳过 torch/LSTM-AE，只保留规则 QC 主方法和 Isolation Forest 辅助分数。报告中的方法结论不受影响，因为 LSTM-AE 本来只作为辅助复核分数，单独 F1 较低，不作为主方法。若需要复现 LSTM-AE，可安装 `requirements.txt` 与 `requirements-ml.txt` 后运行 `python src/main.py --mode all`。

## 3. 数据与输出

| 类型 | 路径 |
|---|---|
| 原始合成数据、真值、多传感器数据 | `data/raw/` |
| 原规则清洗结果 | `data/cleaned/rain_gauge_cleaned.csv` |
| 异常标记明细 | `data/cleaned/rain_gauge_flags.csv` |
| 带质量标识的增强结果 | `data/processed/cleaned_with_quality_flags.csv` |
| 真实/类真实迁移结果 | `data/real/processed_real_qc.csv` |
| 统计表与实验结果 | `output/reports/` |
| 图表 | `output/figures/` |
| 技术方案与实验报告 | `docs/技术方案.md`、`docs/实验报告.md` |
| 汇报 PPT | `ppt/雨量计异常数据清洗与纠正_汇报.pptx` |

## 4. 新增结果表

| 文件 | 说明 |
|---|---|
| `feature_summary.csv` | 时序特征统计摘要 |
| `ml_anomaly_scores.csv` | Isolation Forest 分数、LSTM-AE 重构误差与标签 |
| `hybrid_qc_decisions.csv` | 规则法与学习型方法融合后的最终决策 |
| `method_comparison.csv` | 规则法、IF、LSTM-AE 与组合方法对比 |
| `ablation_results.csv` | 规则组件消融实验 |
| `warning_impact.csv` | 预警触发、误报、漏报对比 |
| `real_data_validation_summary.md` | 真实/类真实无真值迁移验证摘要 |

## 5. 图表说明

- `fig1`~`fig6`：原始异常、质量仪表板、清洗前后、累计雨量、平滑效果、检测指标；
- `fig7_method_comparison.png`：方法对比柱状图；
- `fig8_ml_anomaly_scores.png`：IF/LSTM 异常分数时间序列；
- `fig9_ablation_f1.png`、`fig10_ablation_rainfall_error.png`：消融实验；
- `fig11_warning_impact.png`、`fig12_warning_timeline.png`：预警影响；
- `fig13_real_data_qc.png`：真实/类真实迁移展示；
- `fig_quality_flags_distribution.png`：质量标识分布。

## 6. 当前核心结论

在合成有真值实验中，规则法仍是主方法：Precision 100.0%、Recall 97.45%、F1 98.71%，
清洗后总降雨量 708.6 mm，接近真值 710.9 mm，累计雨量误差为 -0.32%。

学习型模型提供辅助分数：源码 Python 环境可启用 Isolation Forest 和 LSTM-AE；自包含 exe 默认启用 Isolation Forest、跳过 LSTM-AE，但二者都不替代规则 QC 主方法。实验结果显示学习型方法单独使用时 F1 低于规则法；
组合方法提升了部分召回，却引入较多误报并削弱累计雨量。因此最终设计采用“规则法直接修正，学习型方法提示复核”的混合策略。

预警影响分析显示，原始污染数据在 10min、1h、3h、24h 阈值下产生大量误报样本；
corrected 数据将误报样本降为 0。smoothed 数据适合展示降噪，但可能带来少量漏报，因此主结果采用 corrected。

## 7. 放入真实雨量 CSV

将真实数据保存为：

```text
data/real/raw_real_rainfall.csv
```

必需字段：

```text
timestamp,rainfall_mm
```

可选字段：

```text
water_level,humidity,temperature,station_id
```

也兼容现有样例中的 `water_level_m`、`humidity_pct`、`temperature_c`。真实数据没有逐点真值时，
程序只输出质量统计、规则可疑点数量、累计雨量变化和质量标识分布，不计算 Precision/Recall/F1。
如果以后放入新的真实雨量计数据，优先替换本路径下的 `data/real/raw_real_rainfall.csv`。CSV 至少需要包含 `timestamp` 和 `rainfall_mm` 两列，`rainfall_mm` 应为每个时间间隔内的毫米雨量；若原始单位是 inch/15min，需要先乘以 25.4 换算为 mm。没有逐点异常真值的新数据仍可运行迁移验证，但只输出规则可疑点和清洗结果，不计算检测 Precision/Recall/F1。不要直接用无标签新数据替换 `data/raw/rain_gauge_raw.csv`，因为该路径用于合成 10min 有真值实验，若替换它还需要同步提供 `data/raw/rain_gauge_truth.csv`。
当前工程已放入一份公开在线雨量数据：[3 Rivers Wet Weather 的 January 2020 15-min Rain Data](https://mds.3riverswetweather.org/atlas/docs/resources/rainfall/January%202020%2015-min%20Rain%20Data.csv)，
选用 `Bell Acres` 站点，将原始英寸/15min 换算为 `rainfall_mm`。如果你以后删除或替换该 CSV，
程序仍支持用户自备真实数据；若没有真实 CSV，才会生成 `simulated-realistic` 类真实流程展示数据，并在报告中明确标注，绝不冒充真实观测。
3 Rivers Wet Weather 页面说明 Rain Gauge CSV 为 ALCOSAN QA/QC 后发布的数据；本项目对真实数据检出的 `spurious/stuck`
只表示课程规则下的可疑复核点，不等同于官方数据错误。

## 8. 常见问题

**为什么不用 LSTM 做洪水水位预测？**  
因为本项目编号是项目3，任务主线是雨量计异常数据清洗与修正，不是项目5的水位预测。LSTM-AE 在这里只用于学习型异常分数和辅助复核。

**为什么规则法仍是主方法？**  
规则法能解释每个异常的业务原因，且能通过“孤立跳变”等条件保护真实暴雨峰值；在监测预警场景中，稳定和可解释比盲目追求模型复杂度更重要。

**没有 torch 会怎样？**  
LSTM-AE 自动跳过，Isolation Forest、规则清洗、质量标识、预警影响、消融实验和真实迁移流程仍可运行。

**为什么主结果用 corrected 而不是 smoothed？**  
平滑能降噪，但会削弱峰值并改变阈值触发，可能造成漏报；因此 smoothed 单列输出供对比，主清洗结果采用 corrected。
